"""Tests for the Sonos Group Volume Controls config flow."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.sonos_group_volume_controls.const import DOMAIN


async def test_user_flow_creates_single_entry(hass: HomeAssistant) -> None:
    """The zero-field confirmation step creates the config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sonos Group Volume Controls"


async def test_second_instance_is_aborted(hass: HomeAssistant) -> None:
    """A second config entry is rejected since only one instance is allowed."""
    existing_entry = MockConfigEntry(domain=DOMAIN)
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
