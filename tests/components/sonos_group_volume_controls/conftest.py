"""Fixtures for Sonos Group Volume Controls tests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.sonos_group_volume_controls.const import DOMAIN, UNIQUE_ID_SUFFIX


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Make this repo's custom_components loadable in every test."""


@pytest.fixture
def sonos_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Stand in for the core sonos integration's config entry."""
    entry = MockConfigEntry(domain="sonos")
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def create_sonos_player(
    hass: HomeAssistant, sonos_config_entry: MockConfigEntry
) -> Callable[..., str]:
    """Return a factory that registers a fake Sonos media_player entity."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    def _create(
        object_id: str,
        unique_id: str,
        *,
        volume_level: float | None = 0.5,
        group_members: list[str] | None = None,
        available: bool = True,
    ) -> str:
        device_entry = device_registry.async_get_or_create(
            config_entry_id=sonos_config_entry.entry_id,
            identifiers={("sonos", unique_id)},
            name=object_id.replace("_", " ").title(),
        )
        entity_entry = entity_registry.async_get_or_create(
            "media_player",
            "sonos",
            unique_id,
            config_entry=sonos_config_entry,
            device_id=device_entry.id,
            suggested_object_id=object_id,
        )
        attributes: dict[str, object] = {}
        if group_members is not None:
            attributes["group_members"] = group_members
        if volume_level is not None:
            attributes["volume_level"] = volume_level
        hass.states.async_set(
            entity_entry.entity_id,
            "unavailable" if not available else "playing",
            attributes,
        )
        return entity_entry.entity_id

    return _create


@pytest.fixture
def setup_integration(hass: HomeAssistant) -> Callable[[], Awaitable[MockConfigEntry]]:
    """Return a factory that sets up the sonos_group_volume_controls config entry."""

    async def _setup() -> MockConfigEntry:
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return _setup


@pytest.fixture
def group_volume_entity_id(hass: HomeAssistant) -> Callable[[str], str | None]:
    """Return a lookup from a target unique_id to its group volume entity_id."""
    entity_registry = er.async_get(hass)

    def _lookup(target_unique_id: str) -> str | None:
        return entity_registry.async_get_entity_id(
            "number", DOMAIN, f"{target_unique_id}{UNIQUE_ID_SUFFIX}"
        )

    return _lookup
