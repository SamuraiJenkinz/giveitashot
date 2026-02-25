"""
AI-based admin action extraction from Message Center major updates.
Uses Azure OpenAI structured outputs to extract actionable admin tasks.
"""

import logging
import httpx
from typing import Optional
from pydantic import BaseModel, Field
import pydantic

from .config import Config
from .extractor import MajorUpdateFields

logger = logging.getLogger(__name__)


class AdminAction(BaseModel):
    """A single admin action extracted from an update."""
    action: str = Field(
        ...,
        max_length=50,
        description="Short imperative: 'Update auth settings'"
    )
    details: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Additional context or details"
    )
    role: Optional[str] = Field(
        default=None,
        description="Target admin role e.g. 'Global Admin'"
    )


class ActionExtraction(BaseModel):
    """Collection of extracted actions with confidence."""
    actions: list[AdminAction] = Field(
        default_factory=list,
        max_length=5,
        description="List of 1-5 admin actions"
    )
    confidence: str = Field(
        ...,
        pattern="^(HIGH|MEDIUM|LOW)$",
        description="Extraction confidence level"
    )


class ActionExtractor:
    """
    Extracts structured admin actions from Message Center major updates.

    Uses Azure OpenAI structured outputs with Pydantic schema validation
    to extract 1-5 actionable admin tasks from email body text.

    Returns None on any failure (graceful degradation - send digest without actions).
    """

    def __init__(self):
        """Initialize the action extractor with Azure OpenAI configuration."""
        self._endpoint = Config.OPENAI_ENDPOINT
        self._api_key = Config.OPENAI_API_KEY

        if not self._endpoint or not self._api_key:
            logger.warning(
                "Azure OpenAI configuration incomplete for action extraction. "
                "Action extraction will be unavailable. "
                "Set CHATGPT_ENDPOINT and AZURE_OPENAI_API_KEY in .env"
            )
            self._available = False
        else:
            self._available = True

    @property
    def available(self) -> bool:
        """Check if action extraction is available (configuration present)."""
        return self._available

    def extract_actions(self, update: MajorUpdateFields) -> Optional[ActionExtraction]:
        """
        Extract admin actions from a single major update.

        Args:
            update: Major update fields to extract actions from.

        Returns:
            ActionExtraction with 1-5 actions and confidence, or None on any failure.
        """
        if not self._available:
            return None

        # Build system prompt with extraction rules
        system_prompt = """You are an IT admin assistant extracting actionable tasks from Microsoft 365 Message Center updates.

Extract 1-5 admin actions as short imperative commands (3-5 words each).

Rules:
- Prioritize the most important admin actions
- Use imperative verb form ("Update", "Review", "Enable", "Configure")
- Include role if task is role-specific (e.g. "Global Admin", "SharePoint Admin")
- Provide brief details if helpful for context
- Set confidence:
  * HIGH: Actions clearly and explicitly stated in the update
  * MEDIUM: Actions partially stated or require minor interpretation
  * LOW: Actions inferred from context or implications

Return structured JSON matching the ActionExtraction schema."""

        # Format action date for prompt
        action_date_str = (
            update.action_required_date.strftime("%B %d, %Y")
            if update.action_required_date
            else "None"
        )

        # Build user prompt with update content (truncate body to 1500 chars)
        body_truncated = update.body_preview[:1500] if len(update.body_preview) > 1500 else update.body_preview

        user_prompt = f"""Extract admin actions from this Message Center update:

MC ID: {update.mc_id or 'Unknown'}
Subject: {update.subject}
Action Required By: {action_date_str}

Body:
{body_truncated}

Return the ActionExtraction JSON with actions and confidence."""

        # Build request payload with structured output
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 500,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "ActionExtraction",
                    "strict": True,
                    "schema": ActionExtraction.model_json_schema()
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            "api-key": self._api_key
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
                content = result["choices"][0]["message"]["content"]

                # Validate with Pydantic
                return ActionExtraction.model_validate_json(content)

        except httpx.HTTPStatusError as e:
            logger.warning(
                f"Action extraction HTTP error for {update.mc_id}: "
                f"{e.response.status_code} - {e.response.text[:200]}"
            )
            return None
        except httpx.TimeoutException:
            logger.warning(f"Action extraction timeout for {update.mc_id}")
            return None
        except pydantic.ValidationError as e:
            logger.warning(
                f"Action extraction validation failed for {update.mc_id}: {e}"
            )
            return None
        except Exception as e:
            logger.warning(
                f"Action extraction failed for {update.mc_id}: {e}"
            )
            return None

    def extract_actions_batch(
        self,
        updates: list[MajorUpdateFields]
    ) -> dict[str, Optional[ActionExtraction]]:
        """
        Extract actions from multiple major updates.

        Args:
            updates: List of major update fields to process.

        Returns:
            Dictionary mapping mc_id (or generated key) to ActionExtraction or None.
        """
        results = {}

        for idx, update in enumerate(updates):
            # Use mc_id as key, or generate one for updates without MC ID
            key = update.mc_id if update.mc_id else f"unknown_{idx}"
            results[key] = self.extract_actions(update)

        # Log summary
        successes = sum(1 for v in results.values() if v is not None)
        logger.info(
            f"Action extraction batch complete: {successes}/{len(updates)} succeeded"
        )

        return results
