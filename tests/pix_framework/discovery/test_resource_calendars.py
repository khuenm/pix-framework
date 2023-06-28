from pathlib import Path

import pytest

from pix_framework.calendar.resource_calendar import RCalendar
from pix_framework.discovery.resource_calendars import _discover_undifferentiated_resource_calendar, \
    _discover_resource_calendars_per_profile, CalendarDiscoveryParams
from pix_framework.discovery.resource_profiles import discover_pool_resource_profiles, discover_differentiated_resource_profiles
from pix_framework.input import read_csv_log
from pix_framework.log_ids import APROMORE_LOG_IDS

assets_dir = Path(__file__).parent.parent / "assets"


@pytest.mark.integration
@pytest.mark.parametrize('log_name', ['DifferentiatedCalendars.csv'])
def test_resource_discover_undifferentiated(log_name):
    log_path = assets_dir / log_name
    log_ids = APROMORE_LOG_IDS
    # Read event log
    log = read_csv_log(log_path, log_ids)
    # Discover resource calendar
    result = _discover_undifferentiated_resource_calendar(
        event_log=log,
        log_ids=log_ids,
        params=CalendarDiscoveryParams(),
        calendar_id="Undifferentiated_test"
    )

    assert result
    assert type(result) is RCalendar
    assert result.calendar_id == "Undifferentiated_test"
    assert len(result.work_intervals) > 0


@pytest.mark.integration
@pytest.mark.parametrize('log_name', ['DifferentiatedCalendars.csv'])
def test_resource_discover_per_resource_pool(log_name):
    log_path = assets_dir / log_name
    log_ids = APROMORE_LOG_IDS
    # Read event log
    log = read_csv_log(log_path, log_ids)
    # Discover resource calendar
    result = _discover_resource_calendars_per_profile(
        event_log=log,
        log_ids=log_ids,
        params=CalendarDiscoveryParams(),
        resource_profiles=discover_pool_resource_profiles(
            event_log=log,
            log_ids=log_ids
        )
    )

    assert result
    assert len(result) > 0
    for calendar in result:
        assert len(calendar.work_intervals) > 0


@pytest.mark.integration
@pytest.mark.parametrize('log_name', ['DifferentiatedCalendars.csv'])
def test_resource_discover_per_resource(log_name):
    log_path = assets_dir / log_name
    log_ids = APROMORE_LOG_IDS
    # Read event log
    log = read_csv_log(log_path, log_ids)
    # Discover resource calendar
    result = _discover_resource_calendars_per_profile(
        event_log=log,
        log_ids=log_ids,
        params=CalendarDiscoveryParams(),
        resource_profiles=discover_differentiated_resource_profiles(
            event_log=log,
            log_ids=log_ids
        )
    )

    assert result
    assert len(result) > 0
    for calendar in result:
        assert len(calendar.work_intervals) > 0