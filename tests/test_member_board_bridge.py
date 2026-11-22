"""Offline contract tests: disabled bridge never exposes paid analysis."""
import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from uuid import uuid4

from routes import member_board_bridge as bridge

TOKEN = "A" * 40
SECRET = "secret-" + "Z" * 48
ORIGIN = "https://scrapradar-backend-production.up.railway.app"
DAY = "2026-11-22"


class FakeResponse(io.BytesIO):
    status = 200


class FakeOpener:
    def __init__(self, data=None, status=200, error=None):
        self.calls = []
        self.data = data
        self.status = status
        self.error = error

    def open(self, req, timeout):
        self.calls.append((req, timeout))
        if self.error is not None:
            raise self.error
        response = FakeResponse(json.dumps(self.data).encode("utf-8"))
        response.status = self.status
        return response


class MemberBridgeTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "BOARD_SENSE_MEMBER_BRIDGE_ENABLED": "1",
            "SCRAP_RADAR_BOARD_SERVICE_KEY": SECRET,
            "SCRAP_RADAR_MEMBERSHIP_ORIGIN": ORIGIN,
        })
        self.env.start()
        self.case_id = str(uuid4())
        self.body = {
            "allowed": True, "case_id": self.case_id,
            "usage": {"used_today": 1, "remaining": 24, "limit": 25, "day_utc": DAY},
        }
        self.opener = FakeOpener(self.body)
        self.patch_opener = patch.object(bridge, "build_opener", return_value=self.opener)
        self.patch_opener.start()

    def tearDown(self):
        self.patch_opener.stop()
        self.env.stop()

    def reserve(self, header="Bearer " + TOKEN):
        return bridge.reserve_paid_case(header, self.case_id)

    def test_disabled_by_default_and_does_not_contact_network(self):
        with patch.dict(os.environ, {"BOARD_SENSE_MEMBER_BRIDGE_ENABLED": ""}):
            with self.assertRaises(bridge.MembershipBridgeDisabled):
                self.reserve()
        self.assertEqual(self.opener.calls, [])

    def test_success_is_server_to_server_with_no_customer_or_plan_assertions(self):
        result = self.reserve()
        self.assertEqual((result.limit, result.used_today, result.remaining), (25, 1, 24))
        self.assertEqual(result.case_id, self.case_id)
        self.assertEqual(len(self.opener.calls), 1)
        req, timeout = self.opener.calls[0]
        self.assertEqual(timeout, 6)
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.full_url, ORIGIN + bridge.RESERVATION_PATH)
        self.assertEqual(json.loads(req.data), {"case_id": self.case_id})
        self.assertEqual(req.get_header("Authorization"), "Bearer " + TOKEN)
        self.assertEqual(req.get_header("X-srf-board-service-key"), SECRET)
        self.assertEqual(req.get_header("Content-type"), "application/json")

    def test_missing_or_invalid_customer_token_denied_without_network(self):
        for header in (None, "", "Basic "+TOKEN, "Bearer ", "Bearer "+TOKEN+"\r\nForwarded: attacker"):
            with self.subTest(header=repr(header)):
                with self.assertRaises(bridge.MembershipBridgeDenied):
                    self.reserve(header)
        self.assertFalse(self.opener.calls)

    def test_fake_case_ids_denied_without_network(self):
        self.case_id = "client-chosen-case"
        with self.assertRaises(bridge.MembershipBridgeDenied):
            self.reserve()
        self.assertFalse(self.opener.calls)

    def test_missing_short_or_space_containing_service_key_fail_closed(self):
        for secret in ("", "short", "X" * 40 + "\n"):
            with patch.dict(os.environ, {"SCRAP_RADAR_BOARD_SERVICE_KEY": secret}):
                with self.assertRaises(bridge.MembershipBridgeUnavailable):
                    self.reserve()
        self.assertFalse(self.opener.calls)

    def test_arbitrary_http_or_redirect_destination_not_accepted(self):
        for origin in (
            "http://scrapradar-backend-production.up.railway.app",
            "https://scrapradar-backend-production.up.railway.app.evil.test",
            ORIGIN + ":443",
            ORIGIN + "/other",
            ORIGIN + "?redirect=evil",
            "https://attacker.example",
            "",
        ):
            with self.subTest(origin=origin), patch.dict(os.environ, {"SCRAP_RADAR_MEMBERSHIP_ORIGIN": origin}):
                with self.assertRaises(bridge.MembershipBridgeUnavailable):
                    self.reserve()
        self.assertFalse(self.opener.calls)

    def test_http_redirects_are_not_followed(self):
        handler = bridge._NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Moved", {}, "https://evil.test"))
        self.assertIsNone(handler.redirect_request(None, None, 307, "Moved", {}, "https://evil.test"))

    def test_provider_denials_never_fall_back_to_free_or_grant(self):
        for status in (401, 403, 429):
            self.opener.error = HTTPError(ORIGIN, status, "denied", {}, None)
            with self.subTest(status=status), self.assertRaises(bridge.MembershipBridgeDenied):
                self.reserve()

    def test_outage_or_redirect_never_falls_back_to_free_or_grant(self):
        for error in (URLError("offline"), TimeoutError("timeout"), HTTPError(ORIGIN, 302, "redirect", {}, None), HTTPError(ORIGIN, 500, "error", {}, None)):
            self.opener.error = error
            with self.subTest(error=type(error).__name__), self.assertRaises(bridge.MembershipBridgeUnavailable):
                self.reserve()

    def test_malformed_or_unverified_reply_never_grants_access(self):
        self.opener.error = None
        for payload in (
            None, [], {}, {"allowed": False}, {"allowed": "true"},
            {"allowed": True}, {"allowed": True, "case_id": "wrong", "usage": self.body["usage"]},
            {"allowed": True, "case_id": self.case_id, "usage": {"used_today": True, "remaining": 24, "limit": 25, "day_utc": DAY}},
            {"allowed": True, "case_id": self.case_id, "usage": {"used_today": 26, "remaining": -1, "limit": 25, "day_utc": DAY}},
            {"allowed": True, "case_id": self.case_id, "usage": {"used_today": 1, "remaining": 25, "limit": 25, "day_utc": DAY}},
            {"allowed": True, "case_id": self.case_id, "usage": {"used_today": 1, "remaining": 24, "limit": 24, "day_utc": DAY}},
            {"allowed": True, "case_id": self.case_id, "usage": {"used_today": 1, "remaining": 24, "limit": 25, "day_utc": "not-a-date"}},
        ):
            self.opener.data = payload
            with self.subTest(payload=payload), self.assertRaises(bridge.MembershipBridgeError):
                self.reserve()

    def test_non200_success_response_fails_closed(self):
        self.opener.status = 202
        with self.assertRaises(bridge.MembershipBridgeUnavailable):
            self.reserve()


if __name__ == "__main__":
    unittest.main()
