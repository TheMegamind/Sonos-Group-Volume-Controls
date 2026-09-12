"""Tests for the Sonos Group Volume Controls number platform."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


async def test_solo_player_mirrors_individual_volume(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_volume_entity_id: Callable[[str], str | None],
) -> None:
    """A player with no group mirrors its own volume_level."""
    create_sonos_player("solo_room", "RINCON_SOLO", volume_level=0.42)
    await setup_integration()

    entity_id = group_volume_entity_id("RINCON_SOLO")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state.state == "42"


async def test_grouped_average_read(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_volume_entity_id: Callable[[str], str | None],
) -> None:
    """A grouped player reports the average volume of all group members."""
    p1 = create_sonos_player(
        "room_one", "RINCON_ONE", volume_level=0.2, group_members=[]
    )
    p2 = create_sonos_player(
        "room_two", "RINCON_TWO", volume_level=0.4, group_members=[]
    )
    p3 = create_sonos_player(
        "room_three", "RINCON_THREE", volume_level=0.6, group_members=[]
    )
    members = [p1, p2, p3]
    for entity_id, volume in ((p1, 0.2), (p2, 0.4), (p3, 0.6)):
        hass.states.async_set(
            entity_id, "playing", {"volume_level": volume, "group_members": members}
        )
    await setup_integration()

    entity_id = group_volume_entity_id("RINCON_ONE")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state.state == "40"


async def test_proportional_set_scales_members(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_volume_entity_id: Callable[[str], str | None],
) -> None:
    """Setting the group volume scales every member proportionally."""
    p1 = create_sonos_player("room_one", "RINCON_ONE")
    p2 = create_sonos_player("room_two", "RINCON_TWO")
    members = [p1, p2]
    hass.states.async_set(
        p1, "playing", {"volume_level": 0.4, "group_members": members}
    )
    hass.states.async_set(
        p2, "playing", {"volume_level": 0.6, "group_members": members}
    )
    await setup_integration()
    calls = async_mock_service(hass, "media_player", "volume_set")

    entity_id = group_volume_entity_id("RINCON_ONE")
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": 80},
        blocking=True,
    )

    volumes = {call.data["entity_id"]: call.data["volume_level"] for call in calls}
    assert volumes[p1] == pytest.approx(0.64)
    assert volumes[p2] == pytest.approx(0.96)


async def test_zero_volume_set_fallback(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_volume_entity_id: Callable[[str], str | None],
) -> None:
    """When every member is at 0%, the target is applied directly, not scaled."""
    p1 = create_sonos_player("room_one", "RINCON_ONE")
    p2 = create_sonos_player("room_two", "RINCON_TWO")
    members = [p1, p2]
    hass.states.async_set(
        p1, "playing", {"volume_level": 0.0, "group_members": members}
    )
    hass.states.async_set(
        p2, "playing", {"volume_level": 0.0, "group_members": members}
    )
    await setup_integration()
    calls = async_mock_service(hass, "media_player", "volume_set")

    entity_id = group_volume_entity_id("RINCON_ONE")
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": 30},
        blocking=True,
    )

    volumes = {call.data["entity_id"]: call.data["volume_level"] for call in calls}
    assert volumes[p1] == pytest.approx(0.3)
    assert volumes[p2] == pytest.approx(0.3)


async def test_proportional_set_clamps_at_bounds(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_volume_entity_id: Callable[[str], str | None],
) -> None:
    """A scale factor that would exceed 100% clamps instead of overshooting."""
    p1 = create_sonos_player("room_one", "RINCON_ONE")
    p2 = create_sonos_player("room_two", "RINCON_TWO")
    members = [p1, p2]
    hass.states.async_set(
        p1, "playing", {"volume_level": 0.9, "group_members": members}
    )
    hass.states.async_set(
        p2, "playing", {"volume_level": 0.5, "group_members": members}
    )
    await setup_integration()
    calls = async_mock_service(hass, "media_player", "volume_set")

    entity_id = group_volume_entity_id("RINCON_ONE")
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": 100},
        blocking=True,
    )

    volumes = {call.data["entity_id"]: call.data["volume_level"] for call in calls}
    assert volumes[p1] == pytest.approx(1.0)
    assert volumes[p2] == pytest.approx(5 / 7)


async def test_member_removed_from_group_recomputes(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_volume_entity_id: Callable[[str], str | None],
) -> None:
    """When a member drops out of the group, the average recomputes to solo."""
    p1 = create_sonos_player("room_one", "RINCON_ONE")
    p2 = create_sonos_player("room_two", "RINCON_TWO")
    members = [p1, p2]
    hass.states.async_set(
        p1, "playing", {"volume_level": 0.2, "group_members": members}
    )
    hass.states.async_set(
        p2, "playing", {"volume_level": 0.8, "group_members": members}
    )
    await setup_integration()
    entity_id = group_volume_entity_id("RINCON_ONE")
    assert hass.states.get(entity_id).state == "50"

    hass.states.async_set(p1, "playing", {"volume_level": 0.2, "group_members": []})
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "20"


async def test_new_player_added_at_runtime_creates_entity(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_volume_entity_id: Callable[[str], str | None],
) -> None:
    """A Sonos player registered after setup gets its own group volume entity."""
    create_sonos_player("room_one", "RINCON_ONE", volume_level=0.5)
    await setup_integration()
    assert group_volume_entity_id("RINCON_NEW") is None

    create_sonos_player("room_new", "RINCON_NEW", volume_level=0.3)
    await hass.async_block_till_done()

    entity_id = group_volume_entity_id("RINCON_NEW")
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "30"


async def test_unavailable_member_is_excluded_from_average(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_volume_entity_id: Callable[[str], str | None],
) -> None:
    """A member that is unavailable is skipped when averaging group volume."""
    p1 = create_sonos_player("room_one", "RINCON_ONE")
    p2 = create_sonos_player("room_two", "RINCON_TWO")
    members = [p1, p2]
    hass.states.async_set(
        p1, "playing", {"volume_level": 0.6, "group_members": members}
    )
    hass.states.async_set(p2, "unavailable", {"group_members": members})
    await setup_integration()

    entity_id = group_volume_entity_id("RINCON_ONE")
    assert hass.states.get(entity_id).state == "60"


async def test_solo_set_calls_volume_set_directly(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_volume_entity_id: Callable[[str], str | None],
) -> None:
    """Setting a solo player's group volume calls volume_set on itself."""
    p1 = create_sonos_player("solo_room", "RINCON_SOLO", volume_level=0.5)
    await setup_integration()
    calls = async_mock_service(hass, "media_player", "volume_set")

    entity_id = group_volume_entity_id("RINCON_SOLO")
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": 70},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data["entity_id"] == p1
    assert calls[0].data["volume_level"] == pytest.approx(0.7)


async def test_group_coordinator_attributes_not_exposed(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_volume_entity_id: Callable[[str], str | None],
) -> None:
    """The group volume number entity no longer exposes coordinator attributes.

    Regression guard: group_coordinator/group_coordinator_name were relocated
    to SonosGroupStatusSensor (see test_sensor.py) and must not reappear here.
    """
    p1 = create_sonos_player("room_one", "RINCON_ONE", group_members=[])
    p2 = create_sonos_player("room_two", "RINCON_TWO", group_members=[])
    members = [p1, p2]
    hass.states.async_set(
        p1,
        "playing",
        {"volume_level": 0.2, "group_members": members, "friendly_name": "Room One"},
    )
    hass.states.async_set(
        p2,
        "playing",
        {"volume_level": 0.4, "group_members": members, "friendly_name": "Room Two"},
    )
    await setup_integration()

    entity_id = group_volume_entity_id("RINCON_TWO")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert "group_coordinator" not in state.attributes
    assert "group_coordinator_name" not in state.attributes


async def test_entity_removed_when_target_removed_from_registry(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_volume_entity_id: Callable[[str], str | None],
) -> None:
    """Removing the underlying Sonos entity removes its group volume entity."""
    target_entity_id = create_sonos_player("room_one", "RINCON_ONE", volume_level=0.5)
    await setup_integration()
    group_entity_id = group_volume_entity_id("RINCON_ONE")
    assert hass.states.get(group_entity_id) is not None

    entity_registry = er.async_get(hass)
    entity_registry.async_remove(target_entity_id)
    await hass.async_block_till_done()

    assert group_volume_entity_id("RINCON_ONE") is None
    assert hass.states.get(group_entity_id) is None


async def test_group_volume_entity_attaches_to_target_device(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_volume_entity_id: Callable[[str], str | None],
) -> None:
    """The group volume entity attaches to the target speaker's own device.

    Regression guard: building DeviceInfo from a copy of the target device's
    identifiers/connections forks a duplicate device row under our config
    entry instead of nesting onto the speaker's native device card. The
    entity must instead resolve onto the same device row as the target.
    """
    target_entity_id = create_sonos_player("room_one", "RINCON_ONE", volume_level=0.5)
    await setup_integration()

    entity_registry = er.async_get(hass)
    target_device_id = entity_registry.entities[target_entity_id].device_id
    assert target_device_id is not None

    entity_id = group_volume_entity_id("RINCON_ONE")
    assert entity_id is not None
    assert entity_registry.entities[entity_id].device_id == target_device_id

    device_registry = dr.async_get(hass)
    assert len(device_registry.devices) == 1


async def test_group_volume_entity_follows_target_device_after_recreation(
    hass: HomeAssistant,
    sonos_config_entry: MockConfigEntry,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_volume_entity_id: Callable[[str], str | None],
) -> None:
    """The entity re-attaches to a recreated target device after a reload.

    Regression guard for the scenario that broke device attachment: the
    native sonos integration recreates a speaker's device row (e.g. after a
    firmware update), and our entity's attachment must follow the target to
    its new device rather than remaining pinned to whichever device existed
    when our entity was first created.
    """
    target_entity_id = create_sonos_player("room_one", "RINCON_ONE", volume_level=0.5)
    entry = await setup_integration()

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    original_device_id = entity_registry.entities[target_entity_id].device_id

    new_device = device_registry.async_get_or_create(
        config_entry_id=sonos_config_entry.entry_id,
        identifiers={("sonos", "RINCON_ONE_NEW")},
        name="Room One",
    )
    entity_registry.async_update_entity(target_entity_id, device_id=new_device.id)

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = group_volume_entity_id("RINCON_ONE")
    assert entity_id is not None
    assert entity_registry.entities[entity_id].device_id == new_device.id
    assert entity_registry.entities[entity_id].device_id != original_device_id
