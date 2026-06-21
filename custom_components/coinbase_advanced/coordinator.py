"""Data coordinator for the Coinbase Advanced custom integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    CoinbaseAdvancedApi,
    CoinbaseAdvancedAuthError,
    CoinbaseAdvancedConnectionError,
    CoinbaseSnapshot,
)
from .const import (
    CONF_EXCHANGE_BASE,
    CONF_INCLUDE_PORTFOLIO_BREAKDOWN,
    CONF_INCLUDE_TRANSACTION_SUMMARY,
    CONF_POLL_INTERVAL,
    CONF_PRODUCTS,
    DEFAULT_EXCHANGE_BASE,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MIN_POLL_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class CoinbaseAdvancedRuntimeData:
    """Runtime data attached to the config entry."""

    api: CoinbaseAdvancedApi
    coordinator: CoinbaseAdvancedCoordinator


class CoinbaseAdvancedCoordinator(DataUpdateCoordinator[CoinbaseSnapshot]):
    """Fetch Coinbase data in one throttled coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: CoinbaseAdvancedApi,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.config_entry = entry
        update_interval_seconds = max(
            int(entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)),
            MIN_POLL_INTERVAL,
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval_seconds),
        )

    async def _async_update_data(self) -> CoinbaseSnapshot:
        """Fetch data from Coinbase."""
        product_ids: list[str] = self.config_entry.options.get(CONF_PRODUCTS, [])
        exchange_base = self.config_entry.options.get(
            CONF_EXCHANGE_BASE, DEFAULT_EXCHANGE_BASE
        )
        include_transaction_summary = bool(
            self.config_entry.options.get(CONF_INCLUDE_TRANSACTION_SUMMARY, False)
        )
        include_portfolio_breakdown = bool(
            self.config_entry.options.get(CONF_INCLUDE_PORTFOLIO_BREAKDOWN, True)
        )

        try:
            return await self.hass.async_add_executor_job(
                lambda: self.api.fetch_snapshot(
                    product_ids=product_ids,
                    exchange_base=exchange_base,
                    include_exchange_rates=True,
                    include_transaction_summary=include_transaction_summary,
                    include_portfolio_breakdown=include_portfolio_breakdown,
                )
            )
        except CoinbaseAdvancedAuthError as error:
            raise ConfigEntryAuthFailed(f"Authentication failed: {error}") from error
        except CoinbaseAdvancedConnectionError as error:
            raise UpdateFailed(f"Coinbase update failed: {error}") from error
        except Exception as error:
            raise UpdateFailed(f"Unexpected Coinbase update error: {error}") from error
