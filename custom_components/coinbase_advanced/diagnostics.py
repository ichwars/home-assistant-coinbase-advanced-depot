"""Diagnostics support for the Coinbase Advanced custom integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, CONF_ID
from homeassistant.core import HomeAssistant

from .api import CoinbaseSnapshot, portfolio_spot_positions
from .const import (
    API_ACCOUNTS,
    API_AVAILABLE_BALANCE,
    API_HOLD,
    API_ID,
    API_NAME,
    API_TYPE,
    API_UUID,
)

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


PORTFOLIO_POSITION_SECTIONS = (
    "spot_positions",
    "perp_positions",
    "futures_positions",
    "prediction_markets_positions",
    "equity_positions",
)


def _portfolio_metadata(snapshot: CoinbaseSnapshot | None) -> list[dict[str, Any]]:
    """Return compact portfolio metadata for diagnostics."""
    if snapshot is None:
        return []
    return [
        {
            API_NAME: portfolio.get(API_NAME),
            API_UUID: portfolio.get(API_UUID),
            API_TYPE: portfolio.get(API_TYPE),
            "deleted": portfolio.get("deleted"),
        }
        for portfolio in snapshot.portfolios
    ]


def _portfolio_breakdown_sections(
    snapshot: CoinbaseSnapshot | None,
) -> dict[str, int]:
    """Return counts for portfolio breakdown sections."""
    counts = {section: 0 for section in PORTFOLIO_POSITION_SECTIONS}
    if snapshot is None:
        return counts

    for breakdown in snapshot.portfolio_breakdowns:
        for section in PORTFOLIO_POSITION_SECTIONS:
            positions = breakdown.get(section, [])
            if isinstance(positions, list):
                counts[section] += len(positions)
    return counts


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
                "portfolio_metadata": _portfolio_metadata(snapshot),
                "has_portfolio_breakdowns": bool(
                    snapshot and snapshot.portfolio_breakdowns
                ),
                "portfolio_breakdown_sections": _portfolio_breakdown_sections(snapshot),
                "portfolio_position_count": len(
                    portfolio_spot_positions(snapshot.portfolio_breakdowns)
                    if snapshot
                    else []
                ),
                "has_exchange_rates": bool(snapshot and snapshot.exchange_rates),
                "has_transaction_summary": bool(snapshot and snapshot.transaction_summary),
                "rate_limit_headers": snapshot.rate_limit_headers if snapshot else {},
            },
        },
        TO_REDACT,
    )
