"""Hợp đồng API cho kho thông tin chương trình và hàng chờ người trả lời."""

from datetime import datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

Category = Literal["overview", "schedule", "policy", "submission", "support", "other"]
Visibility = Literal["public", "program"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ProgramInformationContent(CamelModel):
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=20_000)
    aliases: list[str] = Field(default_factory=list, max_length=30)
    source_url: AnyHttpUrl | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is not None and value.scheme != "https":
            raise ValueError("sourceUrl phải dùng HTTPS.")
        return value

    @field_validator("valid_from", "valid_to")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Mốc hiệu lực phải có múi giờ.")
        return value

    @model_validator(mode="after")
    def validate_window(self) -> "ProgramInformationContent":
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("validTo phải sau validFrom.")
        return self


class AdminProgramInformationCreateRequest(ProgramInformationContent):
    category: Category = "other"
    visibility: Visibility = "program"


class AdminProgramInformationUpdateRequest(ProgramInformationContent):
    expected_version: int = Field(ge=1)
    category: Category
    visibility: Visibility


class ExpectedVersionRequest(CamelModel):
    expected_version: int = Field(ge=1)


class ProgramInformationItemResponse(CamelModel):
    id: int
    cohort_slug: str
    category: Category
    visibility: Visibility
    status: Literal["draft", "published", "archived"]
    version: int
    published_version: int | None = None
    title: str
    body: str
    aliases: list[str] = Field(default_factory=list)
    source_url: str | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    content_hash: str
    updated_at: datetime
    published_at: datetime | None = None


class ProgramInformationListResponse(CamelModel):
    items: list[ProgramInformationItemResponse] = Field(default_factory=list)
    total: int


class HumanInformationRequestCreate(CamelModel):
    shared_question: str = Field(min_length=3, max_length=2000)
    consent_to_share: bool


class HumanInformationRequestResponse(CamelModel):
    id: int
    status: Literal["open", "resolved"]
    shared_question: str
    created_at: datetime
    resolved_item_id: int | None = None


class HumanInformationRequestList(CamelModel):
    items: list[HumanInformationRequestResponse] = Field(default_factory=list)
    total: int


class ResolveHumanInformationRequest(CamelModel):
    item_id: int = Field(ge=1)
    expected_version: int = Field(ge=1)
