# Calendar Guide

This guide explains how to initialize and use the calendar utility in the template project. Use it when a workflow needs holiday checks, file dates, business-day offsets, weekday logic, or month-based date rules.

The implementation is split across:

- [common.py](../../common.py): configures the calendar factory lifecycle for
  notebooks that run the common bootstrap.
- [src/oeds/domain/utils/calendar/calendar_utils.py](../../src/oeds/domain/utils/calendar/calendar_utils.py): creates a caller-owned
  `CalendarUtils` instance on each request.
- [src/oeds/domain/utils/reference/reference_utils.py](../../src/oeds/domain/utils/reference/reference_utils.py): loads holiday dates from the reference catalog.
- [DataKit calendar API reference](../reference/datakit/api/calendar_utils.md): complete calendar classes, method signatures, and source docstrings.
- [jobs/dataflow/task_00_main.py](../../jobs/dataflow/task_00_main.py): sample production use for holiday-based workflow completion.

## Mental Model

The calendar lifecycle has three steps:

1. Configure `ReferenceManager` and `CalendarManager` in `common.py`.
2. On each access, load holiday dates when a holiday group is configured.
3. Build and return a new caller-owned `CalendarUtils` with those holidays.

The returned calendar object can answer questions such as:

- Is the run date a holiday?
- What is the next business day?
- What is the previous weekday?
- What is the first day of the month?
- What is the second Tuesday of the month?

The utility uses `datetime.date` values. Convert dates to strings with `.isoformat()` only when writing file names, paths, table partition values, logs, or task values.

## Configured Calendar In Notebooks

Most workflow notebooks should create a calendar from the configuration set by
[common.py](../../common.py).

The shared job configuration passes these date and geography settings through `common_base_parameters` in [resources/jobs/common.yml](../../resources/jobs/common.yml):

```yaml
timezone: "${var.timezone}"
human_date_format: "${var.human_date_format}"
python_date_format: "${var.python_date_format}"
spark_date_format: "${var.spark_date_format}"
holiday_group: "${var.holiday_group}"
```

[common.py](../../common.py) reads those parameters into `job_ctx` and configures
the reference and calendar factories without loading holiday data:

```python
from oeds.domain.utils.calendar import CalendarManager
from oeds.domain.utils.reference.reference_utils import ReferenceManager

ReferenceManager.initialize(_ctx.get("reference_catalog"))
CalendarManager.initialize(
    holiday_group=_ctx.get("holiday_group"),
    timezone=_ctx.get("timezone", DEFAULT_TIMEZONE),
)
```

Any notebook that runs the common notebook can create a caller-owned calendar:

```python
# COMMAND ----------
# MAGIC %run ../../common

from oeds.domain.utils.calendar import CalendarManager

job_ctx = get_job_context()
rundate = parse_date(job_ctx["rundate"], job_ctx["python_date_format"])
calendar = CalendarManager.get_instance()

if calendar.is_holiday(rundate):
    dbutils.jobs.taskValues.set(key="flow_action", value="complete")
    dbutils.notebook.exit(f"Workflow completed because rundate {rundate} is a holiday.")
```

This is the pattern used by [jobs/dataflow/task_00_main.py](../../jobs/dataflow/task_00_main.py).
Each `get_instance()` call creates a new calendar and reloads configured holiday
data. Retrieve it once and reuse that object within a notebook when multiple
calendar calculations use the same holidays.

## Configure Holiday Source

The default holiday group is defined by the `holiday_group` bundle variable in [default.databricks.yml](../../default.databricks.yml):

```yaml
holiday_group:
  default: "nationalholidayscanada"
```

When creating a real project:

1. Set `holiday_group` to the reference holiday group needed by the pipeline.
2. Keep the fallback `DEFAULT_HOLIDAY_GROUP` in [common.py](../../common.py) aligned with the bundle value.
3. Confirm the active environment has the expected reference catalog, such as `dev_reference_cat`, `stg_reference_cat`, or `prd_reference_cat`.

Leave `holiday_group` empty to skip the reference lookup and use a calendar with
Monday through Friday as business days and no holiday exclusions.

`ReferenceManager.get_holidays` reads these reference tables:

- `<reference_catalog>.standardized_db.itm_date_dim_base`
- `<reference_catalog>.standardized_db.itm_holidayobservance`
- `<reference_catalog>.standardized_db.itm_holiday`

By default, `ReferenceManager.get_holidays` uses a case-insensitive contains match against `itm_holiday.inGroup`. Use `exact=True` when the group must match exactly.

```python
reference_manager = ReferenceManager.get_instance()

holidays = reference_manager.get_holidays(
    holiday_group="nationalholidayscanada",
)

exact_holidays = reference_manager.get_holidays(
    holiday_group="https://www.bankofcanada.ca/id/NationalHolidaysCanada",
    exact=True,
)
```

## Manual Initialization

Use manual initialization in examples, service tasks, tools, or standalone notebooks where you want to make the dependency explicit.

```python
from oeds.domain.utils.calendar import CalendarManager
from oeds.domain.utils.reference.reference_utils import ReferenceManager

job_ctx = get_job_context()
ReferenceManager.initialize(job_ctx["reference_catalog"])
calendar = CalendarManager.initialize(
    holiday_group=job_ctx["holiday_group"],
    timezone=job_ctx.get("timezone", "America/Toronto"),
).get_instance()
```

The complete DataKit calendar signatures and source docstrings are in the [DataKit calendar API reference](../reference/datakit/api/calendar_utils.md).

## Get Common Dates

Use `rundate` from `job_ctx` as the normal anchor date for workflow decisions. The sample main task already reads it after running `common.py`:

```python
rundate = parse_date(job_ctx["rundate"], job_ctx["python_date_format"])
```

Common date calculations:

```python
from oeds.core.calendar_utils import Weekday

d = parse_date(job_ctx["rundate"], job_ctx["python_date_format"])

today = calendar.today()

previous_calendar_day = calendar.day_prev(d)
next_calendar_day = calendar.day_next(d)
three_calendar_days_later = calendar.day_add(d, 3)

previous_weekday = calendar.weekday_prev(d)
next_weekday = calendar.weekday_next(d)
two_weekdays_later = calendar.weekday_add(d, 2)
monday_of_week = calendar.week_monday(d)
same_week_tuesday = calendar.weekday_this(d, Weekday.TUESDAY)
previous_monday = calendar.weekday_prev_occurrence(d, Weekday.MONDAY)
next_friday = calendar.weekday_next_occurrence(d, Weekday.FRIDAY)

previous_business_day = calendar.business_day_prev(d)
next_business_day = calendar.business_day_next(d)
two_business_days_later = calendar.business_day_add(d, 2)

first_day_of_month = calendar.month_first_day(d)
last_day_of_month = calendar.month_last_day(d)
second_tuesday = calendar.month_second_weekday(d, Weekday.TUESDAY)
last_friday = calendar.month_last_weekday(d, Weekday.FRIDAY)
```

If a date is used in a path, file name, or task value, convert it at the boundary:

```python
from pathlib import Path

file_date = calendar.business_day_prev(rundate).isoformat()
land_dir = str(Path(job_ctx["land_root"]) / file_date)

dbutils.jobs.taskValues.set(key="file_date", value=file_date)
dbutils.jobs.taskValues.set(key="land_dir", value=land_dir)
```

## Date Helper Groups

| Need | Method |
| --- | --- |
| Current date in configured timezone | `calendar.today()` |
| Add calendar days | `calendar.day_add(d, n)` |
| Previous or next calendar day | `calendar.day_prev(d)`, `calendar.day_next(d)` |
| Add Monday-Friday weekdays, ignoring holidays | `calendar.weekday_add(d, n)` |
| Previous or next Monday-Friday weekday | `calendar.weekday_prev(d)`, `calendar.weekday_next(d)` |
| Monday of the current week | `calendar.week_monday(d)` |
| Specific weekday in the same week | `calendar.weekday_this(d, Weekday.TUESDAY)` |
| Previous or next occurrence of a weekday | `calendar.weekday_prev_occurrence(d, Weekday.MONDAY)`, `calendar.weekday_next_occurrence(d, Weekday.FRIDAY)` |
| Previous or next business day | `calendar.business_day_prev(d)`, `calendar.business_day_next(d)` |
| Add business days, excluding holidays | `calendar.business_day_add(d, n)` |
| Check business day or holiday | `calendar.is_business_day(d)`, `calendar.is_holiday(d)` |
| Check weekday or weekend | `calendar.is_weekday(d)`, `calendar.is_weekend(d)` |
| Check exact weekday | `calendar.is_day_of_week(d, Weekday.SUNDAY)`, `calendar.is_monday(d)` |
| First or last day of month | `calendar.month_first_day(d)`, `calendar.month_last_day(d)` |
| Nth weekday in month | `calendar.month_nth_weekday(d, Weekday.TUESDAY, 2)` |
| First, second, third, or fourth weekday in month | `calendar.month_first_weekday(d, weekday)`, `calendar.month_second_weekday(d, weekday)`, `calendar.month_third_weekday(d, weekday)`, `calendar.month_fourth_weekday(d, weekday)` |
| Last weekday in month | `calendar.month_last_weekday(d, Weekday.FRIDAY)` |

`weekday_*` methods use Monday-Friday and ignore holidays. `business_day_*` methods use Monday-Friday and exclude the configured holidays.

## Main Task Pattern

Use [jobs/dataflow/task_00_main.py](../../jobs/dataflow/task_00_main.py) for run-level calendar decisions and shared processing dates.

Holiday exit pattern:

```python
if calendar.is_holiday(rundate):
    logger.info(
        "rundate %s is a holiday. Completing workflow without downstream processing.",
        rundate,
    )
    dbutils.jobs.taskValues.set(key="flow_action", value="complete")
    dbutils.notebook.exit(f"Workflow completed because rundate {rundate} is a holiday.")
```

Business file date pattern:

```python
file_date = calendar.business_day_prev(rundate).isoformat()
logger.info("file_date: %s", file_date)
dbutils.jobs.taskValues.set(key="file_date", value=file_date)
```

Choose the file-date rule that matches the source system. Common rules are previous business day, same run date, previous calendar day, or a named weekday from the same week.

## Validation Checklist

Before using calendar logic in a project, check:

- The bundle `holiday_group` matches the intended reference data group.
- [common.py](../../common.py) fallback defaults match the project bundle values.
- The active reference catalog contains the holiday tables used by `ReferenceManager.get_holidays`.
- Workflow tasks use `CalendarManager.get_instance()` after running `common.py`
  unless they have a reason to initialize one manually.
- Date values passed to calendar helpers are `datetime.date`, not strings.
- Path, file-name, and task-value dates are converted with `.isoformat()` at the boundary.
- `weekday_*` is used for Monday-Friday logic that ignores holidays.
- `business_day_*` is used for Monday-Friday logic that excludes configured holidays.

## Related Guides

- [Dataflow Job Guide](G201-dataflow-job-guide.md): use calendar decisions in the `DATAFLOW` workflow entry task.
- [Service Job Guide](G202-service-job-guide.md): run standalone utility notebooks or tasks that may initialize the calendar manually.
- [DataForge Template Project Guide](G001-dataforge-template-guide.md): understand where the calendar utilities fit in the template.
