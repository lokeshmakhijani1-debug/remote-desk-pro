from agent.maintenance_curtain import (
    capability_for,
    selected_monitor_indexes,
    sentinel_is_visible,
    sentinel_rgb,
)


def test_windows_build_and_dwm_capability_gate():
    assert capability_for(19041, True).supported
    assert not capability_for(19040, True).supported
    assert not capability_for(22631, False).supported
    assert not capability_for(None, True, is_windows=False).supported


def test_sentinel_probe_detects_overlay_and_avoids_baseline_colour():
    baseline = (12, 80, 200)
    sentinel = sentinel_rgb(baseline)
    assert sentinel != baseline
    frame = bytes(sentinel) * 16
    assert sentinel_is_visible(frame, 4, 4, sentinel)
    assert not sentinel_is_visible(bytes(baseline) * 16, 4, 4, sentinel)


def test_monitor_selection_defaults_to_all_physical_displays():
    assert selected_monitor_indexes(None, 3) == [1, 2]
    assert selected_monitor_indexes([2, 1, 2], 3) == [1, 2]


def test_monitor_selection_rejects_virtual_or_unknown_displays():
    try:
        selected_monitor_indexes([0], 3)
    except ValueError:
        pass
    else:
        raise AssertionError("Virtual desktop index 0 must not be selectable")
    try:
        selected_monitor_indexes([3], 3)
    except ValueError:
        pass
    else:
        raise AssertionError("Unknown monitor indexes must be rejected")
