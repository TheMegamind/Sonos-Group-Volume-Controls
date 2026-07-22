"""Shared Sonos group-membership resolution.

group_members[0] is guaranteed to be the coordinator: the sonos
integration's SonosSpeaker._async_regroup only runs on the speaker
that IS the coordinator (guarded by `self.soco.uid == group[0]` in
_async_handle_group_event), and it builds sonos_group_entities by
iterating the same `group` list index-for-index, so entry 0 is
always that speaker's own entity_id.
"""

from __future__ import annotations

from homeassistant.components.media_player.const import ATTR_GROUP_MEMBERS
from homeassistant.core import HomeAssistant

GROUP_STATUS_COORDINATOR = "coordinator"
GROUP_STATUS_MEMBER = "member"
GROUP_STATUS_UNGROUPED = "ungrouped"


def resolve_group_members(hass: HomeAssistant, target_entity_id: str) -> list[str]:
    """Return the target's current group_members, freshly read (no caching)."""
    target_state = hass.states.get(target_entity_id)
    if target_state is None:
        return []
    return list(target_state.attributes.get(ATTR_GROUP_MEMBERS) or [])


def resolve_group_coordinator_entity_id(
    hass: HomeAssistant, target_entity_id: str
) -> str:
    """Return the entity_id of the group coordinator, freshly resolved."""
    members = resolve_group_members(hass, target_entity_id)
    if len(members) <= 1:
        return target_entity_id
    return members[0]


def resolve_group_status(hass: HomeAssistant, target_entity_id: str) -> str:
    """Return "coordinator", "member", or "ungrouped" for the target."""
    members = resolve_group_members(hass, target_entity_id)
    if len(members) <= 1:
        return GROUP_STATUS_UNGROUPED
    if members[0] == target_entity_id:
        return GROUP_STATUS_COORDINATOR
    return GROUP_STATUS_MEMBER
