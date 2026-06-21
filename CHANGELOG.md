# Changelog

## 0.4.0-rc1

- Refocused the integration as a read-only Coinbase depot monitor.
- Removed all write API options and `POST`/`PUT`/`DELETE` service access.
- Added a total depot value sensor in the configured base currency.
- Added a Home Assistant reauthentication flow for expired or revoked API keys.
- Added local Home Assistant brand assets under `custom_components/coinbase_advanced/brand/`.
- Added project-local regression tests and GitHub Actions validation.
- Replaced the placeholder license with Apache License 2.0.
