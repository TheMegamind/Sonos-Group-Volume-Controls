"""Tests for the shared Sonos group-membership resolution helper."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.sonos_group_volume_controls.group_resolution import (
    resolve_group_coordinator_entity_id,
    resolve_group_status,
)


async def test_ungrouped_resolves_self_as_coordinator(hass: HomeAssistant) -> None:
    """A player with no group members resolves as its own coordinator."""
    hass.states.async_set("media_player.solo", "playing", {"group_members": []})

    assert (
        resolve_group_coordinator_entity_id(hass, "media_player.solo")
        == "media_player.solo"
    )
    assert resolve_group_status(hass, "media_player.solo") == "ungrouped"


async def test_coordinator_resolves_when_first_in_group_members(
    hass: HomeAssistant,
) -> None:
    """The player at group_members[0] resolves as coordinator."""
    members = ["media_player.one", "media_player.two"]
    hass.states.async_set("media_player.one", "playing", {"group_members": members})

    assert (
        resolve_group_coordinator_entity_id(hass, "media_player.one")
        == "media_player.one"
    )
    assert resolve_group_status(hass, "media_player.one") == "coordinator"


async def test_member_resolves_when_not_first_in_group_members(
    hass: HomeAssistant,
) -> None:
    """A player after group_members[0] resolves as a member, not coordinator."""
    members = ["media_player.one", "media_player.two"]
    hass.states.async_set("media_player.two", "playing", {"group_members": members})

    assert (
        resolve_group_coordinator_entity_id(hass, "media_player.two")
        == "media_player.one"
    )
    assert resolve_group_status(hass, "media_player.two") == "member"


async def test_resolution_is_freshly_read_not_cached(hass: HomeAssistant) -> None:
    """Resolution reflects the current state on every call -- no caching."""
    members = ["media_player.one", "media_player.two"]
    hass.states.async_set("media_player.two", "playing", {"group_members": members})
    assert resolve_group_status(hass, "media_player.two") == "member"

    hass.states.async_set("media_player.two", "playing", {"group_members": []})

    assert resolve_group_status(hass, "media_player.two") == "ungrouped"
    assert (
        resolve_group_coordinator_entity_id(hass, "media_player.two")
        == "media_player.two"
    )


async def test_missing_target_state_resolves_as_ungrouped(hass: HomeAssistant) -> None:
    """A target with no state at all resolves as ungrouped / self-coordinator."""
    assert resolve_group_status(hass, "media_player.missing") == "ungrouped"
    assert (
        resolve_group_coordinator_entity_id(hass, "media_player.missing")
        == "media_player.missing"
    )
