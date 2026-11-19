"""Configured calendar creation for DataForge workflows."""

from __future__ import annotations

import logging
from typing import ClassVar

from oeds.core.calendar_utils import CalendarUtils
import oeds.domain.utils.reference.reference_utils as reference_utils

logger = logging.getLogger(__name__)


class CalendarManager:
    """Configure and create caller-owned workflow calendars."""

    _configuration: ClassVar[tuple[str | None, str] | None] = None

    @classmethod
    def initialize(
        cls,
        *,
        holiday_group: str | None,
        timezone: str,
    ) -> type[CalendarManager]:
        """Replace configuration and return the class for chained creation."""
        configuration = cls._normalize_configuration(
            holiday_group=holiday_group,
            timezone=timezone,
        )
        cls._configuration = configuration
        logger.info(
            "Configured calendar factory for timezone '%s' and holiday group '%s'",
            configuration[1],
            configuration[0] or "<none>",
        )
        return cls

    @classmethod
    def get_instance(cls) -> CalendarUtils:
        """Create a caller-owned calendar from the current configuration."""
        configuration = cls._configuration
        if configuration is None:
            raise RuntimeError(
                "CalendarManager is not initialized. "
                "Call CalendarManager.initialize(...) first."
            )

        holiday_group, timezone = configuration
        if holiday_group is None:
            calendar = CalendarUtils(tz_name=timezone)
            logger.info(
                "Created caller-owned calendar for timezone '%s' without holidays",
                timezone,
            )
        else:
            holidays = reference_utils.ReferenceManager.get_instance().get_holidays(
                holiday_group=holiday_group,
                exact=False,
            )
            calendar = CalendarUtils.from_holidays(
                holidays,
                tz_name=timezone,
            )
            logger.info(
                "Created caller-owned calendar for timezone '%s' with %s holiday(s)",
                timezone,
                len(holidays),
            )

        return calendar

    @staticmethod
    def _normalize_configuration(
        *,
        holiday_group: str | None,
        timezone: str,
    ) -> tuple[str | None, str]:
        if holiday_group is not None and not isinstance(holiday_group, str):
            raise TypeError("holiday_group must be a string or None")
        if not isinstance(timezone, str) or not timezone.strip():
            raise ValueError("timezone is required")

        normalized_holiday_group = (
            holiday_group.strip() if holiday_group and holiday_group.strip() else None
        )
        return normalized_holiday_group, timezone.strip()
