from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytesseract

from app.core.config import get_settings
from app.services.parsers.csv_text import parse_text_blob
from app.services.parsers.base import ParsedMessage


def parse_screenshot(path: str, contact_identifier: str | None = None) -> list[ParsedMessage]:
    settings = get_settings()
    if not settings.ocr_enabled:
        return []

    image = Image.open(Path(path))
    extracted = pytesseract.image_to_string(image)
    return parse_text_blob(extracted, contact_identifier=contact_identifier)
