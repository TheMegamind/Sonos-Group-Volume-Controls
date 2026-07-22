"""Sensor platform for Sonos Group Volume Controls."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
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

from .const import GROUP_STATUS_UNIQUE_ID_SUFFIX, MEDIA_PLAYER_DOMAIN, SONOS_PLATFORM
from .group_resolution import (
    GROUP_STATUS_COORDINATOR,
    GROUP_STATUS_MEMBER,
    GROUP_STATUS_UNGROUPED,
    resolve_group_status,
)


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
    """Set up Sonos Group Volume Controls sensor entities."""
    entity_registry = er.async_get(hass)
    entity_map: dict[str, SonosGroupStatusSensor] = {}

    def _build_entity(target_entry: er.RegistryEntry) -> SonosGroupStatusSensor:
        group_status_entity = SonosGroupStatusSensor(
            target_entity_id=target_entry.entity_id,
            unique_id=f"{target_entry.unique_id}{GROUP_STATUS_UNIQUE_ID_SUFFIX}",
            device_info=_device_info_for_target(hass, target_entry),
        )
        entity_map[target_entry.entity_id] = group_status_entity
        return group_status_entity

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
            group_status_entity = entity_map.pop(target_entity_id, None)
            if group_status_entity is None or group_status_entity.entity_id is None:
                return
            entity_registry.async_remove(group_status_entity.entity_id)

    entry.async_on_unload(
        hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _handle_registry_event)
    )

    initial_entities = [
        _build_entity(target_entry)
        for target_entry in list(entity_registry.entities.values())
        if _is_sonos_media_player(target_entry)
    ]
    async_add_entities(initial_entities)


class SonosGroupStatusSensor(SensorEntity):
    """Sensor entity reflecting a Sonos player's group membership role."""

    _attr_has_entity_name = True
    _attr_translation_key = "group_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        GROUP_STATUS_COORDINATOR,
        GROUP_STATUS_MEMBER,
        GROUP_STATUS_UNGROUPED,
    ]
    _attr_should_poll = False

    def __init__(
        self,
        target_entity_id: str,
        unique_id: str,
        device_info: DeviceInfo | None,
    ) -> None:
        """Initialize the group status entity."""
        self._target_entity_id = target_entity_id
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._attr_available = False
        self._attr_native_value = None
        self._unsub_tracking: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        """Start tracking the target entity and compute initial state."""
        await super().async_added_to_hass()
        self._unsub_tracking = async_track_state_change_event(
            self.hass, [self._target_entity_id], self._handle_tracked_state_change
        )
        self._async_recompute()

    async def async_will_remove_from_hass(self) -> None:
        """Stop tracking state changes."""
        if self._unsub_tracking is not None:
            self._unsub_tracking()
            self._unsub_tracking = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_tracked_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Recompute and publish state on any target state change."""
        self._async_recompute()
        self.async_write_ha_state()

    @callback
    def _async_recompute(self) -> None:
        """Recompute native_value from current group membership."""
        target_state = self.hass.states.get(self._target_entity_id)
        if target_state is None or target_state.state == STATE_UNAVAILABLE:
            self._attr_available = False
            self._attr_native_value = None
            return

        self._attr_available = True
        self._attr_native_value = resolve_group_status(
            self.hass, self._target_entity_id
        )
