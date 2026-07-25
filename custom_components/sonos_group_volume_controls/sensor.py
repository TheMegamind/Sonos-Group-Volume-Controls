"""Sensor platform for Sonos Group Volume Controls."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_UNAVAILABLE
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

from .const import (
    ATTR_GROUP_COORDINATOR,
    ATTR_GROUP_COORDINATOR_NAME,
    ATTR_GROUP_NAME,
    GROUP_STATUS_UNIQUE_ID_SUFFIX,
    MEDIA_PLAYER_DOMAIN,
    SONOS_PLATFORM,
)
from .group_resolution import (
    GROUP_STATUS_COORDINATOR,
    GROUP_STATUS_MEMBER,
    GROUP_STATUS_UNGROUPED,
    resolve_group_coordinator_entity_id,
    resolve_group_members,
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
        self._tracked_entity_ids: set[str] = set()
        self._unsub_tracking: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        """Start tracking the target and its resolved coordinator, and compute initial state."""
        await super().async_added_to_hass()
        self._async_recompute()

    async def async_will_remove_from_hass(self) -> None:
        """Stop tracking state changes."""
        if self._unsub_tracking is not None:
            self._unsub_tracking()
            self._unsub_tracking = None
        await super().async_will_remove_from_hass()

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
        """Recompute native_value from current group membership."""
        target_state = self.hass.states.get(self._target_entity_id)
        if target_state is None or target_state.state == STATE_UNAVAILABLE:
            self._retrack({self._target_entity_id})
            self._attr_available = False
            self._attr_native_value = None
            return

        coordinator_entity_id = resolve_group_coordinator_entity_id(
            self.hass, self._target_entity_id
        )
        self._retrack({self._target_entity_id, coordinator_entity_id})

        self._attr_available = True
        self._attr_native_value = resolve_group_status(
            self.hass, self._target_entity_id
        )

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return the resolved group coordinator's entity_id, name, and group name."""
        coordinator_entity_id = resolve_group_coordinator_entity_id(
            self.hass, self._target_entity_id
        )
        coordinator_state = self.hass.states.get(coordinator_entity_id)
        coordinator_name = (
            coordinator_state.attributes.get(ATTR_FRIENDLY_NAME)
            if coordinator_state is not None
            and coordinator_state.state != STATE_UNAVAILABLE
            else None
        )

        members = resolve_group_members(self.hass, self._target_entity_id)
        if len(members) > 1:
            # Always built from the coordinator's name and the full group's
            # member count, not speaker-relative, so this is identical
            # across every member of the group.
            group_name = (
                f"{coordinator_name} +{len(members) - 1}"
                if coordinator_name is not None
                else None
            )
        else:
            own_state = self.hass.states.get(self._target_entity_id)
            group_name = (
                own_state.attributes.get(ATTR_FRIENDLY_NAME)
                if own_state is not None and own_state.state != STATE_UNAVAILABLE
                else None
            )

        return {
            ATTR_GROUP_COORDINATOR: coordinator_entity_id,
            ATTR_GROUP_COORDINATOR_NAME: coordinator_name,
            ATTR_GROUP_NAME: group_name,
        }
