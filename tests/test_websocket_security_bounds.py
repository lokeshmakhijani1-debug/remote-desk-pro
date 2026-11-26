from backend.main import MAX_WS_BINARY_BYTES, MAX_WS_TEXT_BYTES, websocket_payload_within_limit


def test_websocket_text_frames_are_bounded():
    assert websocket_payload_within_limit("x" * MAX_WS_TEXT_BYTES)
    assert not websocket_payload_within_limit("x" * (MAX_WS_TEXT_BYTES + 1))


def test_websocket_binary_frames_are_bounded():
    assert websocket_payload_within_limit(b"x" * MAX_WS_BINARY_BYTES)
    assert not websocket_payload_within_limit(b"x" * (MAX_WS_BINARY_BYTES + 1))


def test_websocket_payload_rejects_non_string_types():
    assert not websocket_payload_within_limit(None)
    assert not websocket_payload_within_limit({"type": "control"})
