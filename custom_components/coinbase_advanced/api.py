"""Coinbase Advanced REST API wrapper used by the Home Assistant integration.

This module intentionally does not depend on ``coinbase-advanced-py``.  That SDK
currently pulls in a websocket dependency range that can conflict with Home
Assistant's package constraints.  The integration only needs REST for setup,
polling and the generic service, so we sign REST requests directly with the CDP
JWT scheme.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import logging
import secrets
import time
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
import requests

from .const import (
    API_ACCOUNT_TYPE_VAULT,
    API_ACCOUNTS,
    API_AVAILABLE_BALANCE,
    API_CURRENCY,
    API_DATA,
    API_HOLD,
    API_ID,
    API_NAME,
    API_PORTFOLIOS,
    API_RATES,
    API_TYPE,
    API_UUID,
    API_VALUE,
    DEFAULT_EXCHANGE_BASE,
)

_LOGGER = logging.getLogger(__name__)

BASE_URL = "api.coinbase.com"
BASE_URL_HTTPS = f"https://{BASE_URL}"
API_PREFIX = "/api/v3/brokerage"
USER_AGENT = "home-assistant-coinbase-advanced/0.4.0-rc6"
RATE_LIMIT_HEADERS = {
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
}


class CoinbaseAdvancedError(Exception):
    """Base error for Coinbase Advanced integration."""


class CoinbaseAdvancedAuthError(CoinbaseAdvancedError):
    """Authentication failed."""


class CoinbaseAdvancedConnectionError(CoinbaseAdvancedError):
    """Coinbase API could not be reached."""


@dataclass(slots=True, frozen=True)
class CoinbaseSnapshot:
    """Normalized snapshot for Home Assistant entities."""

    portfolios: list[dict[str, Any]]
    accounts: list[dict[str, Any]]
    products: dict[str, dict[str, Any]]
    exchange_rates: dict[str, Any] | None
    transaction_summary: dict[str, Any] | None


def as_plain_data(value: Any) -> Any:
    """Convert response-like objects to built-in Python containers."""
    if hasattr(value, "to_dict"):
        value = value.to_dict()

    if isinstance(value, Mapping):
        return {str(key): as_plain_data(item) for key, item in value.items()}

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [as_plain_data(item) for item in value]

    return value


def _is_auth_error_status(status_code: int) -> bool:
    """Return true for HTTP status codes that normally mean auth/permission failure."""
    return status_code in {401, 403}


def _is_auth_error_text(text: str) -> bool:
    """Best-effort auth error detection across Coinbase error variants."""
    text = text.lower()
    return any(
        marker in text
        for marker in (
            "api key",
            "invalid signature",
            "could not deserialize key data",
            "unauthorized",
            "forbidden",
            "missing required scopes",
        )
    )


def _coerce_float(value: Any, default: float = 0.0) -> float:
    """Coerce API numeric strings to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_api_secret(api_secret: str) -> str:
    """Normalize common pasted CDP private-key forms."""
    api_secret = api_secret.strip()

    # Some users paste the JSON key file contents into the secret field. Accept
    # that and extract the private key when possible.
    if api_secret.startswith("{"):
        try:
            key_file = json.loads(api_secret)
        except json.JSONDecodeError:
            pass
        else:
            api_secret = str(
                key_file.get("privateKey")
                or key_file.get("private_key")
                or key_file.get("apiSecret")
                or api_secret
            )

    # Home Assistant text inputs often store pasted PEM newlines as literal \n.
    if "\\n" in api_secret:
        api_secret = api_secret.replace("\\n", "\n")

    return api_secret


def _base64url_encode(value: bytes) -> str:
    """Return unpadded base64url encoded text."""
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _jwt_json(value: Mapping[str, Any]) -> str:
    """Return compact JSON for JWT signing."""
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _encode_es256_jwt(
    payload: Mapping[str, Any],
    headers: Mapping[str, Any],
    private_key: ec.EllipticCurvePrivateKey,
) -> str:
    """Encode and sign a JWT with ES256 without depending on PyJWT."""
    encoded_header = _base64url_encode(_jwt_json(headers).encode("utf-8"))
    encoded_payload = _base64url_encode(_jwt_json(payload).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    der_signature = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der_signature)
    signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"{encoded_header}.{encoded_payload}.{_base64url_encode(signature)}"


def account_id(account: Mapping[str, Any]) -> str:
    """Return the stable account id from a Coinbase account object."""
    return str(account.get(API_UUID) or account.get(API_ID) or account.get(API_NAME, "unknown"))


def account_name(account: Mapping[str, Any]) -> str:
    """Return account display name."""
    return str(account.get(API_NAME) or account_currency(account) or "Account")


def account_currency(account: Mapping[str, Any]) -> str:
    """Return account currency code."""
    currency = account.get(API_CURRENCY)
    if isinstance(currency, Mapping):
        return str(currency.get("code") or currency.get("id") or "")
    return str(currency or "")


def account_is_vault(account: Mapping[str, Any]) -> bool:
    """Return whether this account is a vault account."""
    return str(account.get(API_TYPE, "")) == API_ACCOUNT_TYPE_VAULT


def account_balance(account: Mapping[str, Any]) -> float:
    """Return available + hold balance for an account."""
    available = account.get(API_AVAILABLE_BALANCE, {})
    hold = account.get(API_HOLD, {})
    if isinstance(available, Mapping):
        available = available.get(API_VALUE)
    if isinstance(hold, Mapping):
        hold = hold.get(API_VALUE)
    return _coerce_float(available) + _coerce_float(hold)


def portfolio_value_in_base(
    accounts: Sequence[Mapping[str, Any]],
    exchange_rates: Mapping[str, Any] | None,
) -> float | None:
    """Return non-vault portfolio value in the exchange-rate base currency."""
    if not exchange_rates:
        return None

    rates = exchange_rates.get(API_RATES, {})
    if not isinstance(rates, Mapping):
        return None

    total = 0.0
    has_value = False
    for account in accounts:
        if account_is_vault(account):
            continue
        currency = account_currency(account)
        rate = _coerce_float(rates.get(currency))
        if not rate:
            continue
        total += account_balance(account) / rate
        has_value = True

    if not has_value:
        return None
    return round(total, 8)


class CoinbaseAdvancedApi:
    """Small REST client for Coinbase Advanced/CDP API keys."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        timeout: int = 10,
        rate_limit_headers: bool = True,
    ) -> None:
        """Initialize the API wrapper."""
        self.api_key = api_key.strip()
        self.api_secret = _normalize_api_secret(api_secret)
        self.timeout = timeout
        self.rate_limit_headers = rate_limit_headers
        self.session = requests.Session()

    def _build_rest_jwt(self, method: str, path: str) -> str:
        """Build a Coinbase CDP REST JWT for one method/path pair."""
        try:
            private_key = serialization.load_pem_private_key(
                self.api_secret.encode("utf-8"), password=None
            )
        except ValueError as error:
            raise CoinbaseAdvancedAuthError(
                "Invalid Coinbase API secret/private key format. Use the CDP EC private key."
            ) from error

        now = int(time.time())
        uri = f"{method} {BASE_URL}{path}"
        payload = {
            "sub": self.api_key,
            "iss": "cdp",
            "nbf": now,
            "exp": now + 120,
            "uri": uri,
        }
        headers = {
            "alg": "ES256",
            "kid": self.api_key,
            "nonce": secrets.token_hex(),
            "typ": "JWT",
        }
        return _encode_es256_jwt(payload, headers, private_key)

    def _headers(self, method: str, path: str) -> dict[str, str]:
        """Return Coinbase REST request headers."""
        return {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._build_rest_jwt(method, path)}",
        }

    def validate(self) -> dict[str, Any]:
        """Validate credentials and return a small identity payload."""
        portfolios = self.fetch_portfolios()
        first = portfolios[0] if portfolios else {}
        title = first.get(API_NAME) or first.get(API_UUID) or "Coinbase"
        unique_id = first.get(API_UUID) or first.get(API_ID) or title
        return {"title": str(title), "unique_id": str(unique_id)}

    def fetch_portfolios(self) -> list[dict[str, Any]]:
        """Fetch portfolios."""
        response = self.call_rest("GET", f"{API_PREFIX}/portfolios")
        portfolios = response.get(API_PORTFOLIOS, []) if isinstance(response, Mapping) else []
        return [dict(item) for item in portfolios if isinstance(item, Mapping)]

    def fetch_accounts(self) -> list[dict[str, Any]]:
        """Fetch all Coinbase accounts, following cursors where present."""
        response = self.call_rest("GET", f"{API_PREFIX}/accounts")
        accounts: list[dict[str, Any]] = []

        while True:
            if isinstance(response, Mapping):
                accounts.extend(
                    dict(item)
                    for item in response.get(API_ACCOUNTS, [])
                    if isinstance(item, Mapping)
                )
                if not response.get("has_next"):
                    break
                cursor = response.get("cursor")
                response = self.call_rest(
                    "GET", f"{API_PREFIX}/accounts", params={"cursor": cursor}
                )
                continue
            break

        return accounts

    def fetch_exchange_rates(self, currency: str = DEFAULT_EXCHANGE_BASE) -> dict[str, Any]:
        """Fetch exchange rates using Coinbase's exchange-rate endpoint."""
        response = self.call_rest(
            "GET",
            "/v2/exchange-rates",
            params={"currency": currency or DEFAULT_EXCHANGE_BASE},
        )
        if isinstance(response, Mapping) and API_DATA in response:
            data = response[API_DATA]
            return dict(data) if isinstance(data, Mapping) else {}
        return dict(response) if isinstance(response, Mapping) else {}

    def fetch_products(self, product_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch selected products by id."""
        products: dict[str, dict[str, Any]] = {}
        for product_id in product_ids:
            product_id = product_id.strip().upper()
            if not product_id:
                continue
            product = self.call_rest("GET", f"{API_PREFIX}/products/{product_id}")
            if isinstance(product, Mapping):
                products[product_id] = dict(product)
        return products

    def fetch_transaction_summary(self) -> dict[str, Any] | None:
        """Fetch transaction summary when the API key has the required permission."""
        summary = self.call_rest("GET", f"{API_PREFIX}/transaction_summary")
        return dict(summary) if isinstance(summary, Mapping) else None

    def fetch_snapshot(
        self,
        *,
        product_ids: list[str] | None = None,
        exchange_base: str = DEFAULT_EXCHANGE_BASE,
        include_exchange_rates: bool = True,
        include_transaction_summary: bool = False,
    ) -> CoinbaseSnapshot:
        """Fetch all data needed by the current entity set."""
        portfolios = self.fetch_portfolios()
        accounts = self.fetch_accounts()
        products = self.fetch_products(product_ids or [])
        exchange_rates = (
            self.fetch_exchange_rates(exchange_base) if include_exchange_rates else None
        )
        transaction_summary = (
            self.fetch_transaction_summary() if include_transaction_summary else None
        )

        return CoinbaseSnapshot(
            portfolios=portfolios,
            accounts=accounts,
            products=products,
            exchange_rates=exchange_rates,
            transaction_summary=transaction_summary,
        )

    def call_rest(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Call a Coinbase REST endpoint in read-only mode."""
        method = method.upper().strip()
        if not path.startswith("/") or path.startswith("//") or "://" in path:
            raise CoinbaseAdvancedError("Path must be a relative API path starting with '/'.")

        if method != "GET":
            raise CoinbaseAdvancedError(
                "Coinbase Advanced is read-only; only GET API calls are supported."
            )

        clean_params = {
            key: value for key, value in (params or {}).items() if value is not None
        }

        url = f"{BASE_URL_HTTPS}{path}"
        try:
            response = self.session.request(
                method,
                url,
                params=clean_params,
                headers=self._headers(method, path),
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise CoinbaseAdvancedConnectionError(str(error)) from error

        if response.status_code >= 400:
            message = f"{response.status_code} {response.reason}: {response.text}"
            if _is_auth_error_status(response.status_code) or _is_auth_error_text(message):
                raise CoinbaseAdvancedAuthError(message)
            raise CoinbaseAdvancedConnectionError(message)

        if response.status_code == 204 or not response.text:
            result: Any = {}
        else:
            try:
                result = response.json()
            except ValueError as error:
                raise CoinbaseAdvancedConnectionError(
                    f"Coinbase returned a non-JSON response: {response.text[:200]}"
                ) from error

        if self.rate_limit_headers and isinstance(result, dict):
            result = {
                **result,
                **{
                    key: response.headers.get(key)
                    for key in RATE_LIMIT_HEADERS
                    if response.headers.get(key) is not None
                },
            }

        _LOGGER.debug("Coinbase %s %s returned keys: %s", method, path, list(result) if isinstance(result, dict) else type(result))
        return as_plain_data(result)
