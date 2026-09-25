import os
import unittest
from unittest.mock import patch

from starlette.requests import Request

from routes import free_usage_gate as gate


def request(headers=(), client="10.0.0.7"):
    return Request({"type": "http", "method": "GET", "scheme": "http", "path": "/free-usage",
                    "headers": [(k.encode(), v.encode()) for k, v in headers],
                    "client": (client, 9000), "server": ("localhost", 8080)})


class FreeUsageGateSecurityTests(unittest.TestCase):
    def test_forwarded_list_cannot_change_visitor_on_railway(self):
        a = request([("x-real-ip", "8.8.8.8"), ("x-forwarded-for", "1.1.1.1")])
        b = request([("x-real-ip", "8.8.8.8"), ("x-forwarded-for", "9.9.9.9")])
        with patch.dict(os.environ, {"RAILWAY_ENVIRONMENT_NAME": "production"}):
            self.assertEqual(gate._client_ip(a), "8.8.8.8")
            self.assertEqual(gate._visitor_id(a), gate._visitor_id(b))

    def test_rejects_invalid_or_private_real_ip_and_untrusted_local_headers(self):
        with patch.dict(os.environ, {"RAILWAY_ENVIRONMENT_NAME": "production"}):
            for spoofed in ("127.0.0.1", "10.1.0.9", "8.8.8.8, 9.9.9.9", "invalid"):
                with self.subTest(spoofed=spoofed):
                    self.assertEqual(gate._client_ip(request([
                        ("x-real-ip", spoofed), ("x-forwarded-for", "1.1.1.1")])), "10.0.0.7")
        with patch.dict(os.environ, {"RAILWAY_ENVIRONMENT_NAME": ""}):
            self.assertEqual(gate._client_ip(request([("x-real-ip", "8.8.8.8")])), "10.0.0.7")

    def test_production_without_durable_store_blocks_check_and_claim(self):
        with patch.object(gate, "BOARD_SENSE_ENV", "production"), \
                patch.object(gate, "_supabase_ready", return_value=False), \
                patch.object(gate, "_local_check", side_effect=AssertionError("local fallback")), \
                patch.object(gate, "_local_claim", side_effect=AssertionError("local fallback")):
            checked = gate.check_free_board_allowance(request())
            claimed = gate.record_free_board_use(request(), "single_board")
        self.assertFalse(checked.allowed)
        self.assertFalse(claimed.allowed)
        self.assertEqual(checked.reason, "usage_backend_unavailable")
        self.assertEqual(claimed.reason, "usage_backend_unavailable")

    def test_development_retains_local_allowance(self):
        with patch.object(gate, "BOARD_SENSE_ENV", "development"), \
                patch.dict(os.environ, {"RAILWAY_ENVIRONMENT_NAME": ""}), \
                patch.object(gate, "_supabase_ready", return_value=False), \
                patch.object(gate, "_local_check", return_value=0):
            checked = gate.check_free_board_allowance(request())
        self.assertTrue(checked.allowed)

    def test_railway_production_cannot_fall_back_to_development(self):
        with patch.object(gate, "BOARD_SENSE_ENV", "development"), \
                patch.dict(os.environ, {"RAILWAY_ENVIRONMENT_NAME": "production"}), \
                patch.object(gate, "_supabase_ready", return_value=False), \
                patch.object(gate, "_local_check", side_effect=AssertionError("local fallback")):
            checked = gate.check_free_board_allowance(request())
        self.assertEqual(checked.reason, "usage_backend_unavailable")


if __name__ == "__main__":
    unittest.main()
