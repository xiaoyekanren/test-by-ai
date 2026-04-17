from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current UTC time using a non-deprecated clock source.

    The backend currently stores UTC timestamps as naive datetimes in the
    database and JSON payloads. We source the time from a timezone-aware UTC
    clock, then normalize back to the existing naive representation so this
    migration stays low-risk.
    """

    return datetime.now(UTC).replace(tzinfo=None)
