from copy import deepcopy

import pytest
from pydantic import ValidationError

from contracts.configuration import load_config
from contracts.models import IntersectionConfig


def test_baseline_cycle_and_movements():
    config = load_config()
    assert config.fixed_time.nominal_cycle_seconds == 450
    assert config.fixed_time.sequence == ["U", "T", "S", "B"]
    assert config.fixed_time.green_seconds == {"U": 85, "T": 150, "S": 95, "B": 100}
    assert config.geometry.left_turn_signal_controlled is False
    assert config.geometry.yield_at_merge is True
    assert config.provenance.current_field_configuration_verified is False
    assert [(a.code, a.outer.left, a.inner.right) for a in config.approaches] == [
        ("U", "T", "B"), ("T", "S", "U"), ("S", "B", "T"), ("B", "U", "S")]


@pytest.mark.parametrize("change", [
    lambda x: x["fixed_time"].update(nominal_cycle_seconds=449),
    lambda x: x["fixed_time"].update(sequence=["U", "U", "S", "B"]),
    lambda x: x["fixed_time"]["green_seconds"].update(U=0),
    lambda x: x["fixed_time"]["green_seconds"].update(U=85.0),
    lambda x: x["fixed_time"]["green_seconds"].update(U=True),
    lambda x: x["approaches"][0]["outer"].update(left="B"),
    lambda x: x["approaches"][0].update(code="T"),
    lambda x: x["geometry"].update(left_turn_signal_controlled=True),
    lambda x: x["geometry"].update(lane_change_in_intersection=True),
])
def test_invalid_geometry_or_timing_is_rejected(change):
    data = deepcopy(load_config().model_dump())
    change(data)
    with pytest.raises(ValidationError):
        IntersectionConfig.model_validate(data)


def test_services_refuse_invalid_configuration(tmp_path):
    from atcs_simulator.app.main import create_app as create_atcs
    from backend.app.main import create_app as create_backend
    from backend.app.settings import Settings

    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"intersection_id":"incomplete"}', encoding="utf-8")
    with pytest.raises(ValidationError):
        create_atcs(str(invalid))
    with pytest.raises(ValidationError):
        create_backend(Settings(_env_file=None, sigap_config_path=str(invalid)))
