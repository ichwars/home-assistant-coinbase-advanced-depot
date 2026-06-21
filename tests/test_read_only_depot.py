"""Regression tests for the read-only Coinbase depot model."""

from __future__ import annotations

import importlib.util
import inspect
import json
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
    hashes = types.ModuleType("cryptography.hazmat.primitives.hashes")
    hashes.SHA256 = lambda: object()
    sys.modules["cryptography.hazmat.primitives.hashes"] = hashes
    primitives.hashes = hashes
    asymmetric = sys.modules.setdefault(
        "cryptography.hazmat.primitives.asymmetric",
        types.ModuleType("cryptography.hazmat.primitives.asymmetric"),
    )
    ec = types.ModuleType("cryptography.hazmat.primitives.asymmetric.ec")
    ec.ECDSA = lambda algorithm: ("ecdsa", algorithm)
    utils = types.ModuleType("cryptography.hazmat.primitives.asymmetric.utils")
    utils.decode_dss_signature = lambda signature: (1, 2)
    sys.modules["cryptography.hazmat.primitives.asymmetric.ec"] = ec
    sys.modules["cryptography.hazmat.primitives.asymmetric.utils"] = utils
    asymmetric.ec = ec
    asymmetric.utils = utils

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


class PackagingTests(unittest.TestCase):
    """Packaging contract tests for Home Assistant loading."""

    def test_manifest_does_not_require_pyjwt(self) -> None:
        """The integration must not trigger HA requirement installation for PyJWT."""
        manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))

        self.assertNotIn("PyJWT==2.10.1", manifest.get("requirements", []))

    def test_api_does_not_import_jwt_package(self) -> None:
        """JWT signing must be implemented without importing the external jwt package."""
        source = (INTEGRATION / "api.py").read_text(encoding="utf-8")

        self.assertNotIn("import jwt", source)

    def test_config_flow_schema_avoids_unserializable_python_callables(self) -> None:
        """Home Assistant serializes config flow schemas for the frontend."""
        source = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")

        self.assertNotIn("str.strip", source.partition("def _csv_items")[0])


class BrandAssetTests(unittest.TestCase):
    """Brand asset placement tests."""

    def test_brand_assets_exist_for_home_assistant_and_hacs(self) -> None:
        """Expose icons for HA local brands and HACS repository cards."""
        repo_brand = ROOT / "brand"
        integration_brand = INTEGRATION / "brand"

        for directory in (repo_brand, integration_brand):
            self.assertGreater((directory / "icon.png").stat().st_size, 0)
            self.assertGreater((directory / "logo.png").stat().st_size, 0)


class TranslationTests(unittest.TestCase):
    """Translation regression tests for Home Assistant frontend rendering."""

    def _walk_strings(self, value):
        """Yield all strings nested inside dictionaries and lists."""
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from self._walk_strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from self._walk_strings(item)

    def test_translations_do_not_contain_angle_bracket_placeholders(self) -> None:
        """HA's frontend translator treats angle-bracket placeholders as tags."""
        files = [
            INTEGRATION / "strings.json",
            INTEGRATION / "translations" / "en.json",
            INTEGRATION / "translations" / "de.json",
        ]

        offenders: list[str] = []
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            offenders.extend(
                f"{path.name}: {text}"
                for text in self._walk_strings(data)
                if "<" in text or ">" in text
            )

        self.assertEqual(offenders, [])

    def test_german_translation_uses_real_umlauts(self) -> None:
        """German UI strings should not use ASCII fallback spellings."""
        german = (INTEGRATION / "translations" / "de.json").read_text(encoding="utf-8")

        self.assertNotIn("benoetigt", german)
        self.assertNotIn("gehoeren", german)
        self.assertNotIn("fuer", german)
        self.assertIn("benötigt", german)

    def test_setup_description_links_to_coinbase_api_keys(self) -> None:
        """The setup dialog should link directly to the Coinbase API key page."""
        strings = json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))

        description = strings["config"]["step"]["user"]["description"]

        self.assertIn("https://portal.cdp.coinbase.com/access/api", description)

    def test_setup_fields_explain_key_name_and_secret(self) -> None:
        """Field help should explain what values Coinbase users need to paste."""
        strings = json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))
        user_step = strings["config"]["step"]["user"]

        self.assertIn("data_description", user_step)
        self.assertIn("organizations/ORG_ID/apiKeys/KEY_ID", user_step["data_description"]["api_key"])
        self.assertIn("private key", user_step["data_description"]["api_token"].lower())

    def test_invalid_key_format_message_mentions_key_name(self) -> None:
        """The format error should distinguish the key name from the secret."""
        strings = json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))

        message = strings["config"]["error"]["invalid_key_format"]

        self.assertIn("API key name", message)


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
