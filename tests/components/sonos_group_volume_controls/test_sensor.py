"""Tests for the Sonos Group Volume Controls sensor platform."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.sonos_group_volume_controls.group_resolution import (
    resolve_group_coordinator_entity_id,
)


async def test_solo_player_is_ungrouped(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """A player with no group members reports ungrouped."""
    create_sonos_player("solo_room", "RINCON_SOLO", group_members=[])
    await setup_integration()

    entity_id = group_status_entity_id("RINCON_SOLO")
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "ungrouped"


async def test_group_members_zero_index_is_coordinator(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """The player at group_members[0] reports coordinator."""
    p1 = create_sonos_player("room_one", "RINCON_ONE", group_members=[])
    p2 = create_sonos_player("room_two", "RINCON_TWO", group_members=[])
    members = [p1, p2]
    hass.states.async_set(p1, "playing", {"group_members": members})
    hass.states.async_set(p2, "playing", {"group_members": members})
    await setup_integration()

    entity_id = group_status_entity_id("RINCON_ONE")
    assert hass.states.get(entity_id).state == "coordinator"


async def test_non_zero_index_member_is_member(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """A player after group_members[0] reports member."""
    p1 = create_sonos_player("room_one", "RINCON_ONE", group_members=[])
    p2 = create_sonos_player("room_two", "RINCON_TWO", group_members=[])
    members = [p1, p2]
    hass.states.async_set(p1, "playing", {"group_members": members})
    hass.states.async_set(p2, "playing", {"group_members": members})
    await setup_integration()

    entity_id = group_status_entity_id("RINCON_TWO")
    assert hass.states.get(entity_id).state == "member"


async def test_status_updates_live_on_group_membership_change(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """Status recomputes immediately when the target's own group_members changes."""
    p1 = create_sonos_player("room_one", "RINCON_ONE", group_members=[])
    p2 = create_sonos_player("room_two", "RINCON_TWO", group_members=[])
    members = [p1, p2]
    hass.states.async_set(p1, "playing", {"group_members": members})
    hass.states.async_set(p2, "playing", {"group_members": members})
    await setup_integration()
    entity_id = group_status_entity_id("RINCON_TWO")
    assert hass.states.get(entity_id).state == "member"

    hass.states.async_set(p2, "playing", {"group_members": []})
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "ungrouped"


async def test_unavailable_target_is_unavailable(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """An unavailable target's group status sensor is also unavailable."""
    create_sonos_player("room_one", "RINCON_ONE", available=False)
    await setup_integration()

    entity_id = group_status_entity_id("RINCON_ONE")
    assert hass.states.get(entity_id).state == "unavailable"


async def test_new_player_added_at_runtime_creates_entity(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """A Sonos player registered after setup gets its own group status entity."""
    create_sonos_player("room_one", "RINCON_ONE", group_members=[])
    await setup_integration()
    assert group_status_entity_id("RINCON_NEW") is None

    create_sonos_player("room_new", "RINCON_NEW", group_members=[])
    await hass.async_block_till_done()

    entity_id = group_status_entity_id("RINCON_NEW")
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "ungrouped"


async def test_entity_removed_when_target_removed_from_registry(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """Removing the underlying Sonos entity removes its group status entity."""
    target_entity_id = create_sonos_player(
        "room_one", "RINCON_ONE", group_members=[]
    )
    await setup_integration()
    status_entity_id = group_status_entity_id("RINCON_ONE")
    assert hass.states.get(status_entity_id) is not None

    entity_registry = er.async_get(hass)
    entity_registry.async_remove(target_entity_id)
    await hass.async_block_till_done()

    assert group_status_entity_id("RINCON_ONE") is None
    assert hass.states.get(status_entity_id) is None


async def test_number_and_sensor_agree_on_coordinator_resolution(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_volume_entity_id: Callable[[str], str | None],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """The number and sensor platforms must never disagree about the coordinator.

    Both consume group_resolution.resolve_group_coordinator_entity_id --
    this is a regression guard against the two platforms drifting apart
    if one is ever edited to resolve membership independently.
    """
    p1 = create_sonos_player("room_one", "RINCON_ONE", group_members=[])
    p2 = create_sonos_player("room_two", "RINCON_TWO", group_members=[])
    members = [p1, p2]
    hass.states.async_set(
        p1, "playing", {"volume_level": 0.3, "group_members": members}
    )
    hass.states.async_set(
        p2, "playing", {"volume_level": 0.7, "group_members": members}
    )
    await setup_integration()

    coordinator_entity_id = resolve_group_coordinator_entity_id(hass, p2)
    assert coordinator_entity_id == p1

    number_entity_id = group_volume_entity_id("RINCON_TWO")
    number_state = hass.states.get(number_entity_id)
    assert number_state.attributes["group_coordinator"] == coordinator_entity_id

    sensor_p1_entity_id = group_status_entity_id("RINCON_ONE")
    sensor_p2_entity_id = group_status_entity_id("RINCON_TWO")
    assert hass.states.get(sensor_p1_entity_id).state == "coordinator"
    assert hass.states.get(sensor_p2_entity_id).state == "member"
    assert (coordinator_entity_id == p1) == (
        hass.states.get(sensor_p1_entity_id).state == "coordinator"
    )
