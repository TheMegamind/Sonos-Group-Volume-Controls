"""The Sonos Group Volume Controls integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

PLATFORMS = [Platform.NUMBER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sonos Group Volume Controls from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_cleanup_orphaned_devices(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow removing a device once none of our entities are attached to it."""
    entity_registry = er.async_get(hass)
    return not _device_has_entry_entities(entity_registry, entry, device_entry.id)


@callback
def _device_has_entry_entities(
    entity_registry: er.EntityRegistry, entry: ConfigEntry, device_id: str
) -> bool:
    """Return True if an entity registered under this config entry uses the device."""
    return any(
        registry_entry.config_entry_id == entry.entry_id
        for registry_entry in er.async_entries_for_device(
            entity_registry, device_id, include_disabled_entities=True
        )
    )


@callback
def _async_cleanup_orphaned_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove devices owned by this entry that no longer have any of our entities.

    Runs after platform setup completes so a device about to be repopulated
    this same pass is never mistaken for abandoned. This cleans up device
    rows left over from before entities attached directly to the target
    speaker's device (see v0.1.7), and guards against a future
    device-registry reshuffle producing the same kind of orphan.
    """
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if not _device_has_entry_entities(entity_registry, entry, device_entry.id):
            device_registry.async_remove_device(device_entry.id)
