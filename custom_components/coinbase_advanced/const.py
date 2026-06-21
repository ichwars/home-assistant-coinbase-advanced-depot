"""Constants for the Coinbase Advanced custom integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN

DOMAIN = "coinbase_advanced"
NAME = "Coinbase Advanced"

CONF_ACCOUNT_CURRENCIES = "account_balance_currencies"
CONF_PRODUCTS = "products"
CONF_EXCHANGE_RATE_CURRENCIES = "exchange_rate_currencies"
CONF_EXCHANGE_BASE = "exchange_base"
CONF_POLL_INTERVAL = "poll_interval"
CONF_INCLUDE_TRANSACTION_SUMMARY = "include_transaction_summary"
CONF_INCLUDE_ZERO_BALANCES = "include_zero_balances"
CONF_INCLUDE_PORTFOLIO_BREAKDOWN = "include_portfolio_breakdown"

DEFAULT_EXCHANGE_BASE = "USD"
DEFAULT_POLL_INTERVAL = 60
MIN_POLL_INTERVAL = 30
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_POLL_INTERVAL)

# Service names / attrs
SERVICE_API_CALL = "api_call"
SERVICE_REFRESH = "refresh"
ATTR_ENTRY_ID = "entry_id"
ATTR_PATH = "path"
ATTR_PARAMS = "params"

# Coinbase API fields used across files. Keep this list small and normalized.
API_ACCOUNTS = "accounts"
API_ACCOUNT_TYPE = "account_type"
API_ACCOUNT_UUID = "account_uuid"
API_ASSET = "asset"
API_ASSET_COLOR = "asset_color"
API_ASSET_UUID = "asset_uuid"
API_PORTFOLIOS = "portfolios"
API_PORTFOLIO_BALANCES = "portfolio_balances"
API_RATES = "rates"
API_DATA = "data"
API_CURRENCY = "currency"
API_UUID = "uuid"
API_ID = "id"
API_NAME = "name"
API_TYPE = "type"
API_AVAILABLE_BALANCE = "available_balance"
API_HOLD = "hold"
API_VALUE = "value"
API_SPOT_POSITIONS = "spot_positions"
API_ALLOCATION = "allocation"
API_AVAILABLE_TO_SEND_CRYPTO = "available_to_send_crypto"
API_AVAILABLE_TO_TRADE_CRYPTO = "available_to_trade_crypto"
API_AVAILABLE_TO_TRANSFER_CRYPTO = "available_to_transfer_crypto"
API_AVERAGE_ENTRY_PRICE = "average_entry_price"
API_COST_BASIS = "cost_basis"
API_TOTAL_BALANCE = "total_balance"
API_TOTAL_BALANCE_CRYPTO = "total_balance_crypto"
API_TOTAL_BALANCE_FIAT = "total_balance_fiat"
API_TOTAL_CASH_EQUIVALENT_BALANCE = "total_cash_equivalent_balance"
API_TOTAL_CRYPTO_BALANCE = "total_crypto_balance"
API_TOTAL_EQUITIES_BALANCE = "total_equities_balance"
API_TOTAL_FUTURES_BALANCE = "total_futures_balance"
API_FUTURES_UNREALIZED_PNL = "futures_unrealized_pnl"
API_PERP_UNREALIZED_PNL = "perp_unrealized_pnl"
API_UNREALIZED_PNL = "unrealized_pnl"
API_IS_CASH = "is_cash"
API_ACCOUNT_TYPE_VAULT = "ACCOUNT_TYPE_VAULT"
API_ACCOUNT_TYPE_WALLET = "ACCOUNT_TYPE_WALLET"
API_ACCOUNT_TYPE_STAKED_FUNDS = "ACCOUNT_TYPE_STAKED_FUNDS"
