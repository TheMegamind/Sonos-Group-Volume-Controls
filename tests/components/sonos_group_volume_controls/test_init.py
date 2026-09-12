"""Tests for Sonos Group Volume Controls integration setup and unload."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sonos_group_volume_controls import (
    async_remove_config_entry_device,
)
from custom_components.sonos_group_volume_controls.const import DOMAIN


async def test_setup_and_unload_entry(hass: HomeAssistant) -> None:
    """The config entry loads and unloads cleanly with no Sonos players."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_async_remove_config_entry_device_returns_true_when_no_entities_attached(
    hass: HomeAssistant,
) -> None:
    """A device with none of our entities attached is safe to detach."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "orphan")},
        name="Orphan Device",
    )

    assert await async_remove_config_entry_device(hass, entry, device)


async def test_async_remove_config_entry_device_returns_false_when_entity_attached(
    hass: HomeAssistant,
) -> None:
    """A device with one of our entities still attached must not be removed."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "occupied")},
        name="Occupied Device",
    )
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "occupied_unique_id",
        config_entry=entry,
        device_id=device.id,
    )

    assert not await async_remove_config_entry_device(hass, entry, device)


async def test_setup_cleans_up_orphaned_device_owned_by_this_entry(
    hass: HomeAssistant,
) -> None:
    """Setup removes a leftover device this entry owns with no entities left.

    Regression guard for legacy device rows forked by the pre-v0.1.7 bug:
    a device attributed to this config entry with zero of our entities
    attached is cleaned up automatically on the next setup/reload.
    """
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    orphan_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "orphan")},
        name="Orphan Device",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get(orphan_device.id) is None


async def test_setup_does_not_touch_device_owned_by_another_config_entry(
    hass: HomeAssistant,
) -> None:
    """Setup never removes a device owned by a different config entry.

    Regression guard: the cleanup scan is scoped to devices owned by this
    config entry only, so the native sonos integration's own (empty from
    our point of view) device must survive.
    """
    sonos_entry = MockConfigEntry(domain="sonos")
    sonos_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    sonos_device = device_registry.async_get_or_create(
        config_entry_id=sonos_entry.entry_id,
        identifiers={("sonos", "RINCON_UNTOUCHED")},
        name="Untouched Speaker",
    )

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get(sonos_device.id) is not None


async def test_setup_does_not_remove_device_repopulated_same_setup_pass(
    hass: HomeAssistant,
) -> None:
    """Cleanup does not remove a device that already has one of our entities.

    Ordering regression guard: the cleanup scan must run against entity
    registry state as it stands *after* platform setup completes, not a
    snapshot taken beforehand -- otherwise a device that gains one of our
    entities during this very setup pass would be mistaken for abandoned
    and wrongly removed.
    """
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "repopulated")},
        name="Repopulated Device",
    )
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "repopulated_unique_id",
        config_entry=entry,
        device_id=device.id,
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get(device.id) is not None
