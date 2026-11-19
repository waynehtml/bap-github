# Calendar and date utilities

## When to use this capability

Use `CalendarUtils` for calendar-day, weekday, business-day, holiday, and month calculations. Use `time_utils` for timezone-aware “now/today” values, UTC conversion, ISO strings, Unix timestamps, and date-string conversion.

## Choose the public API

- Use `CalendarUtils.from_holidays` when business-day calculations must exclude a known holiday set.
- Use `Weekday` instead of raw integers in weekday-oriented calls.
- Use weekday helpers when holidays must be ignored; use business-day helpers when configured holidays must be excluded.
- Use `time_utils` for datetime and serialization boundaries.

## Restrictions and side effects

`CalendarUtils` treats Monday through Friday as weekdays. Its configured timezone affects only `today`; arithmetic operates on supplied dates. A zero weekday offset returns the original date even on a weekend, while a zero business-day offset rolls a non-business date forward.

Time helpers return timezone-aware values unless they return a `date` or string. `to_utc` interprets a naive datetime in the host system timezone, while `datetime_to_utc_iso_str` interprets it in the package default timezone. Prefer aware datetimes at boundaries.

`set_default_tz` mutates module state, but default arguments bound when the module was imported do not change. Pass `tz` explicitly when a call must follow a dynamically selected timezone. Options named `ms` preserve microseconds rather than truncating to milliseconds.

## Short example

```python
from datetime import date

from oeds.core.calendar_utils import CalendarUtils, Weekday
from oeds.core.time_utils import datetime_to_utc_iso_str, now_local

calendar = CalendarUtils.from_holidays([date(2026, 1, 1)], tz_name="UTC")
next_business_day = calendar.business_day_next(date(2025, 12, 31))
first_monday = calendar.month_first_weekday(next_business_day, Weekday.MONDAY)
created_at = datetime_to_utc_iso_str(now_local(tz="UTC"))

print(next_business_day, first_monday, created_at)
```

## Related examples

- [Calendar example](../../examples/calendar_utils/date_calculations.py)
- [Timezone and timestamp example](../../examples/time_utils/date_time_operations.py)
