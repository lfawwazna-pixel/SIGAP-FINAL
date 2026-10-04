import pytest
from integration_lab.__main__ import run_lab


@pytest.mark.process
@pytest.mark.parametrize('scenario', ['sender-stop', 'data-freeze', 'release'])
def test_atcs_watchdog_with_real_separate_sender(tmp_path, scenario):
    result = run_lab(scenario, tmp_path/scenario)
    assert result['result'] == 'passed'
