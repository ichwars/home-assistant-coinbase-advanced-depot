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
API_PORTFOLIOS = "portfolios"
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
API_ACCOUNT_TYPE_VAULT = "ACCOUNT_TYPE_VAULT"
