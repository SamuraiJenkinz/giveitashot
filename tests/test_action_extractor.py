"""
Tests for AI-based admin action extraction from Message Center updates.
Uses mocked httpx calls to avoid real API requests.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, Mock
import httpx
import json

from src.action_extractor import (
    ActionExtractor,
    AdminAction,
    ActionExtraction
)
from src.extractor import MajorUpdateFields, UrgencyTier


# ============================================
# Test Pydantic Models
# ============================================

class TestPydanticModels:
    """Test Pydantic model validation."""

    def test_admin_action_valid(self):
        """Create AdminAction with valid data."""
        action = AdminAction(action="Update auth settings")
        assert action.action == "Update auth settings"
        assert action.details is None
        assert action.role is None

    def test_admin_action_with_role(self):
        """Create AdminAction with role specified."""
        action = AdminAction(
            action="Enable MFA",
            details="For all admin accounts",
            role="Global Admin"
        )
        assert action.action == "Enable MFA"
        assert action.details == "For all admin accounts"
        assert action.role == "Global Admin"

    def test_admin_action_max_length(self):
        """Action field should reject strings longer than 50 chars."""
        long_action = "A" * 51
        with pytest.raises(Exception):  # Pydantic ValidationError
            AdminAction(action=long_action)

    def test_action_extraction_valid(self):
        """Create ActionExtraction with valid data."""
        extraction = ActionExtraction(
            actions=[
                AdminAction(action="Update settings"),
                AdminAction(action="Review policy")
            ],
            confidence="HIGH"
        )
        assert len(extraction.actions) == 2
        assert extraction.confidence == "HIGH"

    def test_action_extraction_invalid_confidence(self):
        """Confidence should reject values not matching HIGH/MEDIUM/LOW."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            ActionExtraction(
                actions=[AdminAction(action="Test")],
                confidence="INVALID"
            )


# ============================================
# Test ActionExtractor.extract_actions
# ============================================

class TestExtractActions:
    """Test single action extraction."""

    @pytest.fixture
    def sample_update(self):
        """Create a sample MajorUpdateFields for testing."""
        return MajorUpdateFields(
            mc_id="MC123456",
            action_required_date=datetime(2026, 3, 15),
            affected_services=["Exchange Online"],
            categories=["MAJOR UPDATE"],
            published_date=datetime(2026, 2, 1),
            last_updated_date=datetime(2026, 2, 1),
            body_preview="Important: Update Exchange authentication settings by March 15, 2026.",
            urgency=UrgencyTier.HIGH,
            is_updated=False,
            subject="[MC123456] Exchange Authentication Update Required"
        )

    @pytest.fixture
    def mock_success_response(self):
        """Create a mock successful Azure OpenAI response."""
        response_data = {
            "actions": [
                {
                    "action": "Update auth settings",
                    "details": "Exchange Online authentication",
                    "role": "Exchange Admin"
                }
            ],
            "confidence": "HIGH"
        }
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(response_data)
                    }
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        return mock_response

    def test_extract_actions_success(self, sample_update, mock_success_response):
        """Extract actions successfully with valid response."""
        with patch('src.action_extractor.Config') as mock_config:
            mock_config.OPENAI_ENDPOINT = 'https://test.openai.azure.com/endpoint'
            mock_config.OPENAI_API_KEY = 'test-key'

            extractor = ActionExtractor()

            with patch('httpx.Client') as mock_client_class:
                mock_client = Mock()
                mock_client.__enter__ = Mock(return_value=mock_client)
                mock_client.__exit__ = Mock(return_value=False)
                mock_client.post = Mock(return_value=mock_success_response)
                mock_client_class.return_value = mock_client

                result = extractor.extract_actions(sample_update)

                assert result is not None
                assert isinstance(result, ActionExtraction)
                assert len(result.actions) == 1
                assert result.actions[0].action == "Update auth settings"
                assert result.confidence == "HIGH"

    def test_extract_actions_timeout(self, sample_update):
        """Return None when LLM API times out."""
        with patch('src.action_extractor.Config') as mock_config:
            mock_config.OPENAI_ENDPOINT = 'https://test.openai.azure.com/endpoint'
            mock_config.OPENAI_API_KEY = 'test-key'

            extractor = ActionExtractor()

            with patch('httpx.Client') as mock_client_class:
                mock_client = Mock()
                mock_client.__enter__ = Mock(return_value=mock_client)
                mock_client.__exit__ = Mock(return_value=False)
                mock_client.post = Mock(side_effect=httpx.TimeoutException("Timeout"))
                mock_client_class.return_value = mock_client

                result = extractor.extract_actions(sample_update)

                assert result is None

    def test_extract_actions_http_error(self, sample_update):
        """Return None when LLM API returns HTTP error."""
        with patch('src.action_extractor.Config') as mock_config:
            mock_config.OPENAI_ENDPOINT = 'https://test.openai.azure.com/endpoint'
            mock_config.OPENAI_API_KEY = 'test-key'

            extractor = ActionExtractor()

            with patch('httpx.Client') as mock_client_class:
                mock_client = Mock()
                mock_client.__enter__ = Mock(return_value=mock_client)
                mock_client.__exit__ = Mock(return_value=False)

                mock_response = Mock()
                mock_response.status_code = 400
                mock_response.text = "Bad Request"

                error = httpx.HTTPStatusError(
                    "400 Bad Request",
                    request=Mock(),
                    response=mock_response
                )
                mock_client.post = Mock(side_effect=error)
                mock_client_class.return_value = mock_client

                result = extractor.extract_actions(sample_update)

                assert result is None

    def test_extract_actions_invalid_json(self, sample_update):
        """Return None when LLM response has invalid JSON."""
        with patch('src.action_extractor.Config') as mock_config:
            mock_config.OPENAI_ENDPOINT = 'https://test.openai.azure.com/endpoint'
            mock_config.OPENAI_API_KEY = 'test-key'

            extractor = ActionExtractor()

            with patch('httpx.Client') as mock_client_class:
                mock_client = Mock()
                mock_client.__enter__ = Mock(return_value=mock_client)
                mock_client.__exit__ = Mock(return_value=False)

                mock_response = Mock()
                mock_response.json.return_value = {
                    "choices": [
                        {
                            "message": {
                                "content": "not valid json"
                            }
                        }
                    ]
                }
                mock_response.raise_for_status = Mock()
                mock_client.post = Mock(return_value=mock_response)
                mock_client_class.return_value = mock_client

                result = extractor.extract_actions(sample_update)

                assert result is None

    def test_extract_actions_empty_body(self, sample_update):
        """Extract actions from update with empty body preview."""
        sample_update.body_preview = ""

        with patch('src.action_extractor.Config') as mock_config:
            mock_config.OPENAI_ENDPOINT = 'https://test.openai.azure.com/endpoint'
            mock_config.OPENAI_API_KEY = 'test-key'

            extractor = ActionExtractor()

            with patch('httpx.Client') as mock_client_class:
                mock_client = Mock()
                mock_client.__enter__ = Mock(return_value=mock_client)
                mock_client.__exit__ = Mock(return_value=False)

                # Should still make API call with empty body
                response_data = {
                    "actions": [],
                    "confidence": "LOW"
                }
                mock_response = Mock()
                mock_response.json.return_value = {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(response_data)
                            }
                        }
                    ]
                }
                mock_response.raise_for_status = Mock()
                mock_client.post = Mock(return_value=mock_response)
                mock_client_class.return_value = mock_client

                result = extractor.extract_actions(sample_update)

                assert result is not None
                assert len(result.actions) == 0
                assert result.confidence == "LOW"

    def test_extract_actions_unavailable(self, sample_update):
        """Return None immediately when Azure OpenAI not configured."""
        with patch('src.action_extractor.Config') as mock_config:
            mock_config.OPENAI_ENDPOINT = ''
            mock_config.OPENAI_API_KEY = ''

            extractor = ActionExtractor()

            assert extractor.available is False

            # Should not make API call
            with patch('httpx.Client') as mock_client_class:
                result = extractor.extract_actions(sample_update)

                assert result is None
                # Verify no API call was made
                mock_client_class.assert_not_called()

    def test_extract_actions_prompt_contains_mc_id(self, sample_update, mock_success_response):
        """Verify user prompt includes MC ID and subject."""
        with patch('src.action_extractor.Config') as mock_config:
            mock_config.OPENAI_ENDPOINT = 'https://test.openai.azure.com/endpoint'
            mock_config.OPENAI_API_KEY = 'test-key'

            extractor = ActionExtractor()

            with patch('httpx.Client') as mock_client_class:
                mock_client = Mock()
                mock_client.__enter__ = Mock(return_value=mock_client)
                mock_client.__exit__ = Mock(return_value=False)
                mock_client.post = Mock(return_value=mock_success_response)
                mock_client_class.return_value = mock_client

                extractor.extract_actions(sample_update)

                # Verify post was called
                assert mock_client.post.called

                # Get the payload from the call
                call_args = mock_client.post.call_args
                payload = call_args.kwargs['json']

                # Verify user prompt contains MC ID and subject
                user_message = payload['messages'][1]['content']
                assert "MC123456" in user_message
                assert "Exchange Authentication Update Required" in user_message

    def test_extract_actions_uses_structured_output(self, sample_update, mock_success_response):
        """Verify payload uses json_schema with strict=True."""
        with patch('src.action_extractor.Config') as mock_config:
            mock_config.OPENAI_ENDPOINT = 'https://test.openai.azure.com/endpoint'
            mock_config.OPENAI_API_KEY = 'test-key'

            extractor = ActionExtractor()

            with patch('httpx.Client') as mock_client_class:
                mock_client = Mock()
                mock_client.__enter__ = Mock(return_value=mock_client)
                mock_client.__exit__ = Mock(return_value=False)
                mock_client.post = Mock(return_value=mock_success_response)
                mock_client_class.return_value = mock_client

                extractor.extract_actions(sample_update)

                # Get the payload
                call_args = mock_client.post.call_args
                payload = call_args.kwargs['json']

                # Verify structured output format
                assert 'response_format' in payload
                assert payload['response_format']['type'] == 'json_schema'
                assert 'json_schema' in payload['response_format']
                assert payload['response_format']['json_schema']['strict'] is True


# ============================================
# Test ActionExtractor.extract_actions_batch
# ============================================

class TestExtractActionsBatch:
    """Test batch action extraction."""

    @pytest.fixture
    def sample_updates(self):
        """Create multiple sample updates."""
        return [
            MajorUpdateFields(
                mc_id="MC111111",
                action_required_date=datetime(2026, 3, 15),
                affected_services=["Exchange Online"],
                categories=["MAJOR UPDATE"],
                published_date=datetime(2026, 2, 1),
                last_updated_date=datetime(2026, 2, 1),
                body_preview="Update required.",
                urgency=UrgencyTier.HIGH,
                is_updated=False,
                subject="Update 1"
            ),
            MajorUpdateFields(
                mc_id="MC222222",
                action_required_date=datetime(2026, 4, 1),
                affected_services=["Teams"],
                categories=["ADMIN IMPACT"],
                published_date=datetime(2026, 2, 1),
                last_updated_date=datetime(2026, 2, 1),
                body_preview="Teams configuration change.",
                urgency=UrgencyTier.NORMAL,
                is_updated=False,
                subject="Update 2"
            )
        ]

    def test_batch_all_succeed(self, sample_updates):
        """Extract actions from batch where all succeed."""
        with patch('src.action_extractor.Config') as mock_config:
            mock_config.OPENAI_ENDPOINT = 'https://test.openai.azure.com/endpoint'
            mock_config.OPENAI_API_KEY = 'test-key'

            extractor = ActionExtractor()

            def mock_extract(update):
                """Mock successful extraction."""
                return ActionExtraction(
                    actions=[AdminAction(action=f"Action for {update.mc_id}")],
                    confidence="HIGH"
                )

            with patch.object(extractor, 'extract_actions', side_effect=mock_extract):
                results = extractor.extract_actions_batch(sample_updates)

                assert len(results) == 2
                assert "MC111111" in results
                assert "MC222222" in results
                assert results["MC111111"] is not None
                assert results["MC222222"] is not None

    def test_batch_partial_failure(self, sample_updates):
        """Extract actions from batch where one fails."""
        with patch('src.action_extractor.Config') as mock_config:
            mock_config.OPENAI_ENDPOINT = 'https://test.openai.azure.com/endpoint'
            mock_config.OPENAI_API_KEY = 'test-key'

            extractor = ActionExtractor()

            def mock_extract(update):
                """Mock mixed success/failure."""
                if update.mc_id == "MC111111":
                    return ActionExtraction(
                        actions=[AdminAction(action="Success")],
                        confidence="HIGH"
                    )
                else:
                    return None

            with patch.object(extractor, 'extract_actions', side_effect=mock_extract):
                results = extractor.extract_actions_batch(sample_updates)

                assert len(results) == 2
                assert results["MC111111"] is not None
                assert results["MC222222"] is None

    def test_batch_empty_list(self):
        """Extract actions from empty batch."""
        with patch('src.action_extractor.Config') as mock_config:
            mock_config.OPENAI_ENDPOINT = 'https://test.openai.azure.com/endpoint'
            mock_config.OPENAI_API_KEY = 'test-key'

            extractor = ActionExtractor()

            results = extractor.extract_actions_batch([])

            assert len(results) == 0
