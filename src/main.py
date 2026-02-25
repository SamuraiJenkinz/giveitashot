"""
Email Summarizer Agent - Main Entry Point

Reads emails from an Exchange Online shared mailbox using Exchange Web Services (EWS),
generates a summary, and sends it to specified recipients.

Supports incremental mode (default): only fetches emails since the last successful run.
Use --full to fetch all emails from today instead.

Usage:
    python -m src.main
    python -m src.main --full
    python -m src.main --dry-run
"""

import argparse
import logging
import sys
from datetime import datetime

from .action_extractor import ActionExtractor
from .auth import EWSAuthenticator, AuthenticationError
from .classifier import EmailClassifier
from .config import Config
from .ews_client import EWSClient, EWSClientError
from .extractor import MessageCenterExtractor
from .state import StateManager
from .summarizer import EmailSummarizer


def setup_logging(debug: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if debug else logging.INFO
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Reduce noise from exchangelib
    if not debug:
        logging.getLogger("exchangelib").setLevel(logging.WARNING)


def main() -> int:
    """
    Main entry point for the Email Summarizer Agent.

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Email Summarizer Agent - Summarizes daily emails from a shared mailbox via EWS"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear the token cache and re-authenticate"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate summary but don't send email"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Fetch all emails from today (ignore last run time)"
    )
    parser.add_argument(
        "--clear-state",
        action="store_true",
        help="Clear state file (forces full fetch on next run)"
    )
    parser.add_argument(
        "--regular-only",
        action="store_true",
        help="Send only regular digest (skip major update digest)"
    )
    parser.add_argument(
        "--major-only",
        action="store_true",
        help="Send only major update digest (skip regular digest)"
    )
    args = parser.parse_args()

    # Setup logging
    debug_mode = args.debug or Config.DEBUG
    setup_logging(debug_mode)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Email Summarizer Agent Starting (EWS)")
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    try:
        # Validate configuration
        logger.info("Validating configuration...")
        Config.validate()
        logger.info(f"User account: {Config.USER_EMAIL}")
        logger.info(f"Send from: {Config.get_send_from()}")
        logger.info(f"Shared mailbox: {Config.SHARED_MAILBOX}")

        # Log recipient configuration
        to_recipients = Config.get_recipients()
        logger.info(f"Summary TO: {', '.join(to_recipients)}")
        if Config.SUMMARY_CC:
            logger.info(f"Summary CC: {', '.join(Config.SUMMARY_CC)}")
        if Config.SUMMARY_BCC:
            logger.info(f"Summary BCC: {', '.join(Config.SUMMARY_BCC)}")

        # Initialize authenticator
        logger.info("Initializing authentication...")
        authenticator = EWSAuthenticator()

        # Clear cache if requested
        if args.clear_cache:
            logger.info("Clearing token cache...")
            authenticator.clear_cache()

        # Get EWS credentials
        logger.info("Acquiring EWS credentials...")
        credentials = authenticator.get_ews_credentials()
        logger.info("Authentication successful")

        # Initialize EWS client
        logger.info("Initializing EWS client...")
        ews_client = EWSClient(credentials)

        # Initialize state manager for incremental fetching
        state = StateManager()

        # Handle --clear-state flag
        if args.clear_state:
            logger.info("Clearing state file...")
            state.clear()

        # Determine fetch mode (incremental vs full)
        since = None
        if args.full:
            logger.info("Full mode: fetching all emails from today")
        else:
            since = state.get_last_run(digest_type="regular")
            if since:
                logger.info(f"Incremental mode: fetching emails since {since.isoformat()}")
            else:
                logger.info("No previous run found, fetching all emails from today")

        # Fetch emails from shared mailbox
        logger.info(f"Fetching emails from {Config.SHARED_MAILBOX}...")
        emails = ews_client.get_shared_mailbox_emails(Config.SHARED_MAILBOX, since=since)

        if not emails:
            logger.info("No new emails found - skipping summary")
            logger.info("=" * 60)
            logger.info("Email Summarizer Agent Completed (No New Emails)")
            logger.info("=" * 60)
            return 0

        logger.info(f"Found {len(emails)} email(s)")

        # Classify emails to detect Message Center major updates
        logger.info("Classifying emails...")
        classifier = EmailClassifier()
        try:
            regular_emails, major_update_emails = classifier.classify_batch(emails)
            logger.info(f"Classification: {len(regular_emails)} regular, {len(major_update_emails)} major updates")
        except Exception as e:
            logger.warning(f"Classification failed, treating all as regular: {e}")
            regular_emails = emails
            major_update_emails = []

        # Regular digest processing (skip if --major-only)
        if not args.major_only:
            if not regular_emails:
                if major_update_emails:
                    logger.info(f"No regular emails to summarize ({len(major_update_emails)} major update(s) detected)")
                else:
                    logger.info("No new emails found - skipping summary")
                    logger.info("=" * 60)
                    logger.info("Email Summarizer Agent Completed (No New Emails)")
                    logger.info("=" * 60)
                    return 0
            else:
                # Generate summary
                logger.info("Generating email summary...")
                summarizer = EmailSummarizer()
                summary = summarizer.summarize_emails(regular_emails)

                # Format the summary
                subject = summarizer.get_subject_line(summary, Config.SHARED_MAILBOX)
                body_html = summarizer.format_summary_html(summary, Config.SHARED_MAILBOX)

                logger.info(f"Summary subject: {subject}")

                if args.dry_run:
                    logger.info("DRY RUN - Not sending regular digest email")
                    logger.info("-" * 40)
                    logger.info("Regular Digest Preview:")
                    logger.info(f"From: {Config.get_send_from()}")
                    logger.info(f"To: {', '.join(to_recipients)}")
                    if Config.SUMMARY_CC:
                        logger.info(f"CC: {', '.join(Config.SUMMARY_CC)}")
                    if Config.SUMMARY_BCC:
                        logger.info(f"BCC: {', '.join(Config.SUMMARY_BCC)}")
                    logger.info(f"Subject: {subject}")
                    logger.info(f"Emails summarized: {summary.total_count}")
                    if summary.total_count > 0:
                        logger.info("Email subjects:")
                        for email_summary in summary.email_summaries:
                            logger.info(f"  - {email_summary.subject}")
                    logger.info("-" * 40)
                else:
                    # Send the summary email
                    logger.info(f"Sending regular digest to {len(to_recipients)} recipient(s)...")
                    ews_client.send_email(
                        to_recipients=to_recipients,
                        subject=subject,
                        body_html=body_html,
                        cc_recipients=Config.SUMMARY_CC if Config.SUMMARY_CC else None,
                        bcc_recipients=Config.SUMMARY_BCC if Config.SUMMARY_BCC else None
                    )
                    logger.info("Regular digest email sent successfully!")

                    # Update state with current time for next incremental run
                    state.set_last_run(digest_type="regular")

        # Major digest processing (skip if --regular-only)
        if not args.regular_only:
            if major_update_emails:
                # Check if major digest is enabled
                if not Config.is_major_digest_enabled():
                    logger.info("Major updates detected but major digest not enabled (MAJOR_UPDATE_TO not configured)")
                else:
                    try:
                        logger.info(f"Processing {len(major_update_emails)} major update(s)...")

                        # Extract fields from major updates
                        extractor = MessageCenterExtractor()
                        major_fields = extractor.extract_batch(major_update_emails)
                        major_fields = extractor.deduplicate(major_fields)

                        if not major_fields:
                            logger.info("No major updates to digest after deduplication")
                        else:
                            # Extract AI actions from major updates
                            actions = {}
                            try:
                                action_extractor = ActionExtractor()
                                if action_extractor.available:
                                    logger.info(f"Extracting AI actions from {len(major_fields)} major update(s)...")
                                    actions = action_extractor.extract_actions_batch(major_fields)
                                    succeeded = sum(1 for v in actions.values() if v is not None)
                                    logger.info(f"AI action extraction: {succeeded}/{len(major_fields)} succeeded")
                                else:
                                    logger.info("AI action extraction unavailable (Azure OpenAI not configured)")
                            except Exception as e:
                                logger.warning(f"AI action extraction failed entirely: {e}")
                                actions = {}

                            # Format HTML and subject
                            # Format HTML and subject
                            if not args.major_only:
                                summarizer = EmailSummarizer()
                            major_html = summarizer.format_major_updates_html(major_fields, actions=actions)
                            major_subject = summarizer.get_major_subject_line(major_fields)

                            logger.info(f"Major digest subject: {major_subject}")

                            if args.dry_run:
                                logger.info("DRY RUN - Not sending major digest email")
                                logger.info("-" * 40)
                                logger.info("Major Digest Preview:")
                                major_recipients = Config.get_major_recipients()
                                logger.info(f"From: {Config.get_send_from()}")
                                logger.info(f"To: {', '.join(major_recipients)}")
                                if Config.MAJOR_UPDATE_CC:
                                    logger.info(f"CC: {', '.join(Config.MAJOR_UPDATE_CC)}")
                                if Config.MAJOR_UPDATE_BCC:
                                    logger.info(f"BCC: {', '.join(Config.MAJOR_UPDATE_BCC)}")
                                logger.info(f"Subject: {major_subject}")
                                logger.info(f"Updates: {len(major_fields)}")
                                # Count by urgency
                                from .extractor import UrgencyTier
                                critical = sum(1 for u in major_fields if u.urgency == UrgencyTier.CRITICAL)
                                high = sum(1 for u in major_fields if u.urgency == UrgencyTier.HIGH)
                                normal = sum(1 for u in major_fields if u.urgency == UrgencyTier.NORMAL)
                                logger.info(f"Urgency breakdown: {critical} Critical, {high} High, {normal} Normal")
                                if actions:
                                    ai_count = sum(1 for v in actions.values() if v is not None)
                                    logger.info(f"AI actions extracted: {ai_count}/{len(major_fields)} updates")
                                logger.info("MC IDs:")
                                for update in major_fields:
                                    mc_id = update.mc_id or "MC######"
                                    logger.info(f"  - {mc_id}")
                                logger.info("-" * 40)
                            else:
                                # Send the major digest email
                                major_recipients = Config.get_major_recipients()
                                logger.info(f"Sending major digest to {len(major_recipients)} recipient(s)...")
                                ews_client.send_email(
                                    to_recipients=major_recipients,
                                    subject=major_subject,
                                    body_html=major_html,
                                    cc_recipients=Config.MAJOR_UPDATE_CC if Config.MAJOR_UPDATE_CC else None,
                                    bcc_recipients=Config.MAJOR_UPDATE_BCC if Config.MAJOR_UPDATE_BCC else None
                                )
                                logger.info("Major digest email sent successfully!")

                                # Update state for major digest
                                state.set_last_run(digest_type="major")

                    except Exception as e:
                        logger.error(f"Major digest failed: {e}")
                        # Don't crash - regular digest may have already been sent

        logger.info("=" * 60)
        logger.info("Email Summarizer Agent Completed Successfully")
        logger.info("=" * 60)
        return 0

    except AuthenticationError as e:
        logger.error(f"Authentication failed: {e}")
        logger.error("Please check your Azure AD app registration and credentials.")
        return 1

    except EWSClientError as e:
        logger.error(f"EWS error: {e}")
        logger.error("Please verify you have access to the shared mailbox.")
        return 1

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        return 1

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
