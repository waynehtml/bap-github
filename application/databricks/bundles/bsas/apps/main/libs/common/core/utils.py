"""Date-only helpers using the runtime's local date when no date is supplied."""

from datetime import date as Date
from datetime import datetime, timedelta


def date_to_str(dt: Date | None = None, fmt: str = "%Y%m%d") -> str:
    """Format a date, defaulting to today's date in the runtime's timezone."""
    target = dt or Date.today()  # noqa: DTZ011 - preserve runtime-local date behavior
    return target.strftime(fmt)


def str_to_date(s: str | int, fmt: str = "%Y%m%d") -> Date:
    """Parse a string or integer into a date; reject empty or malformed input."""
    if s is None:
        raise ValueError("str_to_date: input must be a non-empty string or int")
    text = str(s).strip()
    if not text:
        raise ValueError("str_to_date: input string is empty")
    return datetime.strptime(text, fmt).date()  # noqa: DTZ007 - date-only result


def get_last_weekday(ref_date: Date | None = None) -> Date:
    """Return the last Monday-to-Friday date strictly before ref_date.

    An omitted date uses the runtime's local date. Holidays are not considered.
    """
    if ref_date is None:
        ref_date = Date.today()  # noqa: DTZ011 - preserve runtime-local date behavior
    weekday = ref_date.weekday()
    if weekday == 0:
        return ref_date - timedelta(days=3)
    elif weekday == 6:
        return ref_date - timedelta(days=2)
    elif weekday == 5:
        return ref_date - timedelta(days=1)
    else:
        return ref_date - timedelta(days=1)
