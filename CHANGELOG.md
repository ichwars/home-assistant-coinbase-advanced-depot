# Changelog

## 0.4.0-rc7

- Replaced the Coinbase-like brand concept with the neutral Portfolio Pulse brand icon scaled from `ha_coinbase.png`.
- Use the selected brand icon for both `icon.png` and `logo.png` in the repository and integration brand assets.
- Fetch Coinbase portfolio breakdowns and use their total value for the depot value sensor when available.
- Add optional Coinbase portfolio breakdown polling, enabled by default.
- Add portfolio breakdown value sensors for total, crypto, cash, and non-zero futures/equities/PnL values.
- Add portfolio position balance sensors for non-wallet positions such as staked ETH.
- Add richer portfolio position attributes for fiat value, allocation, cost basis, average entry price, unrealized PnL, and available trade/transfer/send amounts.

## 0.4.0-rc6

- Fixed config flow loading by removing an unserializable `str.strip` callable from the Home Assistant form schema.
- Credential values are still trimmed during validation.

## 0.4.0-rc5

- Added root-level `brand/` assets for HACS repository cards while keeping the Home Assistant local brand assets inside the integration directory.

## 0.4.0-rc4

- Added field-level setup help for the Coinbase CDP API key name and private key.
- Trimmed setup credentials and reject empty values before Coinbase validation.
- Clarified that the API key field expects the full CDP API key name, not the display name.

## 0.4.0-rc3

- Fixed German umlauts in the setup and reauthentication dialogs.
- Added a direct link to the Coinbase API key page in the setup and reauthentication dialogs.
- Replaced angle-bracket API key placeholders with safe plain-text examples to avoid Home Assistant frontend translation errors.
- Replaced the local Home Assistant brand icon.

## 0.4.0-rc2

- Removed the `PyJWT` manifest requirement that could prevent Home Assistant from loading the config flow.
- Replaced `PyJWT` usage with local ES256 JWT signing via Home Assistant's existing `cryptography` dependency.

## 0.4.0-rc1

- Refocused the integration as a read-only Coinbase depot monitor.
- Removed all write API options and `POST`/`PUT`/`DELETE` service access.
- Added a total depot value sensor in the configured base currency.
- Added a Home Assistant reauthentication flow for expired or revoked API keys.
- Added local Home Assistant brand assets under `custom_components/coinbase_advanced/brand/`.
- Added project-local regression tests and GitHub Actions validation.
- Replaced the placeholder license with Apache License 2.0.
