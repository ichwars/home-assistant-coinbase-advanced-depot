"""Sensors for the Coinbase Advanced custom integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import (
    CoinbaseSnapshot,
    account_balance,
    account_currency,
    account_id,
    account_is_vault,
    account_name,
    portfolio_balance_currency,
    portfolio_balance_value,
    portfolio_spot_positions,
    portfolio_value_in_base,
    position_account_id,
    position_account_type,
    position_allocation,
    position_asset,
    position_asset_color,
    position_asset_uuid,
    position_average_entry_price,
    position_available_to_send,
    position_available_to_trade,
    position_available_to_transfer,
    position_balance,
    position_cost_basis,
    position_fiat_value,
    position_is_cash,
    position_unrealized_pnl,
)
from .const import (
    API_ACCOUNT_TYPE,
    API_ACCOUNT_TYPE_STAKED_FUNDS,
    API_ACCOUNT_TYPE_WALLET,
    API_ALLOCATION,
    API_ASSET_COLOR,
    API_ASSET_UUID,
    API_AVAILABLE_TO_SEND_CRYPTO,
    API_AVAILABLE_TO_TRADE_CRYPTO,
    API_AVAILABLE_TO_TRANSFER_CRYPTO,
    API_AVERAGE_ENTRY_PRICE,
    API_AVAILABLE_BALANCE,
    API_COST_BASIS,
    API_CURRENCY,
    API_FUTURES_UNREALIZED_PNL,
    API_HOLD,
    API_IS_CASH,
    API_PERP_UNREALIZED_PNL,
    API_RATES,
    API_TOTAL_BALANCE,
    API_TOTAL_BALANCE_CRYPTO,
    API_TOTAL_BALANCE_FIAT,
    API_TOTAL_CASH_EQUIVALENT_BALANCE,
    API_TOTAL_CRYPTO_BALANCE,
    API_TOTAL_EQUITIES_BALANCE,
    API_TOTAL_FUTURES_BALANCE,
    API_UNREALIZED_PNL,
    API_VALUE,
    CONF_ACCOUNT_CURRENCIES,
    CONF_EXCHANGE_BASE,
    CONF_EXCHANGE_RATE_CURRENCIES,
    CONF_INCLUDE_ZERO_BALANCES,
    CONF_PRODUCTS,
    DEFAULT_EXCHANGE_BASE,
    DOMAIN,
)
from .coordinator import CoinbaseAdvancedCoordinator

ATTRIBUTION = "Data provided by Coinbase"
ATTR_ACCOUNT_ID = "account_id"
ATTR_AVAILABLE = "available"
ATTR_HOLD = "hold"
ATTR_BALANCE_IN_BASE = "balance_in_exchange_base"
ATTR_PRODUCT_ID = "product_id"
ATTR_BASE_CURRENCY = "base_currency"
ATTR_QUOTE_CURRENCY = "quote_currency"
ATTR_STATUS = "status"
ATTR_ACCOUNT_COUNT = "account_count"
ATTR_POSITION_COUNT = "position_count"
ATTR_BALANCE_KEY = "balance_key"

PARALLEL_UPDATES = 0

CURRENCY_ICONS = {
    "BTC": "mdi:currency-btc",
    "ETH": "mdi:currency-eth",
    "EUR": "mdi:currency-eur",
    "LTC": "mdi:litecoin",
    "USD": "mdi:currency-usd",
}
DEFAULT_COIN_ICON = "mdi:cash"

PORTFOLIO_BALANCE_SENSORS: tuple[tuple[str, str, str, bool], ...] = (
    (API_TOTAL_BALANCE, "Portfolio total value", "total-value", True),
    (API_TOTAL_CRYPTO_BALANCE, "Portfolio crypto value", "crypto-value", True),
    (
        API_TOTAL_CASH_EQUIVALENT_BALANCE,
        "Portfolio cash value",
        "cash-value",
        True,
    ),
    (API_TOTAL_FUTURES_BALANCE, "Portfolio futures value", "futures-value", False),
    (API_TOTAL_EQUITIES_BALANCE, "Portfolio equities value", "equities-value", False),
    (
        API_FUTURES_UNREALIZED_PNL,
        "Portfolio futures unrealized PnL",
        "futures-unrealized-pnl",
        False,
    ),
    (
        API_PERP_UNREALIZED_PNL,
        "Portfolio perpetual unrealized PnL",
        "perp-unrealized-pnl",
        False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Coinbase Advanced sensors from a config entry.

    Behavior for wallet sensors:
    - If account_balance_currencies is empty, create sensors only for non-vault
      accounts with a non-zero balance. Coinbase often returns many zero-balance
      wallet objects that users do not consider part of their depot.
    - If account_balance_currencies is set, create sensors only for those
      currencies, even if the current balance is zero.
    - If include_zero_balances is true and no explicit currency filter is set,
      include every non-vault account returned by Coinbase.
    """
    coordinator: CoinbaseAdvancedCoordinator = config_entry.runtime_data.coordinator
    data = coordinator.data
    entities: list[SensorEntity] = []
    expected_unique_ids: set[str] = set()

    selected_account_currencies: list[str] = config_entry.options.get(
        CONF_ACCOUNT_CURRENCIES, []
    )
    include_zero_balances = bool(
        config_entry.options.get(CONF_INCLUDE_ZERO_BALANCES, False)
    )
    selected_products: list[str] = config_entry.options.get(CONF_PRODUCTS, [])
    selected_rates: list[str] = config_entry.options.get(CONF_EXCHANGE_RATE_CURRENCIES, [])
    exchange_base: str = config_entry.options.get(CONF_EXCHANGE_BASE, DEFAULT_EXCHANGE_BASE)

    def add_entity(entity: SensorEntity) -> None:
        """Track expected unique IDs so stale entities can be removed."""
        entities.append(entity)
        unique_id = getattr(entity, "unique_id", None)
        if unique_id:
            expected_unique_ids.add(str(unique_id))

    add_entity(DepotValueSensor(coordinator, config_entry.entry_id, exchange_base))

    if data.portfolio_breakdowns:
        for balance_key, name, unique_suffix, include_zero in PORTFOLIO_BALANCE_SENSORS:
            value = portfolio_balance_value(data.portfolio_breakdowns, balance_key)
            if value is None or (not include_zero and value == 0):
                continue
            add_entity(
                PortfolioBalanceSensor(
                    coordinator,
                    config_entry.entry_id,
                    balance_key,
                    name,
                    unique_suffix,
                    exchange_base,
                )
            )

    account_ids = {account_id(account) for account in data.accounts}
    for account in data.accounts:
        currency = account_currency(account)
        if account_is_vault(account):
            continue
        if selected_account_currencies:
            if currency not in selected_account_currencies:
                continue
        elif not include_zero_balances and account_balance(account) <= 0:
            continue
        add_entity(AccountBalanceSensor(coordinator, config_entry.entry_id, account))

    for position in portfolio_spot_positions(data.portfolio_breakdowns):
        asset = position_asset(position)
        position_id = position_account_id(position)
        if (
            position_account_type(position) == API_ACCOUNT_TYPE_WALLET
            and position_id in account_ids
        ):
            continue
        if selected_account_currencies:
            if asset not in selected_account_currencies:
                continue
        elif not include_zero_balances and position_balance(position) <= 0:
            continue
        add_entity(PortfolioPositionSensor(coordinator, config_entry.entry_id, position))

    for product_id in selected_products:
        if product_id in data.products:
            add_entity(ProductPriceSensor(coordinator, config_entry.entry_id, product_id))

    if data.exchange_rates:
        rates = data.exchange_rates.get(API_RATES, {})
        for currency in selected_rates:
            if currency in rates:
                add_entity(
                    ExchangeRateSensor(
                        coordinator,
                        config_entry.entry_id,
                        exchange_base,
                        currency,
                    )
                )

    _remove_stale_entities(hass, config_entry, expected_unique_ids)
    async_add_entities(entities)


def _remove_stale_entities(
    hass: HomeAssistant, config_entry, expected_unique_ids: set[str]
) -> None:
    """Remove previously created Coinbase Advanced entities no longer desired."""
    registry = er.async_get(hass)
    unique_id_prefix = f"{DOMAIN}-{config_entry.entry_id}-"
    for entity_entry in er.async_entries_for_config_entry(
        registry, config_entry.entry_id
    ):
        unique_id = entity_entry.unique_id
        if (
            unique_id
            and unique_id.startswith(unique_id_prefix)
            and unique_id not in expected_unique_ids
        ):
            registry.async_remove(entity_entry.entity_id)


def _coerce_float(value: Any) -> float | None:
    """Coerce an API value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _balance_part(account: Mapping[str, Any], key: str) -> float | None:
    """Return available/hold balance part from an account."""
    value = account.get(key, {})
    if isinstance(value, Mapping):
        value = value.get(API_VALUE)
    return _coerce_float(value)


def _product_price(product: Mapping[str, Any]) -> float | None:
    """Return product price from a product payload."""
    for key in ("price", "mid_market_price", "last_trade_price"):
        value = _coerce_float(product.get(key))
        if value is not None:
            return value
    return None


def _quote_currency(product: Mapping[str, Any], product_id: str) -> str | None:
    """Return quote currency for a product."""
    quote = product.get("quote_currency_id") or product.get("quote_currency")
    if quote:
        return str(quote)
    if "-" in product_id:
        return product_id.split("-", 1)[1]
    return None


def _base_currency(product: Mapping[str, Any], product_id: str) -> str | None:
    """Return base currency for a product."""
    base = product.get("base_currency_id") or product.get("base_currency")
    if base:
        return str(base)
    if "-" in product_id:
        return product_id.split("-", 1)[0]
    return None


class CoinbaseAdvancedBaseEntity(CoordinatorEntity, SensorEntity):
    """Base entity for Coinbase Advanced sensors."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: CoinbaseAdvancedCoordinator, entry_id: str) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.coinbase.com/settings/api",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Coinbase",
            name="Coinbase Advanced",
        )

    @property
    def snapshot(self) -> CoinbaseSnapshot:
        """Return current coordinator data."""
        return self.coordinator.data


class DepotValueSensor(CoinbaseAdvancedBaseEntity):
    """Total Coinbase depot value in the configured base currency."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: CoinbaseAdvancedCoordinator,
        entry_id: str,
        exchange_base: str,
    ) -> None:
        """Initialize depot value sensor."""
        super().__init__(coordinator, entry_id)
        self._exchange_base = exchange_base
        self._attr_name = "Depot value"
        self._attr_unique_id = f"{DOMAIN}-{entry_id}-depot-value-{exchange_base}"
        self._attr_native_unit_of_measurement = exchange_base
        self._attr_icon = CURRENCY_ICONS.get(exchange_base, DEFAULT_COIN_ICON)

    @property
    def native_value(self) -> float | None:
        """Return total non-vault account value in the configured base currency."""
        value = portfolio_value_in_base(
            self.snapshot.accounts,
            self.snapshot.exchange_rates,
            self.snapshot.portfolio_breakdowns,
        )
        return round(value, 2) if value is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return depot metadata."""
        return {
            ATTR_BASE_CURRENCY: self._exchange_base,
            ATTR_ACCOUNT_COUNT: sum(
                1 for account in self.snapshot.accounts if not account_is_vault(account)
            ),
            ATTR_POSITION_COUNT: len(
                portfolio_spot_positions(self.snapshot.portfolio_breakdowns)
            ),
        }


class PortfolioBalanceSensor(CoinbaseAdvancedBaseEntity):
    """Portfolio breakdown monetary balance sensor."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: CoinbaseAdvancedCoordinator,
        entry_id: str,
        balance_key: str,
        name: str,
        unique_suffix: str,
        fallback_currency: str,
    ) -> None:
        """Initialize portfolio breakdown balance sensor."""
        super().__init__(coordinator, entry_id)
        self._balance_key = balance_key
        self._fallback_currency = fallback_currency
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}-{entry_id}-portfolio-{unique_suffix}"
        self._attr_icon = CURRENCY_ICONS.get(fallback_currency, DEFAULT_COIN_ICON)

    @property
    def native_value(self) -> float | None:
        """Return the current portfolio balance value."""
        value = portfolio_balance_value(
            self.snapshot.portfolio_breakdowns,
            self._balance_key,
        )
        return round(value, 2) if value is not None else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the currency reported by Coinbase for this balance."""
        return (
            portfolio_balance_currency(
                self.snapshot.portfolio_breakdowns,
                self._balance_key,
            )
            or self._fallback_currency
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return portfolio balance metadata."""
        return {
            ATTR_BALANCE_KEY: self._balance_key,
            API_CURRENCY: self.native_unit_of_measurement,
            ATTR_POSITION_COUNT: len(
                portfolio_spot_positions(self.snapshot.portfolio_breakdowns)
            ),
        }


class AccountBalanceSensor(CoinbaseAdvancedBaseEntity):
    """Wallet balance sensor."""

    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: CoinbaseAdvancedCoordinator,
        entry_id: str,
        account: Mapping[str, Any],
    ) -> None:
        """Initialize account balance sensor."""
        super().__init__(coordinator, entry_id)
        self._account_id = account_id(account)
        self._currency = account_currency(account)
        self._attr_name = f"{account_name(account)} balance"
        self._attr_unique_id = f"{DOMAIN}-{entry_id}-account-{self._account_id}"
        self._attr_native_unit_of_measurement = self._currency
        self._attr_icon = CURRENCY_ICONS.get(self._currency, DEFAULT_COIN_ICON)

    def _current_account(self) -> Mapping[str, Any] | None:
        """Return the current account payload."""
        for account in self.snapshot.accounts:
            if account_id(account) == self._account_id:
                return account
        return None

    @property
    def native_value(self) -> float | None:
        """Return the current balance."""
        account = self._current_account()
        if account is None:
            return None
        return account_balance(account)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        account = self._current_account()
        if account is None:
            return {ATTR_ACCOUNT_ID: self._account_id}

        attrs: dict[str, Any] = {
            ATTR_ACCOUNT_ID: self._account_id,
            API_CURRENCY: self._currency,
            ATTR_AVAILABLE: _balance_part(account, API_AVAILABLE_BALANCE),
            ATTR_HOLD: _balance_part(account, API_HOLD),
        }

        exchange_rates = self.snapshot.exchange_rates or {}
        rates = exchange_rates.get(API_RATES, {})
        rate = _coerce_float(rates.get(self._currency)) if isinstance(rates, Mapping) else None
        if rate:
            attrs[ATTR_BALANCE_IN_BASE] = round(account_balance(account) / rate, 8)
            attrs[ATTR_BASE_CURRENCY] = exchange_rates.get(API_CURRENCY)

        return attrs


class PortfolioPositionSensor(CoinbaseAdvancedBaseEntity):
    """Portfolio spot position balance sensor."""

    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: CoinbaseAdvancedCoordinator,
        entry_id: str,
        position: Mapping[str, Any],
    ) -> None:
        """Initialize portfolio position balance sensor."""
        super().__init__(coordinator, entry_id)
        self._position_id = position_account_id(position)
        self._asset = position_asset(position)
        self._account_type = position_account_type(position)
        label = (
            "staked"
            if self._account_type == API_ACCOUNT_TYPE_STAKED_FUNDS
            else "position"
        )
        self._attr_name = f"{self._asset} {label} balance"
        self._attr_unique_id = f"{DOMAIN}-{entry_id}-position-{self._position_id}"
        self._attr_native_unit_of_measurement = self._asset
        self._attr_icon = CURRENCY_ICONS.get(self._asset, DEFAULT_COIN_ICON)

    def _current_position(self) -> Mapping[str, Any] | None:
        """Return the current position payload."""
        for position in portfolio_spot_positions(self.snapshot.portfolio_breakdowns):
            if position_account_id(position) == self._position_id:
                return position
        return None

    @property
    def native_value(self) -> float | None:
        """Return current portfolio position balance."""
        position = self._current_position()
        if position is None:
            return None
        return position_balance(position)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return position metadata."""
        position = self._current_position()
        if position is None:
            return {ATTR_ACCOUNT_ID: self._position_id}

        return {
            ATTR_ACCOUNT_ID: self._position_id,
            API_CURRENCY: self._asset,
            API_ACCOUNT_TYPE: self._account_type,
            API_TOTAL_BALANCE_CRYPTO: position_balance(position),
            API_TOTAL_BALANCE_FIAT: position_fiat_value(position),
            API_ALLOCATION: position_allocation(position),
            API_COST_BASIS: position_cost_basis(position),
            API_AVERAGE_ENTRY_PRICE: position_average_entry_price(position),
            API_UNREALIZED_PNL: position_unrealized_pnl(position),
            API_AVAILABLE_TO_TRADE_CRYPTO: position_available_to_trade(position),
            API_AVAILABLE_TO_TRANSFER_CRYPTO: position_available_to_transfer(position),
            API_AVAILABLE_TO_SEND_CRYPTO: position_available_to_send(position),
            API_ASSET_COLOR: position_asset_color(position),
            API_ASSET_UUID: position_asset_uuid(position),
            API_IS_CASH: position_is_cash(position),
        }


class ProductPriceSensor(CoinbaseAdvancedBaseEntity):
    """Selected Coinbase product price sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: CoinbaseAdvancedCoordinator,
        entry_id: str,
        product_id: str,
    ) -> None:
        """Initialize product price sensor."""
        super().__init__(coordinator, entry_id)
        self._product_id = product_id
        product = self.snapshot.products.get(product_id, {})
        base = _base_currency(product, product_id) or product_id
        quote = _quote_currency(product, product_id)
        self._attr_name = f"{product_id} price"
        self._attr_unique_id = f"{DOMAIN}-{entry_id}-product-{product_id}"
        self._attr_native_unit_of_measurement = quote
        self._attr_icon = CURRENCY_ICONS.get(base, DEFAULT_COIN_ICON)

    @property
    def native_value(self) -> float | None:
        """Return current product price."""
        product = self.snapshot.products.get(self._product_id)
        if not product:
            return None
        return _product_price(product)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return product metadata."""
        product = self.snapshot.products.get(self._product_id, {})
        return {
            ATTR_PRODUCT_ID: self._product_id,
            ATTR_BASE_CURRENCY: _base_currency(product, self._product_id),
            ATTR_QUOTE_CURRENCY: _quote_currency(product, self._product_id),
            ATTR_STATUS: product.get("status"),
            "price_percentage_change_24h": product.get("price_percentage_change_24h"),
            "volume_24h": product.get("volume_24h"),
        }


class ExchangeRateSensor(CoinbaseAdvancedBaseEntity):
    """Exchange-rate sensor showing one selected currency in the chosen base."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: CoinbaseAdvancedCoordinator,
        entry_id: str,
        exchange_base: str,
        currency: str,
    ) -> None:
        """Initialize exchange-rate sensor."""
        super().__init__(coordinator, entry_id)
        self._exchange_base = exchange_base
        self._currency = currency
        self._attr_name = f"{currency} exchange rate"
        self._attr_unique_id = f"{DOMAIN}-{entry_id}-exchange-{exchange_base}-{currency}"
        self._attr_native_unit_of_measurement = exchange_base
        self._attr_icon = CURRENCY_ICONS.get(currency, DEFAULT_COIN_ICON)

    @property
    def native_value(self) -> float | None:
        """Return current rate as one unit of currency expressed in exchange_base."""
        exchange_rates = self.snapshot.exchange_rates or {}
        rates = exchange_rates.get(API_RATES, {})
        if not isinstance(rates, Mapping):
            return None
        rate = _coerce_float(rates.get(self._currency))
        if not rate:
            return None
        return round(1 / rate, 8)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return exchange-rate metadata."""
        return {
            ATTR_BASE_CURRENCY: self._exchange_base,
            API_CURRENCY: self._currency,
        }
