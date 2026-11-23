from agent.privacy_overlay import (
    EMERGENCY_HOTKEY_MODIFIERS,
    EMERGENCY_HOTKEY_VK,
    WDA_EXCLUDEFROMCAPTURE,
)


def test_privacy_curtain_uses_capture_exclusion_and_emergency_hotkey():
    assert WDA_EXCLUDEFROMCAPTURE == 0x11
    assert EMERGENCY_HOTKEY_VK == ord("B")
    assert EMERGENCY_HOTKEY_MODIFIERS == (0x0002 | 0x0001 | 0x0004)

def test_privacy_curtain_is_click_through_and_non_activating():
    from agent.privacy_overlay import (
        WS_EX_LAYERED,
        WS_EX_NOACTIVATE,
        WS_EX_TOOLWINDOW,
        WS_EX_TRANSPARENT,
    )
    assert WS_EX_TRANSPARENT == 0x00000020
    assert WS_EX_LAYERED == 0x00080000
    assert WS_EX_TOOLWINDOW == 0x00000080
    assert WS_EX_NOACTIVATE == 0x08000000
