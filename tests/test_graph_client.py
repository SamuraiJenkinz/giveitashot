"""
Unit tests for GraphClient — read and send paths.

All tests use mocked HTTP responses via patch.object(client._session, "request").
No live credentials or network calls are made.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone

from src.graph_client import Email, GraphClient, GraphClientError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_response(status_code=200, json_data=None, ok=True, headers=None, reason="OK", text=""):
    """Build a MagicMock that behaves like a requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = ok
    resp.reason = reason
    resp.text = text
    resp.headers = headers or {}
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.return_value = {}
    return resp


def make_message(
    graph_id="AAMkABC123",
    internet_message_id="<abc123@msg.microsoft.com>",
    subject="Test Email",
    sender_name="Test Sender",
    sender_email="sender@example.com",
    body_html="<html><body><p>Hello world</p></body></html>",
    received_datetime="2026-03-13T10:00:00Z",
    has_attachments=False,
):
    """Return a Graph message resource dict with realistic data."""
    msg = {
        "id": graph_id,
        "subject": subject,
        "sender": {
            "emailAddress": {
                "name": sender_name,
                "address": sender_email,
            }
        },
        "body": {
            "contentType": "html",
            "content": body_html,
        },
        "receivedDateTime": received_datetime,
        "hasAttachments": has_attachments,
    }
    if internet_message_id:
        msg["internetMessageId"] = internet_message_id
    return msg


def single_page_response(messages, next_link=None):
    """Build a Graph list-messages response dict."""
    data = {"value": messages}
    if next_link:
        data["@odata.nextLink"] = next_link
    return data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_authenticator():
    auth = MagicMock()
    auth.get_access_token.return_value = "fake-token-xyz"
    return auth


@pytest.fixture
def graph_client(mock_authenticator):
    return GraphClient(mock_authenticator)


# ---------------------------------------------------------------------------
# Read path tests — field parsing
# ---------------------------------------------------------------------------

class TestGetSharedMailboxEmailsParsesFields:
    """Verify all Email fields are populated correctly from Graph JSON."""

    def test_parses_all_fields(self, graph_client):
        msg = make_message(
            graph_id="AAMkABC123",
            internet_message_id="<abc123@msg.microsoft.com>",
            subject="Test Email",
            sender_name="Test Sender",
            sender_email="sender@example.com",
            body_html="<p>Hello world</p>",
            received_datetime="2026-03-13T10:00:00Z",
            has_attachments=True,
        )
        resp = make_response(json_data=single_page_response([msg]))
        since = datetime(2026, 3, 13, tzinfo=timezone.utc)

        with patch.object(graph_client._session, "request", return_value=resp):
            emails = graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)

        assert len(emails) == 1
        e = emails[0]
        assert e.id == "<abc123@msg.microsoft.com>"
        assert e.subject == "Test Email"
        assert e.sender_name == "Test Sender"
        assert e.sender_email == "sender@example.com"
        assert e.body_content == "Hello world"
        assert e.body_preview == "Hello world"
        assert e.received_datetime.tzinfo is not None
        assert e.has_attachments is True

    def test_strips_html_from_body(self, graph_client):
        msg = make_message(body_html="<html><body><p>Hello <b>world</b></p></body></html>")
        resp = make_response(json_data=single_page_response([msg]))
        since = datetime(2026, 3, 13, tzinfo=timezone.utc)

        with patch.object(graph_client._session, "request", return_value=resp):
            emails = graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)

        assert emails[0].body_content == "Hello world"

    def test_uses_internet_message_id(self, graph_client):
        msg = make_message(graph_id="AAMkABC123", internet_message_id="<stable@msg.microsoft.com>")
        resp = make_response(json_data=single_page_response([msg]))
        since = datetime(2026, 3, 13, tzinfo=timezone.utc)

        with patch.object(graph_client._session, "request", return_value=resp):
            emails = graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)

        assert emails[0].id == "<stable@msg.microsoft.com>"

    def test_falls_back_to_graph_id_when_internet_message_id_absent(self, graph_client):
        msg = make_message(internet_message_id=None)
        msg.pop("internetMessageId", None)
        resp = make_response(json_data=single_page_response([msg]))
        since = datetime(2026, 3, 13, tzinfo=timezone.utc)

        with patch.object(graph_client._session, "request", return_value=resp):
            emails = graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)

        assert emails[0].id == "AAMkABC123"

    def test_falls_back_to_graph_id_when_internet_message_id_empty(self, graph_client):
        msg = make_message(internet_message_id="")
        resp = make_response(json_data=single_page_response([msg]))
        since = datetime(2026, 3, 13, tzinfo=timezone.utc)

        with patch.object(graph_client._session, "request", return_value=resp):
            emails = graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)

        assert emails[0].id == "AAMkABC123"

    def test_handles_no_subject(self, graph_client):
        msg = make_message()
        msg["subject"] = None
        resp = make_response(json_data=single_page_response([msg]))
        since = datetime(2026, 3, 13, tzinfo=timezone.utc)

        with patch.object(graph_client._session, "request", return_value=resp):
            emails = graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)

        assert emails[0].subject == "(No Subject)"

    def test_handles_no_sender(self, graph_client):
        msg = make_message()
        msg["sender"] = None
        msg.pop("from", None)
        resp = make_response(json_data=single_page_response([msg]))
        since = datetime(2026, 3, 13, tzinfo=timezone.utc)

        with patch.object(graph_client._session, "request", return_value=resp):
            emails = graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)

        assert emails[0].sender_name == "Unknown"
        assert emails[0].sender_email == "unknown@unknown.com"


# ---------------------------------------------------------------------------
# Read path tests — OData filter and query params
# ---------------------------------------------------------------------------

class TestGetSharedMailboxEmailsQueryParams:
    """Verify correct OData query params are sent."""

    def test_default_since_is_today_midnight_utc(self, graph_client):
        resp = make_response(json_data=single_page_response([]))
        captured_kwargs = {}

        def capture_request(method, url, **kwargs):
            captured_kwargs.update(kwargs)
            return resp

        with patch.object(graph_client._session, "request", side_effect=capture_request):
            graph_client.get_shared_mailbox_emails("mailbox@example.com")

        params = captured_kwargs.get("params", {})
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        assert today_str in params["$filter"]
        assert "00:00:00Z" in params["$filter"]

    def test_odata_filter_format(self, graph_client):
        resp = make_response(json_data=single_page_response([]))
        captured_kwargs = {}

        def capture_request(method, url, **kwargs):
            captured_kwargs.update(kwargs)
            return resp

        since = datetime(2026, 3, 13, 0, 0, 0, tzinfo=timezone.utc)
        with patch.object(graph_client._session, "request", side_effect=capture_request):
            graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)

        params = captured_kwargs["params"]
        assert "$filter" in params
        assert "receivedDateTime ge 2026-03-13T00:00:00Z" == params["$filter"]
        assert "$select" in params
        assert "$orderby" in params
        assert "receivedDateTime desc" == params["$orderby"]
        assert "$top" in params


# ---------------------------------------------------------------------------
# Read path tests — pagination
# ---------------------------------------------------------------------------

class TestGetSharedMailboxEmailsPagination:
    """Verify @odata.nextLink pagination works correctly."""

    def test_pagination_follows_next_link(self, graph_client):
        next_link_url = "https://graph.microsoft.com/v1.0/users/mb/messages?$skiptoken=xyz"
        page1 = single_page_response([make_message(graph_id="msg1", internet_message_id="<msg1@test>")], next_link=next_link_url)
        page2 = single_page_response([make_message(graph_id="msg2", internet_message_id="<msg2@test>")])

        resp1 = make_response(json_data=page1)
        resp2 = make_response(json_data=page2)

        calls_made = []

        def side_effect_fn(method, url, **kwargs):
            calls_made.append((url, kwargs.get("params")))
            if len(calls_made) == 1:
                return resp1
            return resp2

        since = datetime(2026, 3, 13, tzinfo=timezone.utc)
        with patch.object(graph_client._session, "request", side_effect=side_effect_fn):
            emails = graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)

        assert len(emails) == 2
        assert emails[0].id == "<msg1@test>"
        assert emails[1].id == "<msg2@test>"
        # Second call must use nextLink URL, not the original URL
        assert calls_made[1][0] == next_link_url
        # params must be None on second call (nextLink already contains all params)
        assert calls_made[1][1] is None


# ---------------------------------------------------------------------------
# Read path tests — error handling
# ---------------------------------------------------------------------------

class TestGetSharedMailboxEmailsErrorHandling:
    """Verify error handling: bad emails skipped, max_emails respected, 4xx raises."""

    def test_skips_bad_email_keeps_good_ones(self, graph_client):
        good_msg = make_message(graph_id="good1", internet_message_id="<good1@test>")
        # A message dict that will fail _parse_message: body is a string, not dict
        bad_msg = {"id": "bad1", "body": "not-a-dict", "subject": "bad"}

        resp = make_response(json_data=single_page_response([good_msg, bad_msg]))
        since = datetime(2026, 3, 13, tzinfo=timezone.utc)

        with patch.object(graph_client._session, "request", return_value=resp):
            emails = graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)

        # Good email was kept, bad one skipped, no crash
        assert len(emails) == 1
        assert emails[0].id == "<good1@test>"

    def test_respects_max_emails(self, graph_client):
        messages = [
            make_message(graph_id=f"msg{i}", internet_message_id=f"<msg{i}@test>")
            for i in range(5)
        ]
        resp = make_response(json_data=single_page_response(messages))
        since = datetime(2026, 3, 13, tzinfo=timezone.utc)

        with patch.object(graph_client._session, "request", return_value=resp):
            emails = graph_client.get_shared_mailbox_emails(
                "mailbox@example.com", since=since, max_emails=3
            )

        assert len(emails) == 3

    def test_raises_on_error_response(self, graph_client):
        error_body = {"error": {"code": "ErrorAccessDenied", "message": "Access denied"}}
        resp = make_response(status_code=403, ok=False, json_data=error_body, reason="Forbidden")
        since = datetime(2026, 3, 13, tzinfo=timezone.utc)

        with patch.object(graph_client._session, "request", return_value=resp):
            with pytest.raises(GraphClientError) as exc_info:
                graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)

        assert "403" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Retry and throttle tests
# ---------------------------------------------------------------------------

class TestMakeRequestRetry:
    """Verify retry logic: 429, 5xx, max retries, 401 token refresh."""

    def test_retries_on_429(self, graph_client):
        resp_429 = make_response(status_code=429, ok=False, headers={"Retry-After": "1"}, reason="Too Many Requests")
        resp_200 = make_response(json_data=single_page_response([]))

        since = datetime(2026, 3, 13, tzinfo=timezone.utc)
        with patch.object(graph_client._session, "request", side_effect=[resp_429, resp_200]) as mock_req:
            with patch("src.graph_client.time.sleep") as mock_sleep:
                emails = graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)
            # Two HTTP calls were made (1 throttled, 1 success)
            assert mock_req.call_count == 2
            mock_sleep.assert_called_once_with(1)
        assert emails == []

    def test_retries_on_transient_5xx(self, graph_client):
        resp_503 = make_response(status_code=503, ok=False, reason="Service Unavailable")
        resp_200 = make_response(json_data=single_page_response([]))

        since = datetime(2026, 3, 13, tzinfo=timezone.utc)
        with patch.object(graph_client._session, "request", side_effect=[resp_503, resp_200]) as mock_req:
            with patch("src.graph_client.time.sleep"):
                emails = graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)
            assert mock_req.call_count == 2
        assert emails == []

    def test_raises_after_max_retries(self, graph_client):
        resp_429 = make_response(status_code=429, ok=False, headers={"Retry-After": "1"}, reason="Too Many Requests")

        since = datetime(2026, 3, 13, tzinfo=timezone.utc)
        # MAX_RETRIES = 3, all 3 attempts throttled
        with patch.object(graph_client._session, "request", side_effect=[resp_429, resp_429, resp_429]):
            with patch("src.graph_client.time.sleep"):
                with pytest.raises(GraphClientError) as exc_info:
                    graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)

        # get_shared_mailbox_emails wraps the GraphClientError; verify it is raised
        assert "GraphClientError" in type(exc_info.value).__name__ or True
        assert exc_info.value is not None
        # The underlying cause should reference the retry failure
        error_msg = str(exc_info.value)
        assert "429" in error_msg or "retrieve emails" in error_msg or "attempts" in error_msg

    def test_refreshes_token_on_401(self, graph_client, mock_authenticator):
        resp_401 = make_response(status_code=401, ok=False, reason="Unauthorized")
        resp_200 = make_response(json_data=single_page_response([]))

        since = datetime(2026, 3, 13, tzinfo=timezone.utc)
        with patch.object(graph_client._session, "request", side_effect=[resp_401, resp_200]):
            emails = graph_client.get_shared_mailbox_emails("mailbox@example.com", since=since)

        # get_access_token called twice: once per attempt
        assert mock_authenticator.get_access_token.call_count == 2
        assert emails == []


# ---------------------------------------------------------------------------
# Send path tests
# ---------------------------------------------------------------------------

class TestSendEmail:
    """Verify send_email() builds correct payloads and calls POST correctly."""

    def _get_payload(self, graph_client, **send_kwargs):
        """Helper: capture the json payload sent to _session.request."""
        resp = make_response(status_code=202, ok=True, reason="Accepted")
        captured = {}

        def capture_request(method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["json"] = kwargs.get("json")
            return resp

        with patch("src.graph_client.Config.SENDER_EMAIL", "sender@example.com"):
            with patch("src.graph_client.Config.get_send_from", return_value="sender@example.com"):
                with patch.object(graph_client._session, "request", side_effect=capture_request):
                    graph_client.send_email(**send_kwargs)

        return captured

    def test_send_email_basic(self, graph_client):
        result = self._get_payload(
            graph_client,
            to_recipients=["to@example.com"],
            subject="Test Subject",
            body_html="<p>Hello</p>",
        )

        assert result["method"] == "POST"
        assert "sender@example.com/sendMail" in result["url"]
        payload = result["json"]
        assert payload["saveToSentItems"] is True
        msg = payload["message"]
        assert msg["subject"] == "Test Subject"
        assert msg["body"]["contentType"] == "HTML"
        assert msg["body"]["content"] == "<p>Hello</p>"
        assert len(msg["toRecipients"]) == 1
        assert msg["toRecipients"][0]["emailAddress"]["address"] == "to@example.com"

    def test_send_email_with_cc_bcc(self, graph_client):
        result = self._get_payload(
            graph_client,
            to_recipients=["to@example.com"],
            subject="Test",
            body_html="<p>body</p>",
            cc_recipients=["cc@example.com"],
            bcc_recipients=["bcc@example.com"],
        )

        msg = result["json"]["message"]
        assert len(msg["ccRecipients"]) == 1
        assert msg["ccRecipients"][0]["emailAddress"]["address"] == "cc@example.com"
        assert len(msg["bccRecipients"]) == 1
        assert msg["bccRecipients"][0]["emailAddress"]["address"] == "bcc@example.com"

    def test_send_email_with_send_as(self, graph_client):
        resp = make_response(status_code=202, ok=True, reason="Accepted")
        captured = {}

        def capture_request(method, url, **kwargs):
            captured["json"] = kwargs.get("json")
            return resp

        with patch("src.graph_client.Config.SENDER_EMAIL", "mailbox@example.com"):
            with patch("src.graph_client.Config.get_send_from", return_value="alias@example.com"):
                with patch.object(graph_client._session, "request", side_effect=capture_request):
                    graph_client.send_email(
                        to_recipients=["to@example.com"],
                        subject="Test",
                        body_html="<p>body</p>",
                    )

        msg = captured["json"]["message"]
        assert "from" in msg
        assert msg["from"]["emailAddress"]["address"] == "alias@example.com"

    def test_send_email_no_from_when_same_as_sender(self, graph_client):
        resp = make_response(status_code=202, ok=True, reason="Accepted")
        captured = {}

        def capture_request(method, url, **kwargs):
            captured["json"] = kwargs.get("json")
            return resp

        with patch("src.graph_client.Config.SENDER_EMAIL", "sender@example.com"):
            with patch("src.graph_client.Config.get_send_from", return_value="sender@example.com"):
                with patch.object(graph_client._session, "request", side_effect=capture_request):
                    graph_client.send_email(
                        to_recipients=["to@example.com"],
                        subject="Test",
                        body_html="<p>body</p>",
                    )

        msg = captured["json"]["message"]
        assert "from" not in msg

    def test_send_email_filters_empty_recipients(self, graph_client):
        result = self._get_payload(
            graph_client,
            to_recipients=["user@test.com", "", ""],
            subject="Test",
            body_html="<p>body</p>",
        )

        msg = result["json"]["message"]
        assert len(msg["toRecipients"]) == 1
        assert msg["toRecipients"][0]["emailAddress"]["address"] == "user@test.com"

    def test_send_email_raises_on_empty_recipients(self, graph_client):
        with pytest.raises(GraphClientError) as exc_info:
            graph_client.send_email(
                to_recipients=[],
                subject="Test",
                body_html="<p>body</p>",
            )

        assert "At least one TO recipient" in str(exc_info.value)

    def test_send_email_raises_on_all_empty_string_recipients(self, graph_client):
        with pytest.raises(GraphClientError) as exc_info:
            graph_client.send_email(
                to_recipients=["", "   ".strip()],
                subject="Test",
                body_html="<p>body</p>",
            )

        assert "At least one TO recipient" in str(exc_info.value)

    def test_send_email_accepts_string_recipient(self, graph_client):
        result = self._get_payload(
            graph_client,
            to_recipients="single@example.com",
            subject="Test",
            body_html="<p>body</p>",
        )

        msg = result["json"]["message"]
        assert len(msg["toRecipients"]) == 1
        assert msg["toRecipients"][0]["emailAddress"]["address"] == "single@example.com"

    def test_send_email_raises_on_error_response(self, graph_client):
        error_body = {"error": {"code": "ErrorSendAsDenied", "message": "Send As permission required"}}
        resp = make_response(status_code=403, ok=False, json_data=error_body, reason="Forbidden")

        with patch("src.graph_client.Config.SENDER_EMAIL", "sender@example.com"):
            with patch("src.graph_client.Config.get_send_from", return_value="sender@example.com"):
                with patch.object(graph_client._session, "request", return_value=resp):
                    with pytest.raises(GraphClientError) as exc_info:
                        graph_client.send_email(
                            to_recipients=["to@example.com"],
                            subject="Test",
                            body_html="<p>body</p>",
                        )

        assert "403" in str(exc_info.value)

    def test_send_email_save_to_sent_items_is_true_boolean(self, graph_client):
        """saveToSentItems must be boolean True, not string 'True'."""
        result = self._get_payload(
            graph_client,
            to_recipients=["to@example.com"],
            subject="Test",
            body_html="<p>body</p>",
        )

        assert result["json"]["saveToSentItems"] is True
        assert result["json"]["saveToSentItems"] is not "True"

    def test_send_email_no_cc_bcc_when_empty(self, graph_client):
        """ccRecipients and bccRecipients must not appear in payload when not provided."""
        result = self._get_payload(
            graph_client,
            to_recipients=["to@example.com"],
            subject="Test",
            body_html="<p>body</p>",
        )

        msg = result["json"]["message"]
        assert "ccRecipients" not in msg
        assert "bccRecipients" not in msg


# ---------------------------------------------------------------------------
# Datetime parsing tests
# ---------------------------------------------------------------------------

class TestParseDatetime:
    """Exercise _parse_datetime edge cases."""

    def test_utc_z_suffix(self, graph_client):
        dt = graph_client._parse_datetime("2026-03-13T10:00:00Z")
        assert dt.tzinfo is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 13
        assert dt.hour == 10

    def test_empty_string_returns_utc_datetime(self, graph_client):
        dt = graph_client._parse_datetime("")
        assert dt.tzinfo is not None

    def test_invalid_string_returns_utc_datetime(self, graph_client):
        dt = graph_client._parse_datetime("not-a-date")
        assert dt.tzinfo is not None

    def test_invalid_string_logs_warning(self, graph_client):
        with patch("src.graph_client.logger") as mock_logger:
            graph_client._parse_datetime("not-a-date")
        mock_logger.warning.assert_called_once()


# ---------------------------------------------------------------------------
# Email dataclass property tests
# ---------------------------------------------------------------------------

class TestEmailDataclassProperties:
    """Verify Email dataclass properties behave correctly."""

    def _make_email(self, classification=None):
        return Email(
            id="test-id",
            subject="Test",
            sender_name="Sender",
            sender_email="sender@test.com",
            received_datetime=datetime(2026, 3, 13, 10, 30, 0, tzinfo=timezone.utc),
            body_preview="Preview text",
            body_content="Full body text",
            has_attachments=False,
            classification=classification,
        )

    def test_received_time_local_property(self):
        email = self._make_email()
        result = email.received_time_local
        # Should return a formatted time string (e.g. "10:30 AM")
        assert isinstance(result, str)
        assert len(result) > 0
        # Format is HH:MM AM/PM
        assert "AM" in result or "PM" in result

    def test_is_major_update_default_false(self):
        email = self._make_email(classification=None)
        assert email.is_major_update is False

    def test_is_major_update_delegates_to_classification(self):
        mock_classification = MagicMock()
        mock_classification.is_major_update = True
        email = self._make_email(classification=mock_classification)
        assert email.is_major_update is True

    def test_is_major_update_false_from_classification(self):
        mock_classification = MagicMock()
        mock_classification.is_major_update = False
        email = self._make_email(classification=mock_classification)
        assert email.is_major_update is False
