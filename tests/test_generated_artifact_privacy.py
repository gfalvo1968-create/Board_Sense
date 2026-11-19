"""Guardrails for private, nonpersistent derived board images."""
import base64
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from starlette.routing import Mount

from main import app
from routes.board_blueprint import generate_blueprint


class BlueprintPrivacyTests(unittest.TestCase):
    def test_generated_blueprint_is_inline_and_not_written_to_a_public_folder(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "private-board.jpg"
            output_dir = root / "Blueprints"
            image = np.full((800, 1600, 3), 230, dtype=np.uint8)
            cv2.rectangle(image, (70, 60), (1500, 740), (36, 90, 34), -1)
            self.assertTrue(cv2.imwrite(str(input_path), image))

            with (
                patch("routes.board_blueprint.inspect_frame",
                      return_value={"block_analysis": False}),
                patch("routes.board_blueprint.board_region_mask",
                      return_value=np.full((800, 1600), 255, dtype=np.uint8)),
                patch("routes.board_blueprint.detect_motherboard",
                      return_value={"structure_regions": [], "motherboard_structure_score": 0}),
            ):
                result = generate_blueprint(
                    str(input_path),
                    [{"type": "IC-like package", "x": 350, "y": 210,
                      "w": 100, "h": 90, "confidence": 92}],
                    output_dir,
                )
            self.assertTrue(result["available"], result.get("message"))
            self.assertEqual(result["delivery_mode"], "inline_no_store")
            self.assertNotIn("image_filename", result)
            self.assertTrue(result["image_url"].startswith("data:image/jpeg;base64,"))
            raw = base64.b64decode(result["image_url"].split(",", 1)[1], validate=True)
            decoded = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
            self.assertIsNotNone(decoded)
            self.assertLessEqual(max(decoded.shape[:2]), 1200)
            self.assertFalse(output_dir.exists(), "Do not persist derived blueprint images")

    def test_no_public_blueprint_or_crop_directory_mounts(self):
        mounts = {route.path for route in app.routes if isinstance(route, Mount)}
        self.assertNotIn("/blueprints", mounts)
        self.assertNotIn("/multi-board-crops", mounts)
        self.assertIn("/Static", mounts)


if __name__ == "__main__":
    unittest.main()
