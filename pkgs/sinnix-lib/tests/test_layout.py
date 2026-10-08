"""Managed path contracts without imposing names on native capture lanes."""

from pathlib import Path

import pytest

from sinnix_lib.layout import capture_lane_path, machine_lane_path


def test_managed_machine_destination_and_custom_root():
    assert machine_lane_path('/custom/host', 'experiment') == Path('/custom/host/experiment')
    assert machine_lane_path('/custom/host', 'peripheral') == Path('/custom/host/peripheral')
    with pytest.raises(KeyError):
        machine_lane_path('/custom/host', 'experiments')


def test_capture_paths_keep_native_lane_identity():
    assert capture_lane_path('/custom/capture', 'audio-devices') == Path('/custom/capture/audio/device')
    assert capture_lane_path('/custom/peripheral', 'bt-audio') == Path('/custom/peripheral/bt-audio')
