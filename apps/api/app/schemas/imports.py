from datetime import datetime

from pydantic import BaseModel, Field

from app.models.entities import ImportPlatform
from app.schemas.common import DateRangeSummary, MetricExample


class ParsedMessagePreview(BaseModel):
    canonical_id: str
    sender: str
    text: str
    timestamp: datetime
    message_type: str


class ImportContactOption(BaseModel):
    identifier: str
    label: str
    total_messages: int
    sent_messages: int
    received_messages: int
    latest_message_at: datetime | None = None


class ImportPreviewResponse(BaseModel):
    preview_id: str | None = None
    file_name: str
    source_platform: ImportPlatform
    message_count: int
    date_range: DateRangeSummary
    previews: list[ParsedMessagePreview]
    stats: dict[str, int | float | str]
    selection_required: bool = False
    contact_options: list[ImportContactOption] = Field(default_factory=list)


class ImportStatusResponse(BaseModel):
    id: str
    file_name: str
    source_platform: str
    message_count: int
    status: str
    imported_at: datetime
    date_range: DateRangeSummary
    error_details: str | None = None


class ImportUploadResponse(BaseModel):
    import_id: str
    status: str
    message_count: int
    profile_refreshed: bool
    queued: bool = False
    preview: ImportPreviewResponse | None = None
    import_record: ImportStatusResponse | None = None


class PasteImportRequest(BaseModel):
    source_platform: ImportPlatform = Field(default=ImportPlatform.PASTE)
    content: str = Field(min_length=1)
    file_name: str = "pasted-conversation.txt"
    contact_identifier: str | None = None
    run_analysis: bool = True


class ConfirmImportRequest(BaseModel):
    preview_id: str
    run_analysis: bool = True
    contact_identifier: str | None = None


class ImportInstruction(BaseModel):
    platform: str
    title: str
    steps: list[str]
    notes: list[str]
    accepted_extensions: list[str]
