"""Regression: exact duplicate images are rejected before public quota claim."""
import asyncio
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import UploadFile
from PIL import Image

from routes.photo_overlap_diagnostics import exact_duplicate_photo_pairs


def photo_bytes(color=(60, 80, 100)):
    with io.BytesIO() as output:
        Image.new("RGB", (120, 100), color=color).save(output, format="PNG")
        return output.getvalue()


class PreclaimDuplicateTests(unittest.TestCase):
    def test_nonadjacent_duplicates_found_without_exposing_content(self):
        a = photo_bytes()
        b = photo_bytes((100, 60, 80))
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for number, contents in enumerate((a, b, a, a), 1):
                p = Path(directory) / f"test{number}.png"
                p.write_bytes(contents)
                paths.append(p)
            self.assertEqual(exact_duplicate_photo_pairs(paths), [[1, 3], [1, 4], [3, 4]])
            self.assertEqual(exact_duplicate_photo_pairs(paths[:2]), [])

    def test_duplicate_case_returns_422_before_claim_or_analyzer(self):
        import main
        data = photo_bytes()
        files = [
            UploadFile(filename="front.png", file=io.BytesIO(data)),
            UploadFile(filename="same-bits-different-name.png", file=io.BytesIO(data))
        ]
        with (patch.object(main, "_gate_or_block", return_value=None) as gate,
              patch.object(main, "_claim_or_block") as claim,
              patch.object(main, "analyze_board") as analyzer):
            response = asyncio.run(main.analyze_board_case_route(
                request=object(), files=files, item_kind="auto"
            ))
        self.assertEqual(response.status_code, 422)
        body = json.loads(response.body)
        self.assertEqual(body["status"], "duplicate_photos_in_case")
        self.assertEqual(body["duplicate_photo_pairs"], [[1, 2]])
        self.assertIn("No free case was used", body["message"])
        self.assertNotIn("visitor_id", body)
        self.assertNotIn("hash", str(body).lower())
        gate.assert_called_once()
        claim.assert_not_called()
        analyzer.assert_not_called()

    def test_preflight_has_no_side_effect_on_input_files(self):
        a = photo_bytes()
        b = photo_bytes((180, 160, 140))
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for number, contents in enumerate((a, b), 1):
                p = Path(directory) / f"case{number}.png"
                p.write_bytes(contents)
                paths.append(p)
            self.assertEqual(exact_duplicate_photo_pairs(paths), [])
            self.assertEqual([p.read_bytes() for p in paths], [a, b])


if __name__ == "__main__":
    unittest.main()
