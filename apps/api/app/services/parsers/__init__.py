from pathlib import Path

from app.models.entities import ImportPlatform
from app.services.parsers.android_sms import parse_android_sms_export, parse_android_sms_file
from app.services.parsers.csv_text import parse_csv_export, parse_csv_file, parse_text_blob, parse_text_file
from app.services.parsers.imessage import parse_imessage_db
from app.services.parsers.instagram import parse_instagram_export, parse_instagram_file
from app.services.parsers.screenshot import parse_screenshot
from app.services.parsers.telegram import parse_telegram_export, parse_telegram_file
from app.services.parsers.whatsapp import parse_whatsapp_export, parse_whatsapp_file


def _read_text_file(file_path: str) -> str:
    return Path(file_path).read_text(encoding="utf-8", errors="ignore")


def parse_messages(
    source_platform: ImportPlatform,
    file_path: str | None = None,
    content: str | None = None,
    contact_identifier: str | None = None,
):
    if source_platform == ImportPlatform.IMESSAGE and file_path:
        return parse_imessage_db(file_path, contact_identifier=contact_identifier)
    if source_platform == ImportPlatform.WHATSAPP and file_path:
        return parse_whatsapp_file(file_path, contact_identifier=contact_identifier)
    if source_platform == ImportPlatform.WHATSAPP and content is not None:
        return parse_whatsapp_export(content, contact_identifier=contact_identifier)
    if source_platform == ImportPlatform.TELEGRAM and file_path:
        return parse_telegram_file(file_path, contact_identifier=contact_identifier)
    if source_platform == ImportPlatform.TELEGRAM and content is not None:
        return parse_telegram_export(content, contact_identifier=contact_identifier)
    if source_platform == ImportPlatform.INSTAGRAM and file_path:
        return parse_instagram_file(file_path, contact_identifier=contact_identifier)
    if source_platform == ImportPlatform.INSTAGRAM and content is not None:
        return parse_instagram_export(content, contact_identifier=contact_identifier)
    if source_platform == ImportPlatform.ANDROID_SMS and file_path:
        return parse_android_sms_file(file_path, contact_identifier=contact_identifier)
    if source_platform == ImportPlatform.ANDROID_SMS and content is not None:
        return parse_android_sms_export(content, contact_identifier=contact_identifier)
    if source_platform == ImportPlatform.CSV and file_path:
        suffix = Path(file_path or "").suffix.lower()
        if suffix == ".csv":
            return parse_csv_file(file_path, contact_identifier=contact_identifier)
        return parse_text_file(file_path, contact_identifier=contact_identifier)
    if source_platform == ImportPlatform.CSV and content is not None:
        suffix = Path(file_path or "").suffix.lower()
        if suffix == ".csv":
            return parse_csv_export(content, contact_identifier=contact_identifier)
        return parse_text_blob(content, contact_identifier=contact_identifier)
    if source_platform == ImportPlatform.SCREENSHOT and file_path:
        return parse_screenshot(file_path, contact_identifier=contact_identifier)
    if source_platform == ImportPlatform.PASTE and content is not None:
        return parse_text_blob(content, contact_identifier=contact_identifier)
    return []
