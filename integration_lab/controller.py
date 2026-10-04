"""Short-cycle controller for subprocess tests only."""
from atcs_simulator.app.main import create_app
from atcs_simulator.app.control_settings import ControlSettings
from atcs_simulator.app.runtime import AssumedClear
from contracts.control import ControlPolicy


def factory():
    settings = ControlSettings()
    if not settings.configured or not settings.atcs_enable_test_source:
        raise RuntimeError('The isolated lab requires an explicit test key and source flag.')
    return create_app(control_settings=settings, conflict_provider=AssumedClear(),
                      control_policy=ControlPolicy(minimum_green_seconds=1, maximum_green_seconds=20,
                          heartbeat_timeout_seconds=2, data_timeout_seconds=2, plan_wait_seconds=3))
