"""Security checks for the public Board Sense image upload paths."""

import asyncio
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from PIL import Image

from routes.upload_security import MAX_UPLOAD_BYTES, save_board_image


def png_bytes(width=2, height=2):
    output = BytesIO()
    Image.new("RGB", (width, height), "white").save(output, format="PNG")
    return output.getvalue()


def upload(filename, content):
    return UploadFile(file=BytesIO(content), filename=filename)


class UploadSecurityTests(unittest.TestCase):
    def test_client_filename_cannot_escape_or_overwrite_another_file(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            images = root / "data" / "Images"
            protected = root / "Static" / "app.png"
            protected.parent.mkdir()
            protected.write_bytes(b"original")

            for name in ("../../Static/app.png", str(protected)):
                stored = save_board_image(upload(name, png_bytes()), images)
                self.assertEqual(stored.parent, images)
                self.assertEqual(stored.suffix, ".png")
                self.assertNotIn("app", stored.name)
                self.assertEqual(protected.read_bytes(), b"original")

            self.assertEqual(len(list(images.iterdir())), 2)

    def test_rejects_large_file_and_removes_partial_copy(self):
        with TemporaryDirectory() as temp:
            images = Path(temp) / "Images"
            with self.assertRaises(HTTPException) as caught:
                save_board_image(upload("photo.png", png_bytes() + b"x" * MAX_UPLOAD_BYTES), images)
            self.assertEqual(caught.exception.status_code, 413)
            self.assertEqual(list(images.iterdir()), [])

    def test_rejects_non_image_content_and_large_dimensions(self):
        with TemporaryDirectory() as temp:
            images = Path(temp) / "Images"
            with self.assertRaises(HTTPException) as caught:
                save_board_image(upload("photo.png", b"<script>bad</script>"), images)
            self.assertEqual(caught.exception.status_code, 400)
            with patch("routes.upload_security.MAX_IMAGE_PIXELS", 1):
                with self.assertRaises(HTTPException) as caught:
                    save_board_image(upload("photo.png", png_bytes()), images)
            self.assertEqual(caught.exception.status_code, 413)
            self.assertEqual(list(images.iterdir()), [])

    def test_analyze_route_uses_safe_storage_before_analysis(self):
        import main

        with TemporaryDirectory() as temp:
            root = Path(temp)
            images = root / "data" / "Images"
            protected = root / "Static" / "app.png"
            protected.parent.mkdir()
            protected.write_bytes(b"original")

            with (
                patch.object(main, "IMAGE_DIR", images),
                patch.object(main, "_gate_or_block", return_value=None),
                patch.object(main, "_attach_usage", side_effect=lambda result, request, mode: result),
                patch.object(main, "analyze_board", return_value={}) as analyzer,
                patch.object(main, "build_evidence_packet", return_value={}),
            ):
                result = asyncio.run(
                    main.analyze_board_route(
                        request=object(), file=upload("../../Static/app.png", png_bytes())
                    )
                )

            self.assertEqual(result["status"], "success")
            self.assertEqual(protected.read_bytes(), b"original")
            stored = Path(analyzer.call_args.args[0])
            self.assertEqual(stored.parent, images)
            self.assertEqual(stored.suffix, ".png")


if __name__ == "__main__":
    unittest.main()
