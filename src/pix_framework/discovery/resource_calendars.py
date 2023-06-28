from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

import pandas as pd

from pix_framework.calendar.resource_calendar import RCalendar
from pix_framework.discovery.calendar_factory import CalendarFactory
from pix_framework.discovery.resource_profiles import ResourceProfile
from pix_framework.log_ids import EventLogIDs


class CalendarType(str, Enum):
    DEFAULT_24_7 = "24/7"  # 24/7 work day
    DEFAULT_9_5 = "9/5"  # 9 to 5 work day
    UNDIFFERENTIATED = "undifferentiated"
    DIFFERENTIATED_BY_POOL = "differentiated_by_pool"
    DIFFERENTIATED_BY_RESOURCE = "differentiated_by_resource"

    @classmethod
    def from_str(cls, value: str) -> "CalendarType":
        if value.lower() in ("default_24_7", "dt247", "24_7", "247"):
            return cls.DEFAULT_24_7
        elif value.lower() in ("default_9_5", "dt95", "9_5", "95"):
            return cls.DEFAULT_9_5
        elif value.lower() == "undifferentiated":
            return cls.UNDIFFERENTIATED
        elif value.lower() in ("differentiated_by_pool", "pool", "pooled"):
            return cls.DIFFERENTIATED_BY_POOL
        elif value.lower() in ("differentiated_by_resource", "differentiated"):
            return cls.DIFFERENTIATED_BY_RESOURCE
        else:
            raise ValueError(f"Unknown value {value}")

    def __str__(self):
        if self == CalendarType.DEFAULT_24_7:
            return "default_24_7"
        elif self == CalendarType.DEFAULT_9_5:
            return "default_9_5"
        elif self == CalendarType.UNDIFFERENTIATED:
            return "undifferentiated"
        elif self == CalendarType.DIFFERENTIATED_BY_POOL:
            return "differentiated_by_pool"
        elif self == CalendarType.DIFFERENTIATED_BY_RESOURCE:
            return "differentiated_by_resource"
        return f"Unknown CalendarType {str(self)}"


@dataclass
class CalendarDiscoveryParams:
    discovery_type: CalendarType = CalendarType.UNDIFFERENTIATED
    granularity: Optional[int] = 60  # minutes per granule
    confidence: Optional[float] = 0.1  # from 0 to 1.0
    support: Optional[float] = 0.1  # from 0 to 1.0
    participation: Optional[float] = 0.4  # from 0 to 1.0

    def to_dict(self) -> dict:
        # Save discovery type
        calendar_discovery_params = {"discovery_type": self.discovery_type.value}
        # Add calendar discovery parameters if any
        if self.discovery_type in [
            CalendarType.UNDIFFERENTIATED,
            CalendarType.DIFFERENTIATED_BY_RESOURCE,
            CalendarType.DIFFERENTIATED_BY_POOL,
        ]:
            calendar_discovery_params["granularity"] = self.granularity
            calendar_discovery_params["confidence"] = self.confidence
            calendar_discovery_params["support"] = self.support
            calendar_discovery_params["participation"] = self.participation
        # Return dict
        return calendar_discovery_params

    @staticmethod
    def from_dict(calendar_discovery_params: dict) -> "CalendarDiscoveryParams":
        granularity = None
        confidence = None
        support = None
        participation = None
        # If the discovery type implies a discovery, parse parameters
        if calendar_discovery_params["discovery_type"] in [
            CalendarType.UNDIFFERENTIATED,
            CalendarType.DIFFERENTIATED_BY_RESOURCE,
            CalendarType.DIFFERENTIATED_BY_POOL,
        ]:
            granularity = calendar_discovery_params["granularity"]
            confidence = calendar_discovery_params["confidence"]
            support = calendar_discovery_params["support"]
            participation = calendar_discovery_params["participation"]
        # Return parameters instance
        return CalendarDiscoveryParams(
            discovery_type=calendar_discovery_params["discovery_type"],
            granularity=granularity,
            confidence=confidence,
            support=support,
            participation=participation,
        )


def discover_resource_calendars_per_profile(
    event_log: pd.DataFrame,
    log_ids: EventLogIDs,
    params: CalendarDiscoveryParams,
    resource_profiles: List[ResourceProfile],
) -> List[RCalendar]:
    """
    Discover availability calendar for each resource profile in [resource_profiles], updating
    their ID inside the profiles. If the calendar discovery type is 24/7 or 9/5, assign the
    corresponding calendar to each resource profile.

    When it is not possible to discover a resource calendar for a set of resource profiles, e.g.,
    lack of enough data, try:
     1 - Discover a single calendar for all the resource profiles with missing calendar together.
     2 - If not, discover a single calendar for all the resource profiles in the log.
     3 - If not, assign the default 24/7 calendar.

    :param event_log: event log to discover the resource calendars from.
    :param log_ids: column IDs of the event log.
    :param params: parameters for the calendar discovery.
    :param resource_profiles: list of resource profiles with their ID and resources.

    :return: list of availability calendars (one per profile).
    """
    calendar_type = params.discovery_type
    if calendar_type == CalendarType.DEFAULT_24_7:
        # 24/7 calendar to all resource profiles
        full_day_calendar = create_full_day_calendar()
        resource_calendars = [full_day_calendar]
        # Update calendar ID of all resources
        _update_resource_calendars(resource_profiles, full_day_calendar.calendar_id)
    elif calendar_type == CalendarType.DEFAULT_9_5:
        # 9 to 5 calendar per resource profile
        working_hours_calendar = create_working_hours_calendar()
        resource_calendars = [working_hours_calendar]
        # Update calendar ID of all resources
        _update_resource_calendars(resource_profiles, working_hours_calendar.calendar_id)
    elif calendar_type == CalendarType.UNDIFFERENTIATED:
        # Discover a resource calendar for all the resources in the log
        undifferentiated_calendar = _discover_undifferentiated_resource_calendar(event_log, log_ids, params)
        # Set default 24/7 if could not discover one
        if undifferentiated_calendar is None:
            undifferentiated_calendar = create_full_day_calendar()
        # Save discovered calendar
        resource_calendars = [undifferentiated_calendar]
        # Update calendar ID of all resources
        _update_resource_calendars(resource_profiles, undifferentiated_calendar.calendar_id)
    else:
        # Discover a resource calendar per resource profile
        resource_calendars = _discover_resource_calendars_per_profile(event_log, log_ids, params, resource_profiles)
    # Return discovered resource calendars
    return resource_calendars


def _discover_undifferentiated_resource_calendar(
    event_log: pd.DataFrame,
    log_ids: EventLogIDs,
    params: CalendarDiscoveryParams,
    calendar_id: str = "Undifferentiated_calendar",
) -> Optional[RCalendar]:
    """
    Discover one availability calendar using all the timestamps in the received event log.

    :param event_log: event log to discover the resource calendar from.
    :param log_ids: column IDs of the event log.
    :param params: parameters for the calendar discovery.
    :param calendar_id: ID to assign to the discovered calendar.

    :return: resource calendar for all the events in the received event log.
    """
    # Register each timestamp to the same profile
    calendar_factory = CalendarFactory(params.granularity)
    for _, event in event_log.iterrows():
        # Register start/end timestamps
        activity = event[log_ids.activity]
        calendar_factory.check_date_time("Undifferentiated", activity, event[log_ids.start_time])
        calendar_factory.check_date_time("Undifferentiated", activity, event[log_ids.end_time])
    # Discover weekly timetables
    discovered_timetables = calendar_factory.build_weekly_calendars(
        params.confidence, params.support, params.participation
    )
    # Get discovered calendar and update ID if discovered
    undifferentiated_calendar = discovered_timetables.get("Undifferentiated")
    if undifferentiated_calendar is not None:
        undifferentiated_calendar.calendar_id = calendar_id
    # Return resource calendar
    return undifferentiated_calendar


def _discover_resource_calendars_per_profile(
    event_log: pd.DataFrame,
    log_ids: EventLogIDs,
    params: CalendarDiscoveryParams,
    resource_profiles: List[ResourceProfile],
) -> List[RCalendar]:
    # Revert resource profiles
    resource_to_profile = {
        resource.id: resource_profile.id
        for resource_profile in resource_profiles
        for resource in resource_profile.resources
    }

    # --- Discover a calendar per resource profile --- #

    # Register each timestamp to its corresponding profile
    calendar_factory = CalendarFactory(params.granularity)
    for _, event in event_log.iterrows():
        # Register start/end timestamps
        profile_id = resource_to_profile[event[log_ids.resource]]
        activity = event[log_ids.activity]
        calendar_factory.check_date_time(profile_id, activity, event[log_ids.start_time])
        calendar_factory.check_date_time(profile_id, activity, event[log_ids.end_time])

    # Discover weekly timetables
    discovered_timetables = calendar_factory.build_weekly_calendars(
        params.confidence, params.support, params.participation
    )

    # Create calendar per resource profile
    resource_calendars = []
    missing_profiles = []
    for resource_profile in resource_profiles:
        calendar_id = f"{resource_profile.id}_calendar"
        discovered_calendar = discovered_timetables.get(resource_profile.id)
        if discovered_calendar is not None:
            discovered_calendar.calendar_id = calendar_id
            resource_calendars += [discovered_calendar]
            _update_resource_calendars([resource_profile], calendar_id)
        else:
            missing_profiles += [resource_profile]

    # Check if there are resources with no calendars assigned
    if len(missing_profiles) > 0:
        # Retain events performed by the resources with no calendar
        missing_resource_ids = [
            resource.id for resource_profile in resource_profiles for resource in resource_profile.resources
        ]
        filtered_event_log = event_log[event_log[log_ids.resource].isin(missing_resource_ids)]
        # Discover one resource calendar for all of them
        missing_resource_calendar = _discover_undifferentiated_resource_calendar(filtered_event_log, log_ids, params)
        if missing_resource_calendar is None:
            # Could not discover calendar for the missing resources, discover calendar with the entire log
            missing_resource_calendar = _discover_undifferentiated_resource_calendar(event_log, log_ids, params)
            if missing_resource_calendar is None:
                # Could not discover calendar for all the resources in the log, assign default 24/7
                missing_resource_calendar = create_full_day_calendar()
        # Add grouped calendar to discovered resource calendars
        resource_calendars += [missing_resource_calendar]
        # Set common calendar id to missing resources
        _update_resource_calendars(missing_profiles, missing_resource_calendar.calendar_id)
    # Return resource calendars
    return resource_calendars


def _update_resource_calendars(resource_profiles: List[ResourceProfile], calendar_id: str):
    for resource_profile in resource_profiles:
        for resource in resource_profile.resources:
            resource.calendar_id = calendar_id


def create_full_day_calendar(schedule_id: str = "24_7_CALENDAR") -> RCalendar:
    schedule = RCalendar(schedule_id)
    schedule.add_calendar_item(
        from_day="MONDAY",
        to_day="SUNDAY",
        begin_time="00:00:00.000",
        end_time="23:59:59.999",
    )
    return schedule


def create_working_hours_calendar(schedule_id: str = "9_5_CALENDAR") -> RCalendar:
    schedule = RCalendar(schedule_id)
    schedule.add_calendar_item(
        from_day="MONDAY",
        to_day="FRIDAY",
        begin_time="09:00:00.000",
        end_time="17:00:00.000",
    )
    return schedule