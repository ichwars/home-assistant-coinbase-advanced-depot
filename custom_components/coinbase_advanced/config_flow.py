"""Config flow for the Coinbase Advanced custom integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

try:
    from homeassistant.config_entries import OptionsFlowWithReload
except ImportError:  # Older Home Assistant versions
    from homeassistant.config_entries import OptionsFlow as OptionsFlowWithReload
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .api import (
    CoinbaseAdvancedApi,
    CoinbaseAdvancedAuthError,
    CoinbaseAdvancedConnectionError,
    account_currency,
    account_is_vault,
    portfolio_spot_positions,
    position_asset,
)
from .const import (
    API_RATES,
    CONF_ACCOUNT_CURRENCIES,
    CONF_EXCHANGE_BASE,
    CONF_EXCHANGE_RATE_CURRENCIES,
    CONF_INCLUDE_PORTFOLIO_BREAKDOWN,
    CONF_INCLUDE_TRANSACTION_SUMMARY,
    CONF_INCLUDE_ZERO_BALANCES,
    CONF_POLL_INTERVAL,
    CONF_PRODUCTS,
    DEFAULT_EXCHANGE_BASE,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MIN_POLL_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_API_TOKEN): cv.string,
    }
)


def _csv_items(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    """Return raw comma/newline separated option values."""
    if value is None:
        return []
    if isinstance(value, list | tuple):
        raw_values = value
    else:
        raw_values = value.replace("\n", ",").split(",")

    result: list[str] = []
    for item in raw_values:
        normalized = str(item).strip().upper()
        if normalized:
            result.append(normalized)
    return result


def _deduplicate(values: list[str]) -> list[str]:
    """Return values in input order without duplicates."""
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _normalize_account_currency(value: str) -> str:
    """Normalize a wallet-balance filter item.

    Wallet balances are account currencies such as ETH, BTC or USDC. Users often
    enter product pairs like ETH-USD here, so accept that common mistake and use
    the base asset.
    """
    value = value.strip().upper()
    if "-" in value:
        return value.split("-", 1)[0]
    return value


def _parse_account_currency_list(
    value: str | list[str] | tuple[str, ...] | None,
) -> list[str]:
    """Parse wallet-balance currency filters."""
    return _deduplicate([_normalize_account_currency(item) for item in _csv_items(value)])


def _normalize_product_id(value: str, exchange_base: str) -> str:
    """Normalize a Coinbase product id.

    Product sensors need market pairs such as ETH-USD. If the user enters a
    single asset like ETH, assume the configured quote/base currency.
    """
    value = value.strip().upper()
    if value and "-" not in value:
        return f"{value}-{exchange_base.strip().upper()}"
    return value


def _parse_product_list(
    value: str | list[str] | tuple[str, ...] | None, exchange_base: str
) -> list[str]:
    """Parse Coinbase product ids."""
    return _deduplicate([_normalize_product_id(item, exchange_base) for item in _csv_items(value)])


def _parse_currency_list(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    """Parse exchange-rate currency lists."""
    return _deduplicate(_csv_items(value))


def _join_csv(values: list[str] | tuple[str, ...] | None) -> str:
    """Join values for the options form."""
    return ", ".join(values or [])


def _classify_auth_error(error: CoinbaseAdvancedAuthError) -> type[HomeAssistantError]:
    """Classify auth failure for nicer UI errors."""
    text = str(error).lower()
    if "invalid signature" in text or "could not deserialize key data" in text:
        return InvalidSecret
    if "api key" in text or "401" in text or "403" in text:
        return InvalidKey
    return InvalidAuth


def _validate_api_sync(data: Mapping[str, str]) -> dict[str, str]:
    """Validate the Coinbase API credentials."""
    api_key = data[CONF_API_KEY].strip()
    api_token = data[CONF_API_TOKEN].strip()

    # Coinbase Advanced/CDP keys look like organizations/{org_id}/apiKeys/{key_id}.
    # Keeping this check up front avoids accepting legacy Coinbase v2 keys.
    if (
        not api_key
        or not api_token
        or "organizations/" not in api_key
        or "/apiKeys/" not in api_key
    ):
        raise InvalidKeyFormat

    api = CoinbaseAdvancedApi(api_key=api_key, api_secret=api_token)
    try:
        return api.validate()
    except CoinbaseAdvancedAuthError as error:
        raise _classify_auth_error(error) from error
    except CoinbaseAdvancedConnectionError as error:
        raise CannotConnect from error


async def validate_api(hass: HomeAssistant, data: Mapping[str, str]) -> dict[str, str]:
    """Validate credentials in an executor."""
    return await hass.async_add_executor_job(lambda: _validate_api_sync(data))


def _get_api_for_options(config_entry) -> CoinbaseAdvancedApi:
    """Return the loaded API object or create a temporary one."""
    runtime_data = getattr(config_entry, "runtime_data", None)
    if runtime_data:
        return runtime_data.api
    return CoinbaseAdvancedApi(
        api_key=config_entry.data[CONF_API_KEY],
        api_secret=config_entry.data[CONF_API_TOKEN],
    )


def _validate_options_sync(config_entry, options: dict[str, Any]) -> None:
    """Validate options against current Coinbase data."""
    api = _get_api_for_options(config_entry)

    selected_account_currencies: list[str] = options.get(CONF_ACCOUNT_CURRENCIES, [])
    selected_products: list[str] = options.get(CONF_PRODUCTS, [])
    selected_exchange_rates: list[str] = options.get(CONF_EXCHANGE_RATE_CURRENCIES, [])
    exchange_base: str = options.get(CONF_EXCHANGE_BASE, DEFAULT_EXCHANGE_BASE)
    include_portfolio_breakdown = bool(
        options.get(CONF_INCLUDE_PORTFOLIO_BREAKDOWN, True)
    )

    if selected_account_currencies:
        portfolio_breakdowns = []
        if include_portfolio_breakdown:
            portfolios = api.fetch_portfolios()
            portfolio_breakdowns = api.fetch_portfolio_breakdowns(portfolios)
        accounts = api.fetch_accounts()
        account_currencies = {
            account_currency(account)
            for account in accounts
            if not account_is_vault(account)
        }
        account_currencies.update(
            position_asset(position)
            for position in portfolio_spot_positions(portfolio_breakdowns)
        )
        if not set(selected_account_currencies).issubset(account_currencies):
            raise CurrencyUnavailable

    if selected_products:
        try:
            api.fetch_products(selected_products)
        except CoinbaseAdvancedConnectionError as error:
            raise ProductUnavailable from error
        except CoinbaseAdvancedAuthError as error:
            raise InvalidAuth from error

    if selected_exchange_rates:
        rates = api.fetch_exchange_rates(exchange_base).get(API_RATES, {})
        if not set(selected_exchange_rates).issubset(set(rates)):
            raise ExchangeRateUnavailable


class CoinbaseAdvancedConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Coinbase Advanced config flow."""

    VERSION = 1

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication for expired or revoked credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Validate and store replacement Coinbase API credentials."""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
            )

        try:
            info = await validate_api(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidKeyFormat:
            errors["base"] = "invalid_key_format"
        except InvalidKey:
            errors["base"] = "invalid_auth_key"
        except InvalidSecret:
            errors["base"] = "invalid_auth_secret"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception during Coinbase reauthentication")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(info["unique_id"])
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates=user_input,
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        try:
            info = await validate_api(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidKeyFormat:
            errors["base"] = "invalid_key_format"
        except InvalidKey:
            errors["base"] = "invalid_auth_key"
        except InvalidSecret:
            errors["base"] = "invalid_auth_secret"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception during Coinbase setup")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(info["unique_id"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=info["title"],
                data=user_input,
                options={
                    CONF_ACCOUNT_CURRENCIES: [],
                    CONF_PRODUCTS: [],
                    CONF_EXCHANGE_RATE_CURRENCIES: [],
                    CONF_EXCHANGE_BASE: DEFAULT_EXCHANGE_BASE,
                    CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
                    CONF_INCLUDE_PORTFOLIO_BREAKDOWN: True,
                    CONF_INCLUDE_TRANSACTION_SUMMARY: False,
                    CONF_INCLUDE_ZERO_BALANCES: False,
                },
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlowHandler:
        """Return the options flow handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handle Coinbase Advanced options."""

    def _schema(self, defaults: Mapping[str, Any]) -> vol.Schema:
        """Build options schema."""
        return vol.Schema(
            {
                vol.Optional(
                    CONF_ACCOUNT_CURRENCIES,
                    default=_join_csv(defaults.get(CONF_ACCOUNT_CURRENCIES, [])),
                ): str,
                vol.Optional(
                    CONF_PRODUCTS,
                    default=_join_csv(defaults.get(CONF_PRODUCTS, [])),
                ): str,
                vol.Optional(
                    CONF_EXCHANGE_RATE_CURRENCIES,
                    default=_join_csv(defaults.get(CONF_EXCHANGE_RATE_CURRENCIES, [])),
                ): str,
                vol.Optional(
                    CONF_EXCHANGE_BASE,
                    default=defaults.get(CONF_EXCHANGE_BASE, DEFAULT_EXCHANGE_BASE),
                ): cv.string,
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=defaults.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL)),
                vol.Optional(
                    CONF_INCLUDE_PORTFOLIO_BREAKDOWN,
                    default=defaults.get(CONF_INCLUDE_PORTFOLIO_BREAKDOWN, True),
                ): bool,
                vol.Optional(
                    CONF_INCLUDE_TRANSACTION_SUMMARY,
                    default=defaults.get(CONF_INCLUDE_TRANSACTION_SUMMARY, False),
                ): bool,
                vol.Optional(
                    CONF_INCLUDE_ZERO_BALANCES,
                    default=defaults.get(CONF_INCLUDE_ZERO_BALANCES, False),
                ): bool,
            }
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        errors: dict[str, str] = {}
        defaults = dict(self.config_entry.options)

        if user_input is not None:
            exchange_base = str(
                user_input.get(CONF_EXCHANGE_BASE, DEFAULT_EXCHANGE_BASE)
            ).strip().upper()
            options = {
                CONF_ACCOUNT_CURRENCIES: _parse_account_currency_list(
                    user_input.get(CONF_ACCOUNT_CURRENCIES)
                ),
                CONF_PRODUCTS: _parse_product_list(
                    user_input.get(CONF_PRODUCTS), exchange_base
                ),
                CONF_EXCHANGE_RATE_CURRENCIES: _parse_currency_list(
                    user_input.get(CONF_EXCHANGE_RATE_CURRENCIES)
                ),
                CONF_EXCHANGE_BASE: exchange_base,
                CONF_POLL_INTERVAL: int(
                    user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
                ),
                CONF_INCLUDE_PORTFOLIO_BREAKDOWN: bool(
                    user_input.get(CONF_INCLUDE_PORTFOLIO_BREAKDOWN, True)
                ),
                CONF_INCLUDE_TRANSACTION_SUMMARY: bool(
                    user_input.get(CONF_INCLUDE_TRANSACTION_SUMMARY, False)
                ),
                CONF_INCLUDE_ZERO_BALANCES: bool(
                    user_input.get(CONF_INCLUDE_ZERO_BALANCES, False)
                ),
            }

            try:
                await self.hass.async_add_executor_job(
                    lambda: _validate_options_sync(self.config_entry, options)
                )
            except CurrencyUnavailable:
                errors["base"] = "currency_unavailable"
            except ProductUnavailable:
                errors["base"] = "product_unavailable"
            except ExchangeRateUnavailable:
                errors["base"] = "exchange_rate_unavailable"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during Coinbase options flow")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="", data=options)

            defaults = options

        return self.async_show_form(
            step_id="init",
            data_schema=self._schema(defaults),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid auth."""


class InvalidSecret(HomeAssistantError):
    """Error to indicate invalid secret."""


class InvalidKey(HomeAssistantError):
    """Error to indicate invalid key."""


class InvalidKeyFormat(HomeAssistantError):
    """Error to indicate a non-CDP key format."""


class CurrencyUnavailable(HomeAssistantError):
    """Error to indicate a requested wallet currency is unavailable."""


class ProductUnavailable(HomeAssistantError):
    """Error to indicate a requested product is unavailable."""


class ExchangeRateUnavailable(HomeAssistantError):
    """Error to indicate a requested exchange rate is unavailable."""
