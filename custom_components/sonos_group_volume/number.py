"""Number platform for Sonos Group Volume."""

from __future__ import annotations

import asyncio

from homeassistant.components.media_player.const import (
    ATTR_GROUP_MEMBERS,
    ATTR_MEDIA_VOLUME_LEVEL,
)
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_VOLUME_SET, STATE_UNAVAILABLE
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import MEDIA_PLAYER_DOMAIN, SONOS_PLATFORM, UNIQUE_ID_SUFFIX


def _is_sonos_media_player(entry: er.RegistryEntry) -> bool:
    """Return True if the registry entry is a Sonos media_player."""
    return entry.domain == MEDIA_PLAYER_DOMAIN and entry.platform == SONOS_PLATFORM


def _device_info_for_target(
    hass: HomeAssistant, target_entry: er.RegistryEntry
) -> DeviceInfo | None:
    """Build DeviceInfo that nests the new entity into the target's device."""
    if target_entry.device_id is None:
        return None
    device = dr.async_get(hass).async_get(target_entry.device_id)
    if device is None:
        return None
    return DeviceInfo(
        identifiers=device.identifiers,
        connections=device.connections,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sonos Group Volume number entities."""
    entity_registry = er.async_get(hass)
    entity_map: dict[str, SonosGroupVolumeNumber] = {}

    def _build_entity(target_entry: er.RegistryEntry) -> SonosGroupVolumeNumber:
        group_volume_entity = SonosGroupVolumeNumber(
            target_entity_id=target_entry.entity_id,
            unique_id=f"{target_entry.unique_id}{UNIQUE_ID_SUFFIX}",
            device_info=_device_info_for_target(hass, target_entry),
        )
        entity_map[target_entry.entity_id] = group_volume_entity
        return group_volume_entity

    @callback
    def _handle_registry_event(
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        target_entity_id = event.data["entity_id"]
        action = event.data["action"]

        if action == "create":
            if target_entity_id in entity_map:
                return
            target_entry = entity_registry.async_get(target_entity_id)
            if target_entry is None or not _is_sonos_media_player(target_entry):
                return
            async_add_entities([_build_entity(target_entry)])
            return

        if action == "remove":
            group_volume_entity = entity_map.pop(target_entity_id, None)
            if group_volume_entity is None or group_volume_entity.entity_id is None:
                return
            entity_registry.async_remove(group_volume_entity.entity_id)

    entry.async_on_unload(
        hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _handle_registry_event)
    )

    initial_entities = [
        _build_entity(target_entry)
        for target_entry in list(entity_registry.entities.values())
        if _is_sonos_media_player(target_entry)
    ]
    async_add_entities(initial_entities)


class SonosGroupVolumeNumber(NumberEntity):
    """Number entity reflecting and controlling a Sonos group's average volume."""

    _attr_has_entity_name = True
    _attr_translation_key = "group_volume"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_should_poll = False

    def __init__(
        self,
        target_entity_id: str,
        unique_id: str,
        device_info: DeviceInfo | None,
    ) -> None:
        """Initialize the group volume entity."""
        self._target_entity_id = target_entity_id
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._attr_available = False
        self._attr_native_value = None
        self._tracked_entity_ids: set[str] = set()
        self._unsub_tracking: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        """Start tracking the target and its group members."""
        await super().async_added_to_hass()
        self._async_recompute()

    async def async_will_remove_from_hass(self) -> None:
        """Stop tracking state changes."""
        if self._unsub_tracking is not None:
            self._unsub_tracking()
            self._unsub_tracking = None
        await super().async_will_remove_from_hass()

    def _member_volume_level(self, entity_id: str) -> float | None:
        """Return a member's volume_level, or None if unavailable."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state == STATE_UNAVAILABLE:
            return None
        level = state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL)
        if level is None:
            return None
        return float(level)

    def _retrack(self, entity_ids: set[str]) -> None:
        """Resubscribe state tracking if the tracked entity set changed."""
        if entity_ids == self._tracked_entity_ids:
            return
        if self._unsub_tracking is not None:
            self._unsub_tracking()
        self._tracked_entity_ids = entity_ids
        self._unsub_tracking = async_track_state_change_event(
            self.hass, list(entity_ids), self._handle_tracked_state_change
        )

    @callback
    def _handle_tracked_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Recompute and publish state on any tracked entity change."""
        self._async_recompute()
        self.async_write_ha_state()

    @callback
    def _async_recompute(self) -> None:
        """Recompute native_value from current group membership and volumes."""
        target_state = self.hass.states.get(self._target_entity_id)
        if target_state is None or target_state.state == STATE_UNAVAILABLE:
            self._retrack({self._target_entity_id})
            self._attr_available = False
            self._attr_native_value = None
            return

        members = list(target_state.attributes.get(ATTR_GROUP_MEMBERS) or [])
        self._retrack(set(members) | {self._target_entity_id})

        if len(members) <= 1:
            level = self._member_volume_level(self._target_entity_id)
            self._attr_available = level is not None
            self._attr_native_value = None if level is None else int(level * 100)
            return

        levels = [
            lv for m in members if (lv := self._member_volume_level(m)) is not None
        ]
        self._attr_available = bool(levels)
        self._attr_native_value = (
            int((sum(levels) / len(levels)) * 100) if levels else None
        )

    async def _async_call_volume_set(self, entity_id: str, volume: float) -> None:
        """Call media_player.volume_set for a single member entity."""
        await self.hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_SET,
            {ATTR_ENTITY_ID: entity_id, ATTR_MEDIA_VOLUME_LEVEL: volume},
            blocking=True,
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the group volume, scaling members proportionally."""
        target = value / 100

        target_state = self.hass.states.get(self._target_entity_id)
        if target_state is None:
            return
        members = list(target_state.attributes.get(ATTR_GROUP_MEMBERS) or [])

        if len(members) <= 1:
            await self._async_call_volume_set(self._target_entity_id, target)
            return

        current_levels = {
            m: lv for m in members if (lv := self._member_volume_level(m)) is not None
        }
        if not current_levels:
            return

        current_avg = sum(current_levels.values()) / len(current_levels)

        if current_avg == 0:
            # Scale factor undefined at zero — set every member to the
            # target directly rather than proportionally.
            await asyncio.gather(
                *[
                    self._async_call_volume_set(m, target)
                    for m in current_levels
                ]
            )
            return

        scale = target / current_avg
        await asyncio.gather(
            *[
                self._async_call_volume_set(m, min(1.0, max(0.0, lv * scale)))
                for m, lv in current_levels.items()
            ]
        )
