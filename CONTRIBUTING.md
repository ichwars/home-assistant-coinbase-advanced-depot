# Contributing

Thanks for helping improve Coinbase Advanced Depot Monitor.

## Local Checks

Run these checks before opening a pull request:

```bash
python -B -m unittest discover -s tests -p "test_*.py"
python -B -c "import json; [json.load(open(p, encoding='utf-8')) for p in ['custom_components/coinbase_advanced/manifest.json','custom_components/coinbase_advanced/strings.json','custom_components/coinbase_advanced/translations/en.json','custom_components/coinbase_advanced/translations/de.json','hacs.json']]"
python -B -c "from pathlib import Path; files=list(Path('custom_components/coinbase_advanced').glob('*.py')) + [Path('tests/test_read_only_depot.py')]; [compile(path.read_text(encoding='utf-8'), str(path), 'exec') for path in files]"
```

## Scope

This integration is intentionally read-only. Pull requests that add buying,
selling, transfers, order management, withdrawals, or other write actions are
outside the project scope.

## Sensitive Data

Do not include real Coinbase API keys, private keys, account IDs, balances, or
screenshots containing sensitive depot data in issues, pull requests, tests, or
logs.
