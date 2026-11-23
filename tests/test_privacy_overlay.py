from agent.privacy_overlay import (
    EMERGENCY_HOTKEY_MODIFIERS,
    EMERGENCY_HOTKEY_VK,
    WDA_EXCLUDEFROMCAPTURE,
)


def test_privacy_curtain_uses_capture_exclusion_and_emergency_hotkey():
    assert WDA_EXCLUDEFROMCAPTURE == 0x11
    assert EMERGENCY_HOTKEY_VK == ord("B")
    assert EMERGENCY_HOTKEY_MODIFIERS == (0x0002 | 0x0001 | 0x0004)
