from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator


class Listing(BaseModel):
    provider: str = Field(min_length=1, max_length=60, pattern=r"^[a-zA-Z0-9_-]+$")
    provider_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=2, max_length=250)
    venue: str = Field(min_length=2, max_length=150)
    city: str = Field(min_length=2, max_length=80)
    starts_at: datetime
    updated_at: datetime
    price_cents: int = Field(ge=0, le=100_000_000)
    quantity: int = Field(ge=0, le=100_000)
    category: str = Field(default="music", pattern=r"^(music|sports|comedy|theater)$")

    @field_validator("starts_at", "updated_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone offset required; use an ISO-8601 timestamp")
        return value.astimezone(UTC)

    def record(self) -> dict:
        return self.model_dump(mode="json")
