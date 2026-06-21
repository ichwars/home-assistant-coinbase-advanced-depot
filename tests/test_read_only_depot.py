"""Regression tests for the read-only Coinbase depot model."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "coinbase_advanced"
PACKAGE = "coinbase_advanced_under_test"


def _load_module(name: str):
    """Load one integration module without importing Home Assistant."""
    package = sys.modules.setdefault(PACKAGE, types.ModuleType(PACKAGE))
    package.__path__ = [str(INTEGRATION)]

    homeassistant = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
    const = types.ModuleType("homeassistant.const")
    const.CONF_API_KEY = "api_key"
    const.CONF_API_TOKEN = "api_token"
    sys.modules["homeassistant.const"] = const
    homeassistant.const = const

    jwt = types.ModuleType("jwt")
    jwt.encode = lambda *args, **kwargs: "token"
    sys.modules["jwt"] = jwt

    requests = types.ModuleType("requests")
    requests.RequestException = OSError
    requests.Session = lambda: types.SimpleNamespace(request=lambda *args, **kwargs: None)
    sys.modules["requests"] = requests

    cryptography = sys.modules.setdefault("cryptography", types.ModuleType("cryptography"))
    hazmat = sys.modules.setdefault(
        "cryptography.hazmat", types.ModuleType("cryptography.hazmat")
    )
    primitives = sys.modules.setdefault(
        "cryptography.hazmat.primitives",
        types.ModuleType("cryptography.hazmat.primitives"),
    )
    serialization = types.ModuleType("cryptography.hazmat.primitives.serialization")
    serialization.load_pem_private_key = lambda *args, **kwargs: object()
    sys.modules["cryptography.hazmat.primitives.serialization"] = serialization
    cryptography.hazmat = hazmat
    hazmat.primitives = primitives
    primitives.serialization = serialization

    module_name = f"{PACKAGE}.{name}"
    sys.modules.pop(module_name, None)

    spec = importlib.util.spec_from_file_location(
        module_name,
        INTEGRATION / f"{name}.py",
        submodule_search_locations=[str(INTEGRATION)] if name == "__init__" else None,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class ReadOnlyApiTests(unittest.TestCase):
    """Read-only API contract tests."""

    def test_call_rest_has_no_write_override(self) -> None:
        """The REST helper must not expose an allow_write escape hatch."""
        api_module = _load_module("api")

        signature = inspect.signature(api_module.CoinbaseAdvancedApi.call_rest)

        self.assertNotIn("allow_write", signature.parameters)

    def test_call_rest_rejects_non_get_methods_before_network(self) -> None:
        """Non-GET methods are rejected without touching the session."""
        api_module = _load_module("api")
        client = api_module.CoinbaseAdvancedApi("organizations/org/apiKeys/key", "secret")
        session = types.SimpleNamespace(request=lambda *args, **kwargs: self.fail("network called"))
        client.session = session

        with self.assertRaises(api_module.CoinbaseAdvancedError) as ctx:
            client.call_rest("POST", "/api/v3/brokerage/orders")

        self.assertIn("read-only", str(ctx.exception))


class DepotValueTests(unittest.TestCase):
    """Depot valuation tests."""

    def test_portfolio_value_uses_non_vault_balances_and_base_rates(self) -> None:
        """Depot value sums account balances in the selected base currency."""
        api_module = _load_module("api")
        accounts = [
            {
                "uuid": "btc",
                "currency": "BTC",
                "available_balance": {"value": "0.25"},
                "hold": {"value": "0.05"},
            },
            {
                "uuid": "usd",
                "currency": "USD",
                "available_balance": {"value": "125.00"},
                "hold": {"value": "0"},
            },
            {
                "uuid": "vault",
                "currency": "ETH",
                "type": "ACCOUNT_TYPE_VAULT",
                "available_balance": {"value": "99"},
                "hold": {"value": "0"},
            },
        ]
        exchange_rates = {
            "currency": "USD",
            "rates": {
                "BTC": "0.00001",
                "USD": "1.0",
                "ETH": "0.0003",
            },
        }

        value = api_module.portfolio_value_in_base(accounts, exchange_rates)

        self.assertEqual(value, 30125.0)


if __name__ == "__main__":
    unittest.main()
