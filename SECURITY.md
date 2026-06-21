# Security Policy

## Supported Versions

Security fixes are provided for the latest released version of the integration.

## Reporting a Vulnerability

Please report vulnerabilities through GitHub private vulnerability reporting if it
is available for this repository. If it is not available, open a GitHub issue
with a minimal description and avoid posting secrets, API keys, private keys,
account IDs, balances, or other sensitive depot data.

## Coinbase API Key Guidance

Use a Coinbase Advanced / CDP API key with read-only permissions. This
integration does not require trading, transfer, order, or withdrawal permissions.

Never paste a Coinbase private key into GitHub issues, pull requests, logs, or
screenshots. If a key was exposed, revoke it in Coinbase immediately and create a
new read-only key.
