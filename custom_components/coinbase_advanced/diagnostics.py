"""Diagnostics support for the Coinbase Advanced custom integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, CONF_ID
from homeassistant.core import HomeAssistant

from .api import portfolio_spot_positions
from .const import API_ACCOUNTS, API_AVAILABLE_BALANCE, API_HOLD, API_ID, API_UUID

TO_REDACT = {
    CONF_API_KEY,
    CONF_API_TOKEN,
    CONF_ID,
    API_ID,
    API_UUID,
    API_AVAILABLE_BALANCE,
    API_HOLD,
    "resource_path",
    "amount",
    "account_id",
}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = getattr(entry, "runtime_data", None)
    snapshot = runtime_data.coordinator.data if runtime_data else None
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "snapshot": {
                API_ACCOUNTS: snapshot.accounts if snapshot else [],
                "products": snapshot.products if snapshot else {},
                "portfolios": snapshot.portfolios if snapshot else [],
                "has_portfolio_breakdowns": bool(
                    snapshot and snapshot.portfolio_breakdowns
                ),
                "portfolio_position_count": len(
                    portfolio_spot_positions(snapshot.portfolio_breakdowns)
                    if snapshot
                    else []
                ),
                "has_exchange_rates": bool(snapshot and snapshot.exchange_rates),
                "has_transaction_summary": bool(snapshot and snapshot.transaction_summary),
            },
        },
        TO_REDACT,
    )
