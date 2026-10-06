import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.requests import Request
import main
from routes import free_usage_gate as gate


def request(headers):
    return Request({"type": "http", "method": "GET", "scheme": "https", "path": "/free-usage",
                    "headers": [(k.encode(), v.encode()) for k, v in headers],
                    "client": ("10.0.0.7", 9000), "server": ("localhost", 8080)})


class OriginTests(unittest.TestCase):
    def test_direct_origin_is_rejected_before_upload_validation_or_claim(self):
        with patch.dict(os.environ, {"BOARD_SENSE_ORIGIN_KEY": "a" * 40}), \
                patch.object(main, "record_free_board_use", side_effect=AssertionError("claim")), TestClient(main.app) as client:
            self.assertEqual(client.post("/analyze", content=b"invalid form").status_code, 403)
            self.assertEqual(client.get("/free-usage").status_code, 403)
            self.assertEqual(client.get("/health").status_code, 200)
            # Correct proxy header reaches ordinary form validation.
            self.assertEqual(client.post("/analyze", content=b"invalid form", headers={"X-Scrap-Radar-Origin-Key": "a" * 40}).status_code, 422)

    def test_only_authenticated_proxy_can_supply_client_address(self):
        with patch.dict(os.environ, {"BOARD_SENSE_ORIGIN_KEY": "a" * 40, "RAILWAY_ENVIRONMENT_NAME": "production"}):
            untrusted = request([("x-real-ip", "1.1.1.1"), ("cf-connecting-ip", "8.8.8.8")])
            trusted = request([("x-real-ip", "1.1.1.1"), ("cf-connecting-ip", "8.8.8.8"), ("x-scrap-radar-origin-key", "a" * 40)])
            self.assertEqual(gate._client_ip(untrusted), "1.1.1.1")
            self.assertEqual(gate._client_ip(trusted), "8.8.8.8")

    def test_origin_check_remains_inactive_before_dns_cutover(self):
        with patch.dict(os.environ, {"BOARD_SENSE_ORIGIN_KEY": ""}), TestClient(main.app) as client:
            self.assertEqual(client.post("/analyze", content=b"invalid form").status_code, 422)

    def test_non_ascii_tester_header_is_denied_without_an_exception(self):
        with patch.object(gate, "BOARD_SENSE_TESTER_KEY", "a" * 40):
            self.assertFalse(gate._is_authorized_tester(request([("x-board-sense-tester-key", "é")])) )
