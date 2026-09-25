import io
import json
import unittest
from unittest.mock import patch

from routes import market_bridge


class FakeResponse:
    headers = {"Content-Type": "application/json; charset=utf-8"}

    def __init__(self, payload):
        self.stream = io.BytesIO(payload)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stream.close()

    def read(self, limit):
        return self.stream.read(limit)


class MarketBridgeSecurityTests(unittest.TestCase):
    def fetch(self, payload):
        response = FakeResponse(payload)
        with patch.dict("os.environ", {"SCRAP_RADAR_API_URL": "https://market.example"}), \
                patch.object(market_bridge, "build_opener") as opener:
            opener.return_value.open.return_value = response
            result = market_bridge.fetch_scrap_radar_market()
            opener.return_value.open.assert_called_once()
            self.assertEqual(opener.return_value.open.call_args.args[0].full_url,
                             "https://market.example/prices")
            return result

    def test_accepts_the_existing_market_shape_and_preserves_dates(self):
        payload = {"status": "stale", "source": "Reference market",
                   "metals": {"copper": {"price": 3.1, "source_price_date": "2026-09-18", "stale": True}},
                   "scrap_grades": {}, "materials": [], "checked_at": "2026-09-24T12:00:00Z"}
        result = self.fetch(json.dumps(payload).encode())
        self.assertEqual(result["status"], "stale")
        self.assertTrue(result["metals"]["copper"]["stale"])
        self.assertEqual(result["checked_at"], payload["checked_at"])

    def test_rejects_nonobject_payload_and_bad_collection_shapes(self):
        for payload in (b"[]", b'{"status":"live","metals":[],"materials":[]}',
                        b'{"status":"live","metals":{},"materials":{}}',
                        b'{"status":"live","metals":{},"materials":[{"materials":{}}]}',
                        b'{"status":"live","metals":{},"materials":[{"materials":[null]}]}',
                        b'{"status":[],"metals":{}}'):
            with self.subTest(payload=payload):
                self.assertEqual(self.fetch(payload)["status"], "unavailable")

    def test_rejects_oversize_and_nonfinite_prices(self):
        self.assertEqual(self.fetch(b" " * (market_bridge.MAX_RESPONSE_BYTES + 1))["status"],
                         "unavailable")
        nonfinite = b'{"status":"live","metals":{"copper":{"price":1e309}}}'
        self.assertEqual(self.fetch(nonfinite)["status"], "unavailable")
        invalid_quote = b'{"status":"live","metals":{"copper":{"available":true,"price":"3.4"}}}'
        self.assertEqual(self.fetch(invalid_quote)["status"], "unavailable")
        boolean_quote = b'{"status":"live","metals":{"copper":{"available":true,"price":true}}}'
        self.assertEqual(self.fetch(boolean_quote)["status"], "unavailable")

    def test_redirect_handler_blocks_upstream_redirects(self):
        handler = market_bridge._NoRedirects()
        self.assertIsNone(handler.redirect_request(None, None, 302, "redirect", {},
                                                   "https://elsewhere.example/prices"))


if __name__ == "__main__":
    unittest.main()
