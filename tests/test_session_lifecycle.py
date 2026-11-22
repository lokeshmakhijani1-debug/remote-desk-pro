from backend.config import settings
from backend.security import issue_token, read_token

def test_dynamic_password_default_is_24_hours():
    assert settings.device_password_ttl_seconds >= 24 * 60 * 60

def test_account_token_lifetime_is_persistent_but_bounded():
    payload = read_token(issue_token("42", "technician"))
    assert payload["exp"] - payload["iat"] >= 29 * 24 * 60 * 60

def test_viewer_session_token_is_device_scoped_and_long_lived_for_reconnect():
    account_token = issue_token("42", "technician")
    viewer_token = issue_token("viewer:42:123456789", "technician", settings.session_ttl_seconds)
    assert read_token(account_token)["sub"] == "42"
    payload = read_token(viewer_token)
    assert payload["sub"] == "viewer:42:123456789"
    assert payload["exp"] - payload["iat"] >= 29 * 24 * 60 * 60


def test_hub_host_replacement_returns_previous_socket():
    import asyncio
    from backend.main import Hub

    async def exercise():
        hub = Hub()
        first, second = object(), object()
        assert await hub.register_host("device-1", first) is None
        assert await hub.register_host("device-1", second) is first
        assert hub.hosts["device-1"] is second

    asyncio.run(exercise())


def test_hub_reclaims_same_authenticated_viewer_but_rejects_other_viewer():
    import asyncio
    from backend.main import Hub

    async def exercise():
        hub = Hub()
        first, resumed, other = object(), object(), object()
        accepted, active, total, previous = await hub.register_viewer("device-1", first, 50, 42)
        assert accepted and active == 1 and total == 1 and previous is None
        accepted, active, total, previous = await hub.register_viewer("device-1", other, 50, 99)
        assert not accepted and active == 1 and total == 1 and previous is None
        accepted, active, total, previous = await hub.register_viewer("device-1", resumed, 50, 42)
        assert accepted and active == 1 and total == 1 and previous is first
        assert hub.viewers["device-1"] == {resumed}
        assert not await hub.remove_viewer("device-1", first)
        assert await hub.remove_viewer("device-1", resumed)
        assert "device-1" not in hub.viewers

    asyncio.run(exercise())


def test_hub_keeps_viewer_reservation_after_transport_loss_until_explicit_end():
    import asyncio
    from backend.main import Hub

    async def exercise():
        hub = Hub()
        viewer = object()
        await hub.register_viewer("device-1", viewer, 50, 42)
        accepted, active, total, previous = await hub.register_viewer("device-1", object(), 50, 42)
        assert accepted and active == 1 and total == 1 and previous is viewer

    asyncio.run(exercise())
