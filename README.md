# Coinbase Advanced Depot Monitor for Home Assistant

[![CI](https://github.com/ichwars/home-assistant-coinbase-advanced-depot/actions/workflows/ci.yml/badge.svg)](https://github.com/ichwars/home-assistant-coinbase-advanced-depot/actions/workflows/ci.yml)

Custom integration domain: `coinbase_advanced`.

This is an unofficial community integration and is not affiliated with,
endorsed by, or sponsored by Coinbase. Coinbase and related marks are
trademarks of Coinbase.

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

Wallet and portfolio behavior in version 0.4.0-rc8 and newer:

- A depot value sensor is always created. It prefers Coinbase portfolio breakdown totals when available, so staked funds are included in the total depot value.
- Portfolio breakdown sensors are enabled by default and create a separate portfolio sensor area for total value, crypto value, cash value, and non-zero futures/equities/PnL values when Coinbase reports them.
- If `account_balance_currencies` is empty, only non-vault accounts with a non-zero balance create wallet sensors.
- If `account_balance_currencies` is set, only those currencies create wallet sensors.
- `include_zero_balances` can be enabled to show every non-vault zero-balance account returned by Coinbase.
- Staked funds returned by Coinbase portfolio breakdowns, such as staked `ETH`, create position balance sensors even when the account wallet endpoint reports `ETH2` or `CBETH` as zero. These position sensors include attributes for fiat value, allocation, cost basis, average entry price, unrealized PnL, available trade/transfer/send amounts, asset color, asset UUID, and cash marker when Coinbase provides them.
- Stale wallet/product/rate entities created by older options are removed automatically on reload.
- Diagnostics include compact portfolio metadata, portfolio breakdown section counts, and the latest Coinbase rate-limit headers seen by the API client.

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

- `account_balance_currencies`: wallet and portfolio-position assets such as `ETH`, `BTC`, `USDC`. Leave empty to show only balances with non-zero values. If you accidentally enter `ETH-USD`, the integration normalizes it to `ETH`.
- `include_portfolio_breakdown`: enabled by default. Includes Coinbase portfolio breakdown totals and positions, including staked funds.
- `products`: Coinbase market pairs such as `ETH-USD`, `BTC-USD`. If you enter a single asset like `ETH`, it is normalized to `ETH-<exchange_base>`; with `exchange_base=USD`, that becomes `ETH-USD`.
- `exchange_rate_currencies`: target currencies for exchange-rate sensors, such as `EUR`, `BTC`, `ETH`.

## Home Assistant picture

Home Assistant 2026.3 and newer can load local custom-integration brand images
from `custom_components/coinbase_advanced/brand/`. This repository includes:

- `icon.png`
- `logo.png`
- `brand/icon.png`
- `brand/logo.png`
- `custom_components/coinbase_advanced/brand/icon.png`
- `custom_components/coinbase_advanced/brand/logo.png`

Older Home Assistant versions can still use the integration, but may not display
the local picture.

HACS update cards can still show the central Home Assistant Brands placeholder
until HACS uses local custom-integration brands for update entities or its
remote brand cache refreshes. The integration ships the local Home Assistant
brand assets and root-level fallback assets, but the legacy HACS update entity
picture is served from `https://brands.home-assistant.io/_/coinbase_advanced/icon.png`.

## v0.4.0-rc8 changes

- Added root-level `icon.png` and `logo.png` fallbacks in addition to the HACS/HA brand directories.
- Added asset color, asset UUID, and cash marker attributes for portfolio position sensors.
- Added diagnostics for portfolio metadata, portfolio breakdown section counts, and latest Coinbase rate-limit headers.
- Documented the current HACS update-card placeholder limitation for central Home Assistant Brands CDN images.

## v0.4.0-rc7 changes

- Added optional Coinbase portfolio breakdown polling, enabled by default.
- Added portfolio breakdown value sensors for total, crypto, cash, and non-zero futures/equities/PnL values.
- Added richer portfolio position attributes for staked funds and other non-wallet positions.
- Replaced the integration icon and logo with the selected Portfolio Pulse brand asset.

## v0.4.0-rc6 changes

- Fixed config flow loading by removing an unserializable `str.strip` callable from the Home Assistant form schema.
- Credential values are still trimmed during validation.

## v0.4.0-rc5 changes

- Added root-level `brand/` assets for HACS repository cards while keeping the Home Assistant local brand assets inside the integration directory.

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
