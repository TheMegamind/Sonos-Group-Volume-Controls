"""Tests for the Sonos Group Volume Controls sensor platform."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

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


async def test_sensor_attribute_agrees_with_group_resolution(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """The sensor's group_coordinator attribute must agree with group_resolution.

    Coordinator resolution now lives solely on SonosGroupStatusSensor -- the
    number platform no longer resolves or exposes it (see test_number.py's
    test_group_coordinator_attributes_not_exposed). This guards against the
    sensor's extra_state_attributes drifting from
    group_resolution.resolve_group_coordinator_entity_id, and against its
    "coordinator"/"member" enum state drifting from that same resolution,
    if the property is ever edited to compute membership independently.
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

    sensor_p1_entity_id = group_status_entity_id("RINCON_ONE")
    sensor_p2_entity_id = group_status_entity_id("RINCON_TWO")

    assert hass.states.get(sensor_p1_entity_id).state == "coordinator"
    assert hass.states.get(sensor_p2_entity_id).state == "member"
    assert (
        hass.states.get(sensor_p2_entity_id).attributes["group_coordinator"]
        == coordinator_entity_id
    )


async def test_group_name_format_when_grouped(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """group_name is '{coordinator friendly_name} +{count}', count excludes the coordinator."""
    p1 = create_sonos_player("office", "RINCON_OFFICE", group_members=[])
    p2 = create_sonos_player("room_two", "RINCON_TWO", group_members=[])
    p3 = create_sonos_player("room_three", "RINCON_THREE", group_members=[])
    p4 = create_sonos_player("room_four", "RINCON_FOUR", group_members=[])
    p5 = create_sonos_player("room_five", "RINCON_FIVE", group_members=[])
    members = [p1, p2, p3, p4, p5]
    hass.states.async_set(
        p1, "playing", {"group_members": members, "friendly_name": "Sonos Office"}
    )
    for member in (p2, p3, p4, p5):
        hass.states.async_set(member, "playing", {"group_members": members})
    await setup_integration()

    entity_id = group_status_entity_id("RINCON_FIVE")
    state = hass.states.get(entity_id)
    assert state.attributes["group_coordinator"] == p1
    assert state.attributes["group_coordinator_name"] == "Sonos Office"
    assert state.attributes["group_name"] == "Sonos Office +4"


async def test_group_name_format_when_ungrouped(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """group_name for an ungrouped player is just its own friendly_name."""
    p1 = create_sonos_player("guest_room", "RINCON_GUEST", group_members=[])
    hass.states.async_set(
        p1, "playing", {"group_members": [], "friendly_name": "Sonos Guest Room"}
    )
    await setup_integration()

    entity_id = group_status_entity_id("RINCON_GUEST")
    state = hass.states.get(entity_id)
    assert state.attributes["group_coordinator"] == p1
    assert state.attributes["group_coordinator_name"] == "Sonos Guest Room"
    assert state.attributes["group_name"] == "Sonos Guest Room"


async def test_group_attributes_identical_across_members(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """group_coordinator/_name/group_name must match across every member's sensor.

    group_name is always built from the coordinator's name and the full
    group's member count, not speaker-relative, so it must not vary by
    which member's sensor is read.
    """
    p1 = create_sonos_player("room_one", "RINCON_ONE", group_members=[])
    p2 = create_sonos_player("room_two", "RINCON_TWO", group_members=[])
    p3 = create_sonos_player("room_three", "RINCON_THREE", group_members=[])
    members = [p1, p2, p3]
    hass.states.async_set(
        p1, "playing", {"group_members": members, "friendly_name": "Sonos Office"}
    )
    hass.states.async_set(p2, "playing", {"group_members": members})
    hass.states.async_set(p3, "playing", {"group_members": members})
    await setup_integration()

    state_p2 = hass.states.get(group_status_entity_id("RINCON_TWO"))
    state_p3 = hass.states.get(group_status_entity_id("RINCON_THREE"))

    for key in ("group_coordinator", "group_coordinator_name", "group_name"):
        assert state_p2.attributes[key] == state_p3.attributes[key]


async def test_group_attributes_update_after_group_change(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """All three coordinator/group attributes recompute immediately after membership changes."""
    p1 = create_sonos_player("room_one", "RINCON_ONE", group_members=[])
    p2 = create_sonos_player("room_two", "RINCON_TWO", group_members=[])
    members = [p1, p2]
    hass.states.async_set(
        p1, "playing", {"group_members": members, "friendly_name": "Room One"}
    )
    hass.states.async_set(
        p2, "playing", {"group_members": members, "friendly_name": "Room Two"}
    )
    await setup_integration()
    entity_id = group_status_entity_id("RINCON_TWO")
    state = hass.states.get(entity_id)
    assert state.attributes["group_coordinator"] == p1
    assert state.attributes["group_coordinator_name"] == "Room One"
    assert state.attributes["group_name"] == "Room One +1"

    hass.states.async_set(
        p2, "playing", {"group_members": [], "friendly_name": "Room Two"}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["group_coordinator"] == p2
    assert state.attributes["group_coordinator_name"] == "Room Two"
    assert state.attributes["group_name"] == "Room Two"


async def test_group_attributes_fallback_when_coordinator_unavailable(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """group_coordinator_name/group_name fall back to None if the coordinator is unavailable.

    SonosGroupStatusSensor tracks its resolved coordinator in addition to
    its own target entity, so p1 (the coordinator) going unavailable must
    by itself push a repaint of p2's sensor -- no unrelated nudge to p2's
    own state required.
    """
    p1 = create_sonos_player("room_one", "RINCON_ONE", group_members=[])
    p2 = create_sonos_player("room_two", "RINCON_TWO", group_members=[])
    members = [p1, p2]
    hass.states.async_set(
        p1, "playing", {"group_members": members, "friendly_name": "Room One"}
    )
    hass.states.async_set(
        p2, "playing", {"group_members": members, "friendly_name": "Room Two"}
    )
    await setup_integration()
    entity_id = group_status_entity_id("RINCON_TWO")
    state = hass.states.get(entity_id)
    assert state.attributes["group_coordinator_name"] == "Room One"
    assert state.attributes["group_name"] == "Room One +1"

    hass.states.async_set(p1, "unavailable", {"group_members": members})
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["group_coordinator"] == p1
    assert state.attributes["group_coordinator_name"] is None
    assert state.attributes["group_name"] is None


async def test_group_status_entity_attaches_to_target_device(
    hass: HomeAssistant,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """The group status entity attaches to the target speaker's own device.

    Regression guard: building DeviceInfo from a copy of the target device's
    identifiers/connections forks a duplicate device row under our config
    entry instead of nesting onto the speaker's native device card. The
    entity must instead resolve onto the same device row as the target.
    """
    target_entity_id = create_sonos_player("room_one", "RINCON_ONE", group_members=[])
    await setup_integration()

    entity_registry = er.async_get(hass)
    target_device_id = entity_registry.entities[target_entity_id].device_id
    assert target_device_id is not None

    entity_id = group_status_entity_id("RINCON_ONE")
    assert entity_id is not None
    assert entity_registry.entities[entity_id].device_id == target_device_id

    device_registry = dr.async_get(hass)
    assert len(device_registry.devices) == 1


async def test_group_status_entity_follows_target_device_after_recreation(
    hass: HomeAssistant,
    sonos_config_entry: MockConfigEntry,
    create_sonos_player: Callable[..., str],
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
    group_status_entity_id: Callable[[str], str | None],
) -> None:
    """The entity re-attaches to a recreated target device after a reload.

    Regression guard for the scenario that broke device attachment: the
    native sonos integration recreates a speaker's device row (e.g. after a
    firmware update), and our entity's attachment must follow the target to
    its new device rather than remaining pinned to whichever device existed
    when our entity was first created.
    """
    target_entity_id = create_sonos_player("room_one", "RINCON_ONE", group_members=[])
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

    entity_id = group_status_entity_id("RINCON_ONE")
    assert entity_id is not None
    assert entity_registry.entities[entity_id].device_id == new_device.id
    assert entity_registry.entities[entity_id].device_id != original_device_id
