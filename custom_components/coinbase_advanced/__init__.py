"""Coinbase Advanced custom integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant, ServiceCall

try:
    from homeassistant.core import SupportsResponse
except ImportError:  # Older Home Assistant versions
    SupportsResponse = None
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import (
    CoinbaseAdvancedApi,
    CoinbaseAdvancedAuthError,
    CoinbaseAdvancedConnectionError,
    CoinbaseAdvancedError,
)
from .const import (
    ATTR_ENTRY_ID,
    ATTR_PARAMS,
    ATTR_PATH,
    DOMAIN,
    SERVICE_API_CALL,
    SERVICE_REFRESH,
)
from .coordinator import CoinbaseAdvancedCoordinator, CoinbaseAdvancedRuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

CoinbaseAdvancedConfigEntry = ConfigEntry


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Coinbase Advanced services."""
    _async_register_services(hass)
    return True


def _validate_api_path(path: str) -> str:
    """Validate a Coinbase REST path."""
    if not path.startswith("/") or path.startswith("//") or "://" in path:
        raise vol.Invalid("Path must be a relative path starting with '/'.")
    return path


API_CALL_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required(ATTR_PATH): vol.All(cv.string, _validate_api_path),
        vol.Optional(ATTR_PARAMS, default={}): dict,
    }
)

REFRESH_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string})


async def async_setup_entry(
    hass: HomeAssistant, entry: CoinbaseAdvancedConfigEntry
) -> bool:
    """Set up Coinbase Advanced from a config entry."""
    api = CoinbaseAdvancedApi(
        api_key=entry.data[CONF_API_KEY],
        api_secret=entry.data[CONF_API_TOKEN],
    )

    try:
        await hass.async_add_executor_job(api.validate)
    except CoinbaseAdvancedAuthError as error:
        raise ConfigEntryAuthFailed(str(error)) from error
    except CoinbaseAdvancedConnectionError as error:
        raise ConfigEntryNotReady(str(error)) from error

    coordinator = CoinbaseAdvancedCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = CoinbaseAdvancedRuntimeData(api=api, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: CoinbaseAdvancedConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _entry_from_service_call(
    hass: HomeAssistant, call: ServiceCall
) -> CoinbaseAdvancedConfigEntry:
    """Resolve a config entry from a service call."""
    entry_id = call.data.get(ATTR_ENTRY_ID)
    if entry_id:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(
                f"No Coinbase Advanced config entry found for {entry_id}."
            )
        if not getattr(entry, "runtime_data", None):
            raise ServiceValidationError(
                f"Coinbase Advanced config entry {entry_id} is not loaded."
            )
        return entry  # type: ignore[return-value]

    entries: list[CoinbaseAdvancedConfigEntry] = [
        entry  # type: ignore[misc]
        for entry in hass.config_entries.async_entries(DOMAIN)
        if getattr(entry, "runtime_data", None)
    ]
    if len(entries) == 1:
        return entries[0]
    if not entries:
        raise ServiceValidationError("No loaded Coinbase Advanced config entry found.")
    raise ServiceValidationError("Multiple Coinbase Advanced entries exist; pass entry_id.")


def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    hass.data.setdefault(DOMAIN, {})
    if hass.data[DOMAIN].get("services_registered"):
        return

    async def handle_api_call(call: ServiceCall) -> dict[str, Any]:
        """Handle a read-only Coinbase REST call and return the response."""
        entry = _entry_from_service_call(hass, call)
        runtime = entry.runtime_data
        path = call.data[ATTR_PATH]
        params = call.data.get(ATTR_PARAMS, {})

        try:
            response = await hass.async_add_executor_job(
                lambda: runtime.api.call_rest("GET", path, params=params)
            )
        except CoinbaseAdvancedAuthError as error:
            raise HomeAssistantError(f"Coinbase authentication failed: {error}") from error
        except CoinbaseAdvancedError as error:
            raise HomeAssistantError(f"Coinbase API call failed: {error}") from error

        return {"response": response}

    async def handle_refresh(call: ServiceCall) -> None:
        """Force a refresh for a config entry."""
        entry = _entry_from_service_call(hass, call)
        await entry.runtime_data.coordinator.async_request_refresh()

    api_call_kwargs: dict[str, Any] = {"schema": API_CALL_SCHEMA}
    if SupportsResponse is not None:
        api_call_kwargs["supports_response"] = SupportsResponse.ONLY
    hass.services.async_register(
        DOMAIN,
        SERVICE_API_CALL,
        handle_api_call,
        **api_call_kwargs,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        handle_refresh,
        schema=REFRESH_SCHEMA,
    )
    hass.data[DOMAIN]["services_registered"] = True
