# Coinbase Advanced Depot Monitor for Home Assistant

[![CI](https://github.com/ichwars/home-assistant-coinbase-advanced-depot/actions/workflows/ci.yml/badge.svg)](https://github.com/ichwars/home-assistant-coinbase-advanced-depot/actions/workflows/ci.yml)

Custom integration domain: `coinbase_advanced`.

This version uses direct Coinbase CDP REST JWT signing and does **not** depend on
`coinbase-advanced-py`. That avoids dependency conflicts with Home Assistant's
`websockets` constraints while still allowing read-only REST access to Coinbase
Advanced depot data.

The integration is intentionally read-only. It does not buy, sell, transfer,
cancel orders or expose any other trading action.

## Install

### HACS custom repository

Add this repository as a HACS custom repository:

```text
https://github.com/ichwars/home-assistant-coinbase-advanced-depot
```

Category: `Integration`

### Manual install

Copy `custom_components/coinbase_advanced` to
`/config/custom_components/coinbase_advanced`, then restart Home Assistant.

## Setup

Use a Coinbase Developer Platform / Advanced Trade API key:

- API key: `organizations/{org_id}/apiKeys/{key_id}`
- API secret: EC private key from the downloaded CDP key JSON

Use a read-only API key. Trading permissions are not needed and are not used.

The secret field accepts PEM newlines as real newlines or as literal `\n`.

## Sensors

Options allow selecting:

- total depot value in the configured base currency
- wallet balance currencies/assets, e.g. `BTC, ETH, USDC` (not `ETH-USD`)
- product price sensors/market pairs, e.g. `BTC-USD, ETH-USD`
- exchange-rate currencies, e.g. `BTC, ETH, EUR`
- exchange-rate base currency, e.g. `USD`

Wallet behavior in version 0.4.0-rc4:

- A depot value sensor is always created and sums non-vault account balances in the configured base currency.
- If `account_balance_currencies` is empty, only non-vault accounts with a non-zero balance create wallet sensors.
- If `account_balance_currencies` is set, only those currencies create wallet sensors.
- `include_zero_balances` can be enabled to show every non-vault zero-balance account returned by Coinbase.
- Stale wallet/product/rate entities created by older options are removed automatically on reload.

## Services

### `coinbase_advanced.api_call`

Read-only REST call. Only `GET` is supported. Example:

```yaml
service: coinbase_advanced.api_call
data:
  path: /api/v3/brokerage/accounts
```

### `coinbase_advanced.refresh`

Force a refresh of one config entry.


## Options quick guide

- `account_balance_currencies`: wallet assets such as `ETH`, `BTC`, `USDC`. Leave empty to show only wallets with non-zero balances. If you accidentally enter `ETH-USD`, the integration normalizes it to `ETH`.
- `products`: Coinbase market pairs such as `ETH-USD`, `BTC-USD`. If you enter a single asset like `ETH`, it is normalized to `ETH-<exchange_base>`; with `exchange_base=USD`, that becomes `ETH-USD`.
- `exchange_rate_currencies`: target currencies for exchange-rate sensors, such as `EUR`, `BTC`, `ETH`.

## Home Assistant picture

Home Assistant 2026.3 and newer can load local custom-integration brand images
from `custom_components/coinbase_advanced/brand/`. This repository includes:

- `brand/icon.png`
- `brand/logo.png`

Older Home Assistant versions can still use the integration, but may not display
the local picture.

## v0.4.0-rc4 changes

- Added field-level help for the Coinbase CDP API key name and private key.
- Trimmed setup credentials and reject empty values before Coinbase validation.
- Clarified that the first field expects the full CDP API key name, not the display name.

## v0.4.0-rc3 changes

- Fixed German umlauts in the setup dialog.
- Added a direct Coinbase API key page link to the setup and reauthentication dialogs.
- Replaced angle-bracket API key placeholders that could trigger frontend translation errors.
- Replaced the local Home Assistant brand icon.

## v0.4.0-rc2 changes

- Removed the `PyJWT` manifest requirement so Home Assistant can load the config flow without installing extra packages.
- Replaced `PyJWT` usage with local ES256 JWT signing via `cryptography`.

## v0.4.0-rc1 changes

- Refocused the integration as a read-only Coinbase depot monitor.
- Removed write API options and all `POST`/`PUT`/`DELETE` service access.
- Added a total depot value sensor in the configured base currency.
- Added local Home Assistant brand picture assets.
