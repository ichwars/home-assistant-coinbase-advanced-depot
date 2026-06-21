# Changelog

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
