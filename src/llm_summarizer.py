"""
LLM-based email summarization using Azure OpenAI.
Generates intelligent, focused summaries of email content.
"""

import logging
import json
import httpx
from typing import Optional

from .config import Config
from .ews_client import Email

logger = logging.getLogger(__name__)


class LLMSummarizerError(Exception):
    """Raised when LLM summarization fails."""
    pass


class LLMSummarizer:
    """
    Uses Azure OpenAI to generate intelligent email summaries.
    """

    def __init__(self):
        """Initialize the LLM summarizer."""
        self._endpoint = Config.OPENAI_ENDPOINT
        self._api_key = Config.OPENAI_API_KEY

        if not self._endpoint or not self._api_key:
            raise LLMSummarizerError(
                "Azure OpenAI configuration missing. "
                "Set CHATGPT_ENDPOINT and AZURE_OPENAI_API_KEY in .env"
            )

    def _call_llm(self, prompt: str, system_prompt: str) -> str:
        """
        Call the Azure OpenAI API.

        Args:
            prompt: The user prompt
            system_prompt: The system instructions

        Returns:
            str: The LLM response text
        """
        headers = {
            "Content-Type": "application/json",
            "api-key": self._api_key
        }

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 2000
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    self._endpoint,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                result = response.json()
                return result["choices"][0]["message"]["content"]

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API error: {e.response.status_code} - {e.response.text}")
            raise LLMSummarizerError(f"LLM API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise LLMSummarizerError(f"LLM call failed: {e}")

    def summarize_email(self, email: Email) -> str:
        """
        Generate an intelligent summary of a single email.

        Args:
            email: The email to summarize

        Returns:
            str: A focused summary of the email (plain text, 2-3 sentences)
        """
        system_prompt = """You are an expert email summarizer. Extract the key information and present it concisely.

Focus on:
- The main purpose or request
- Any action items or deadlines
- Key decisions or information

Rules:
- Write in plain text only, NO markdown formatting
- Keep to 2-3 sentences maximum
- Be direct and factual
- Do not use bullet points or headers"""

        user_prompt = f"""Summarize this email in 2-3 plain text sentences:

From: {email.sender_name} <{email.sender_email}>
Subject: {email.subject}

Content:
{email.body_content[:2000]}"""

        try:
            return self._call_llm(user_prompt, system_prompt)
        except LLMSummarizerError:
            logger.warning(f"LLM summary failed for email: {email.subject}, using preview")
            return email.body_preview or "(No content)"

    def generate_daily_digest(self, emails: list[Email]) -> dict:
        """
        Generate a structured executive summary of all emails for the day.

        Args:
            emails: List of emails to summarize

        Returns:
            dict: Structured digest with urgent items, action items, and summary
        """
        if not emails:
            return {
                "summary": "No emails received today.",
                "urgent_items": [],
                "action_items": [],
                "themes": []
            }

        # Build context of all emails
        email_summaries = []
        for i, email in enumerate(emails, 1):
            email_summaries.append(
                f"Email {i}:\n"
                f"From: {email.sender_name} ({email.sender_email})\n"
                f"Subject: {email.subject}\n"
                f"Time: {email.received_time_local}\n"
                f"Content: {email.body_content[:800]}"
            )

        emails_context = "\n\n---\n\n".join(email_summaries)

        system_prompt = """You are an executive assistant creating a daily email digest.

Analyze the emails and return a JSON object with this exact structure:
{
    "summary": "A 2-3 sentence overview of today's emails",
    "urgent_items": ["item 1", "item 2"],
    "action_items": ["action 1", "action 2"],
    "themes": ["theme 1", "theme 2"]
}

Rules:
- summary: Brief overview, plain text, no formatting
- urgent_items: List of time-sensitive or high-priority matters (can be empty)
- action_items: List of things that need to be done (can be empty)
- themes: Main topics or recurring subjects (can be empty)
- Keep each item concise (one sentence max)
- Return ONLY valid JSON, no markdown or other text"""

        user_prompt = f"""Analyze these {len(emails)} emails and create an executive digest:

{emails_context}

Return only the JSON object."""

        try:
            response = self._call_llm(user_prompt, system_prompt)

            # Clean up response - remove markdown code blocks if present
            if "```" in response:
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            return json.loads(response.strip())
        except (json.JSONDecodeError, LLMSummarizerError) as e:
            logger.error(f"Failed to generate daily digest: {e}")
            return {
                "summary": "Unable to generate AI summary.",
                "urgent_items": [],
                "action_items": [],
                "themes": []
            }

    def categorize_emails(self, emails: list[Email]) -> dict[str, list[int]]:
        """
        Use LLM to intelligently categorize emails.

        Args:
            emails: List of emails to categorize

        Returns:
            dict: Categories mapped to email indices
        """
        if not emails:
            return {}

        # Build email list for categorization
        email_list = []
        for i, email in enumerate(emails, 1):
            email_list.append(
                f"{i}. From: {email.sender_email} | Subject: {email.subject}"
            )

        emails_text = "\n".join(email_list)

        system_prompt = """You categorize emails into meaningful groups.

Categories to use:
- Action Required: Emails needing a response or action
- FYI/Informational: Updates, newsletters, notifications
- Meetings: Calendar invites, meeting-related
- Urgent: Time-sensitive or high priority items
- Other: Everything else

Return ONLY a JSON object mapping category names to arrays of email numbers.
Example: {"Action Required": [1, 3], "FYI/Informational": [2, 4, 5]}
Do not include categories with empty arrays."""

        user_prompt = f"""Categorize these emails by their numbers:

{emails_text}

Return only the JSON object with categories and email numbers."""

        try:
            response = self._call_llm(user_prompt, system_prompt)
            # Parse JSON from response
            if "```" in response:
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response.strip())
        except (json.JSONDecodeError, LLMSummarizerError) as e:
            logger.warning(f"Email categorization failed: {e}")
            return {}
