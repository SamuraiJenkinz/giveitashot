"""
Email classification for M365 Message Center major update detection.
Uses multi-signal weighted scoring to identify major update emails.
"""

import logging
import re
from dataclasses import dataclass

from .graph_client import Email

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result of email classification with confidence scoring."""
    is_major_update: bool
    confidence_score: float
    matched_signals: list[str]


class EmailClassifier:
    """
    Classifier for detecting M365 Message Center major update emails.

    Uses weighted multi-signal detection:
    - Sender domain pattern (40 points)
    - MC number in subject (30 points)
    - Major update keywords in body (30 points)

    Threshold: 70 points (requires at least 2 strong signals)
    """

    # Compiled regex patterns (compile once, reuse)
    SENDER_PATTERN = re.compile(r'@(email2\.microsoft|microsoft)\.com$', re.IGNORECASE)
    MC_NUMBER_PATTERN = re.compile(r'\bMC\d{5,7}\b')
    MAJOR_UPDATE_KEYWORDS = re.compile(
        r'\b(major update|retirement|admin impact|action required|breaking change|deprecat)',
        re.IGNORECASE
    )

    # Weights for signal scoring
    WEIGHTS = {
        "sender": 40,
        "subject_mc": 30,
        "body_keywords": 30
    }

    # Classification threshold
    THRESHOLD = 70

    def classify(self, email: Email) -> ClassificationResult:
        """
        Classify an email as major update or not.

        Args:
            email: Email to classify.

        Returns:
            ClassificationResult with classification decision, confidence score, and matched signals.
        """
        score = 0.0
        signals = []

        # Signal 1: Sender domain
        if self.SENDER_PATTERN.search(email.sender_email):
            score += self.WEIGHTS["sender"]
            signals.append("sender_domain")

        # Signal 2: MC number in subject
        if self.MC_NUMBER_PATTERN.search(email.subject):
            score += self.WEIGHTS["subject_mc"]
            signals.append("subject_mc_number")

        # Signal 3: Major update keywords in subject or body
        if (self.MAJOR_UPDATE_KEYWORDS.search(email.subject) or
            self.MAJOR_UPDATE_KEYWORDS.search(email.body_content)):
            score += self.WEIGHTS["body_keywords"]
            signals.append("body_keywords")

        # Determine classification based on threshold
        is_major = score >= self.THRESHOLD

        # Log classification decision
        email_id_short = email.id[:20] if len(email.id) > 20 else email.id
        logger.info(
            f"Classified email {email_id_short}...: "
            f"score={score}, signals={signals}, is_major={is_major}"
        )

        return ClassificationResult(
            is_major_update=is_major,
            confidence_score=score,
            matched_signals=signals
        )

    def classify_batch(self, emails: list[Email]) -> tuple[list[Email], list[Email]]:
        """
        Classify a batch of emails and split into regular vs major updates.

        Args:
            emails: List of emails to classify.

        Returns:
            Tuple of (regular_emails, major_update_emails).
        """
        regular_emails = []
        major_update_emails = []

        for email in emails:
            result = self.classify(email)
            # Attach classification result to email
            email.classification = result
            if result.is_major_update:
                major_update_emails.append(email)
            else:
                regular_emails.append(email)

        # Log summary
        logger.info(
            f"Classification complete: {len(regular_emails)} regular, "
            f"{len(major_update_emails)} major updates"
        )

        return (regular_emails, major_update_emails)
