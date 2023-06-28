from pathlib import Path

from pix_framework.discovery.resource_profiles import discover_undifferentiated_resource_profile
from pix_framework.input import read_csv_log
from pix_framework.log_ids import DEFAULT_CSV_IDS

assets_dir = Path(__file__).parent.parent / "assets"


def test_resource_profiles_undifferentiated_keep_names():
    log_path = assets_dir / 'LoanApp_sequential_9-5_diffres_timers.csv'

    log_ids = DEFAULT_CSV_IDS

    log = read_csv_log(log_path, log_ids)

    # Discover undifferentiated profile keeping log resource names
    undifferentiated_profile = discover_undifferentiated_resource_profile(
        event_log=log,
        log_ids=log_ids
    )
    # Assert discovered profile name is expected
    assert undifferentiated_profile is not None
    assert undifferentiated_profile.name == 'Undifferentiated_resource_profile'
    # Assert the resources are the ones from the log
    log_resources = list(log[log_ids.resource].unique())
    profile_resources = [resource.name for resource in undifferentiated_profile.resources]
    assert sorted(profile_resources) == sorted(log_resources)
    # Assert the resources have all activities assigned to them
    log_activities = sorted(log[log_ids.activity].unique())
    for resource in undifferentiated_profile.resources:
        assert sorted(resource.assigned_tasks) == log_activities


def test_resource_profiles_undifferentiated_simplify():
    log_path = assets_dir / 'LoanApp_sequential_9-5_diffres_timers.csv'

    log_ids = DEFAULT_CSV_IDS

    log = read_csv_log(log_path, log_ids)

    # Discover undifferentiated profile keeping log resource names
    undifferentiated_profile = discover_undifferentiated_resource_profile(
        event_log=log,
        log_ids=log_ids,
        keep_log_names=False
    )
    # Assert discovered profile name is expected
    assert undifferentiated_profile is not None
    assert undifferentiated_profile.name == 'Undifferentiated_resource_profile'
    # Assert the number of resources in the log is the same as the amount
    num_log_resources = log[log_ids.resource].nunique()
    assert len(undifferentiated_profile.resources) == 1
    assert undifferentiated_profile.resources[0].amount == num_log_resources
    # Assert the resource has all activities assigned
    log_activities = sorted(log[log_ids.activity].unique())
    assert sorted(undifferentiated_profile.resources[0].assigned_tasks) == log_activities