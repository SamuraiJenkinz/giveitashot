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

from .auth import EWSAuthenticator, AuthenticationError
from .config import Config
from .ews_client import EWSClient, EWSClientError
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
            since = state.get_last_run()
            if since:
                logger.info(f"Incremental mode: fetching emails since {since.isoformat()}")
            else:
                logger.info("No previous run found, fetching all emails from today")

        # Fetch emails from shared mailbox
        logger.info(f"Fetching emails from {Config.SHARED_MAILBOX}...")
        emails = ews_client.get_shared_mailbox_emails(Config.SHARED_MAILBOX, since=since)

        if emails:
            logger.info(f"Found {len(emails)} new email(s)")
        else:
            logger.info("No new emails found - skipping summary")
            logger.info("=" * 60)
            logger.info("Email Summarizer Agent Completed (No New Emails)")
            logger.info("=" * 60)
            return 0

        # Generate summary
        logger.info("Generating email summary...")
        summarizer = EmailSummarizer()
        summary = summarizer.summarize_emails(emails)

        # Format the summary
        subject = summarizer.get_subject_line(summary, Config.SHARED_MAILBOX)
        body_html = summarizer.format_summary_html(summary, Config.SHARED_MAILBOX)

        logger.info(f"Summary subject: {subject}")

        if args.dry_run:
            logger.info("DRY RUN - Not sending email")
            logger.info("-" * 40)
            logger.info("Summary Preview:")
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
            logger.info(f"Sending summary to {len(to_recipients)} recipient(s)...")
            ews_client.send_email(
                to_recipients=to_recipients,
                subject=subject,
                body_html=body_html,
                cc_recipients=Config.SUMMARY_CC if Config.SUMMARY_CC else None,
                bcc_recipients=Config.SUMMARY_BCC if Config.SUMMARY_BCC else None
            )
            logger.info("Summary email sent successfully!")

            # Update state with current time for next incremental run
            state.set_last_run()

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
