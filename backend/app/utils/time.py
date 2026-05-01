from datetime import UTC, datetime

from sqlalchemy.types import String, TypeDecorator


class UTCDateTime(TypeDecorator):
    """在 SQLite 中持久化带时区的 UTC 时间，避免丢失偏移信息。"""

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("UTCDateTime 仅接受带时区信息的时间")
        return value.astimezone(UTC).isoformat(timespec="microseconds")

    def process_result_value(self, value: str | None, dialect) -> datetime | None:
        if value is None:
            return None
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("UTCDateTime 期望从存储中读取带时区信息的值")
        return parsed.astimezone(UTC)


def utc_now() -> datetime:
    """返回当前带时区信息的 UTC 时间。"""

    return datetime.now(UTC)
