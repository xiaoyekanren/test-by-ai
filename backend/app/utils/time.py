from datetime import UTC, datetime

from sqlalchemy.types import String, TypeDecorator


class UTCDateTime(TypeDecorator):
    """Persist timezone-aware UTC datetimes without losing offset data in SQLite."""

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("UTCDateTime only accepts timezone-aware datetimes")
        return value.astimezone(UTC).isoformat(timespec="microseconds")

    def process_result_value(self, value: str | None, dialect) -> datetime | None:
        if value is None:
            return None
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("UTCDateTime expected a timezone-aware value from storage")
        return parsed.astimezone(UTC)


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""

    return datetime.now(UTC)
