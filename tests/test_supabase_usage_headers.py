import unittest
import json
from io import BytesIO
from unittest.mock import patch

from routes import free_usage_gate as gate


class UsageKeyHeaderTests(unittest.TestCase):
    def test_opaque_secret_is_only_sent_as_api_key(self):
        with patch.object(gate, "SUPABASE_SECRET", "sb_secret_example"):
            headers = gate._supabase_headers()
        self.assertEqual(headers["apikey"], "sb_secret_example")
        self.assertNotIn("Authorization", headers)

    def test_legacy_service_role_jwt_remains_supported(self):
        with patch.object(gate, "SUPABASE_SECRET", "legacy-jwt"):
            headers = gate._supabase_headers()
        self.assertEqual(headers["apikey"], "legacy-jwt")
        self.assertEqual(headers["Authorization"], "Bearer legacy-jwt")

    def test_claim_does_not_forward_spoofable_location_headers(self):
        class Response(BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_):
                self.close()

        observed = []

        def urlopen(req, timeout):
            observed.append(json.loads(req.data))
            return Response(b'[{"allowed":true,"used_today":1}]')

        with patch.object(gate, "SUPABASE_SECRET", "sb_secret_example"), \
                patch.object(gate.urlrequest, "urlopen", side_effect=urlopen):
            allowed, used = gate._supabase_claim(object(), "a" * 32)
        self.assertEqual((allowed, used), (True, 1))
        self.assertEqual(observed, [{"p_visitor_hash": "a" * 32, "p_limit": gate.DAILY_FREE_BOARD_LIMIT}])


if __name__ == "__main__":
    unittest.main()
