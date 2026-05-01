# Hermes P45 Futu Market Data Readiness Spec

Date: 2026-04-30
Scope: Futu OpenD / futu-api readiness, live market-data smoke checks, append-only readiness artifacts, local CLI, and documentation
Branch: `codex/quant-governance-p20-p30`

## 1. Purpose

P36, P37, P39, P42, and later co-pilot phases depend on market data. Until the Futu path is verified against a live local OpenD gateway, those phases can pass unit tests while still producing weak or stale real-world evidence.

P45 adds a standalone, read-only market-data readiness gate for Futu OpenD:

- detect whether `futu-api` is installed in Hermes' Python runtime;
- detect whether OpenD is reachable at the configured host/port;
- verify basic quote calls against OpenD when available;
- classify SDK, gateway, snapshot, history, option-chain, quota, and permission readiness;
- persist an append-only readiness report;
- write boss-readable JSON/Markdown artifacts under `output/governance/YYYY-MM-DD/`;
- expose a local CLI for manual smoke testing.

P45 is not a trading integration. It is a data-source readiness artifact that lets later phases know whether real market data is usable before relying on P36/P37 evidence.

## 2. Context From Futu Documentation

The official Futu OpenAPI documentation says Futu API consists of:

- OpenD, a local gateway process that exposes TCP interfaces;
- API SDKs, including Python, which connect to OpenD.

The official AI/OpenClaw integration page says the Futu skills package contains:

- `install-futu-opend` for installing OpenD and the Python SDK;
- `futuapi` for market data, trading, and subscriptions.

The downloaded Futu `futuapi` skill states:

- OpenD must be running, default `127.0.0.1:11111`;
- OpenD and SDK should be `>= 10.4.6408`;
- Python SDK import is `from futu import *`;
- quote examples use `OpenQuoteContext`;
- `request_history_kline` should close the context after use;
- `get_market_snapshot` should close the context after use;
- `request_history_kline` has historical-K-line quota limits and supports paging via `page_req_key`;
- trading unlock must be done manually in OpenD GUI; SDK `unlock_trade` must not be used.

P45 must follow the market-data parts only. It must not use Futu trading contexts, account trading APIs, order APIs, or `unlock_trade`.

## 3. Local Preflight Found Before This Spec

This was observed on 2026-04-30 in the local workspace:

- Futu OpenD process is running:
  - `/Applications/Futu_OpenD.app/Contents/MacOS/Futu_OpenD`
  - listening on `127.0.0.1:11111`
- `FUTU_*`, `MOOMOO_*`, and `OPEND_*` environment variables are not set in the shell inspected by Codex.
- `/opt/homebrew/bin/python3.11` cannot import `futu` or `moomoo`.
- `pip show futu-api` does not show an installed package in that Python runtime.
- The official latest `futu-api` version visible via PyPI index is `10.4.6408`.
- A Futu skills package can be downloaded from:
  - `https://openapi.futunn.com/skills/opend-skills.zip`
- The package includes:
  - `skills/futuapi/SKILL.md`
  - `skills/install-futu-opend/SKILL.md`

These observations should be documented in P45 README updates, but runtime behavior must be based on live checks, not on this one-time preflight.

## 4. Existing Hermes Market-Data Files

Existing files:

```text
agent/research_v1/data/futu_opend.py
agent/research_v1/data/providers.py
agent/research_v1/market_data_service.py
agent/research_v1/recommendation_outcomes.py
agent/research_v1/market_regime_context.py
agent/research_v1/batch_cli.py
tests/agent/research_v1/test_futu_provider.py
tests/agent/research_v1/test_market_data_service.py
```

P45 should add a new readiness module rather than mixing readiness logic into P36/P37/P44.

## 5. Non-Goals And Hard Boundaries

P45 must not:

- place trades;
- submit orders;
- cancel orders;
- modify orders;
- query real positions or account balances;
- unlock trading;
- use `OpenSecTradeContext`, `OpenFutureTradeContext`, or any trade context;
- use `unlock_trade`;
- mutate production config;
- approve production adoption;
- train models;
- schedule jobs;
- send notifications;
- start a server or dynamic viewer;
- call `HermesResearchApp.run()`;
- call `final_judge`;
- create `CanonicalSignal` or `CanonicalReport`;
- mutate `JudgeInputPacket`;
- invoke P36-P44 runtimes;
- mutate P36-P44 evidence;
- silently fall back to Yahoo/AkShare when the Futu readiness check is requested.

P45 may import or instantiate `FutuQuoteClient` and read-only quote provider adapters.

## 6. New Module

Create:

```text
agent/research_v1/market_data_readiness.py
```

The module owns:

- SDK import/version check;
- OpenD TCP reachability check;
- optional quote-context live checks;
- row-shape validation for snapshot/history/option-chain/quota calls;
- readiness classification;
- source hash calculation;
- JSON/Markdown artifact writing;
- runtime orchestration.

## 7. Runtime Entrypoint

Add:

```python
def run_market_data_readiness(
    *,
    output_root: Path,
    as_of_date: str,
    host: str = "127.0.0.1",
    port: int = 11111,
    symbols: list[str] | None = None,
    history_days: int = 30,
    option_symbol: str | None = "US.AAPL",
    live: bool = False,
    provider: Any | None = None,
) -> dict[str, Any]:
    ...
```

Default symbols:

```text
US.AAPL
HK.00700
```

Default option symbol:

```text
US.AAPL
```

`live=False` must perform environment checks and produce `provider_not_tested_live` if quote calls are skipped.

`live=True` must attempt quote calls through the injected provider or default Futu provider.

Tests must use injected fake providers and must not require live OpenD.

## 8. CLI

Add a local CLI command:

```bash
python -m agent.research_v1.batch_cli market-data-readiness-run \
  --as-of-date 2026-04-30 \
  --symbols US.AAPL,HK.00700 \
  --history-days 30 \
  --option-symbol US.AAPL \
  --live \
  --output-root output/governance
```

Arguments:

```text
--as-of-date          required YYYY-MM-DD
--symbols             comma-separated symbols, default US.AAPL,HK.00700
--history-days        positive integer, default 30
--option-symbol       optional, default US.AAPL; pass empty string to skip
--host                default from FUTU_OPEND_HOST or 127.0.0.1
--port                default from FUTU_OPEND_PORT or 11111
--live                opt-in live OpenD quote calls
--output-root         default output/governance, resolved under --app-root when relative
```

Exit codes:

```text
0 provider_ready / provider_degraded / provider_not_tested_live
2 blocked_invalid_input
3 provider_unavailable
```

`provider_unavailable` should not be treated as a test failure by itself. It is a useful operator status.

## 9. Readiness Statuses

Top-level statuses:

```text
provider_ready
provider_degraded
provider_unavailable
provider_not_tested_live
blocked_invalid_input
```

Rules:

- `blocked_invalid_input` for invalid date, empty symbols, bad symbol format, non-positive history days, invalid host, or invalid port.
- `provider_not_tested_live` when `live=False` and static checks are complete.
- `provider_unavailable` when SDK import fails, OpenD is unreachable, or every live quote check fails.
- `provider_degraded` when at least one live quote check succeeds but one or more required checks fail or are permission-limited.
- `provider_ready` when SDK, OpenD, snapshot, history, and required option-chain checks succeed with valid row shape.

P45 should be conservative. If a required check is uncertain, degrade rather than ready.

## 10. Component Checks

Produce `checks` as a list of dicts:

```text
check_id
status
severity
details
observed_at
duration_ms
```

Allowed `check_id` values:

```text
sdk_import
sdk_version
opend_tcp
snapshot
history_kline
history_quota
option_chain
user_info
no_trade_context_used
```

Allowed check statuses:

```text
passed
failed
skipped
degraded
permission_limited
not_installed
not_reachable
not_tested_live
```

Allowed severity:

```text
info
warning
critical
```

## 11. SDK Check

SDK check must:

- attempt to import `futu`;
- record `sdk_module = "futu"`;
- record `sdk_version` if available;
- compare against minimum `10.4.6408`;
- never install the package automatically;
- return `not_installed` if import fails.

If SDK is missing, the report must include:

```text
recommended_action: install_futu_api_sdk
operator_command: /opt/homebrew/bin/python3.11 -m pip install futu-api==10.4.6408
```

This command is guidance only. P45 runtime must not execute it.

## 12. OpenD Check

OpenD TCP check must:

- attempt a TCP connect to host/port with a short timeout;
- record whether the connection succeeds;
- avoid sending account credentials;
- not assume OpenD is logged in just because the TCP port is open.

If the port is closed, include:

```text
recommended_action: start_futu_opend_gui
```

## 13. Live Quote Checks

When `live=True` and SDK/OpenD checks pass, P45 must attempt:

1. Snapshot:
   - call `fetch_snapshot(symbols)`;
   - require at least one row;
   - require `code`;
   - prefer `last_price` or compatible Futu snapshot price field;
   - record returned codes.

2. History K-line:
   - call `fetch_history(symbol, start_date, as_of_date)` for each requested symbol;
   - require at least one row per successfully checked symbol;
   - require `date` and `close`;
   - prefer `open`, `high`, `low`, `volume`;
   - record row count by symbol.

3. Option chain:
   - call `fetch_option_chain(option_symbol, start=None, end=None)` if option symbol is non-empty;
   - require at least one row for a pass;
   - if unavailable because of permission, mark `permission_limited`, not fatal by itself;
   - if option symbol is skipped, mark `skipped`.

4. Historical quota/user info if available:
   - may call lightweight quote-context methods if already supported by `FutuQuoteClient`;
   - if not implemented in the current client, mark `skipped` and recommend a future extension.

P45 should not subscribe to real-time push data in v1.

## 14. Provider Adapter

P45 may use a new internal adapter wrapping `FutuQuoteClient`.

Recommended interface:

```python
class MarketDataReadinessProvider(Protocol):
    data_source: str
    def fetch_snapshot(self, symbols: list[str]) -> list[dict]: ...
    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]: ...
    def fetch_option_chain(self, symbol: str, start: str | None = None, end: str | None = None) -> list[dict]: ...
```

Do not reuse `FallbackMarketDataProvider` for P45. P45 is specifically checking Futu.

## 15. Symbol Validation

Accepted prefixes:

```text
US.
HK.
SH.
SZ.
SG.
```

Unprefixed input should be normalized only if explicitly documented:

- `AAPL` may normalize to `US.AAPL` only when `--default-market US` exists.

For P45 v1, require prefixed symbols in CLI to avoid ambiguity.

## 16. Artifact Output

Write:

```text
output/governance/YYYY-MM-DD/p45_market_data_readiness.json
output/governance/YYYY-MM-DD/p45_market_data_readiness.md
```

JSON must include:

```text
schema_version
report_id
as_of_date
created_at
status
host
port
symbols
history_days
option_symbol
live
sdk
opend
checks
snapshot_summary
history_summary
option_chain_summary
permission_summary
recommended_actions
source_hash
disclaimer
```

Markdown must include:

- status;
- host/port;
- SDK version/import status;
- OpenD reachability;
- snapshot/history/option-chain check table;
- recommended actions;
- disclaimer.

## 17. Disclaimer

Every artifact must include:

```text
P45 is market-data provider readiness only. It does not recommend trades, submit orders, unlock trading, query positions, approve production adoption, train models, schedule jobs, or mutate research decisions.
```

Forbidden rendered terms:

```text
buy this now
sell this now
follow this trade
guaranteed edge
production approved
model promoted
execute trade
place order
unlock_trade
OpenSecTradeContext
OpenFutureTradeContext
```

The module may mention these terms in internal constants/tests, but rendered Markdown must not contain forbidden instruction phrasing except where the disclaimer is checked intentionally. Prefer "submit orders" over "place orders".

## 18. Source Hash

`source_hash` must be deterministic SHA-256 over canonical JSON containing:

- schema version;
- as-of date;
- host and port;
- symbols;
- history days;
- option symbol;
- live flag;
- SDK import/version result;
- OpenD TCP result;
- normalized live check summaries;
- returned row counts and returned codes;
- permission-limited reasons.

Do not hash raw full market data rows into P45 v1. P36/P37 own data-path hashes. P45 only hashes readiness summaries.

## 19. Persistence

Extend `ResearchDatabase` with:

```text
market_data_readiness_reports
```

Columns:

```text
report_id TEXT PRIMARY KEY
schema_version TEXT NOT NULL
as_of_date TEXT NOT NULL
created_at TEXT NOT NULL
status TEXT NOT NULL
host TEXT NOT NULL
port INTEGER NOT NULL
symbols_json TEXT NOT NULL
history_days INTEGER NOT NULL
option_symbol TEXT NOT NULL
live INTEGER NOT NULL
source_hash TEXT NOT NULL
report_json TEXT NOT NULL
```

Natural key:

```text
(as_of_date, host, port, symbols_json, history_days, option_symbol, live, source_hash)
```

Same readiness input should be idempotent. Revised readiness evidence should append a new row.

## 20. Tests

Focused tests should cover:

1. SDK missing returns `provider_unavailable` with `install_futu_api_sdk`.
2. SDK version below minimum returns degraded or unavailable with upgrade guidance.
3. OpenD unreachable returns `provider_unavailable`.
4. `live=False` returns `provider_not_tested_live`.
5. Fake provider snapshot/history/option success returns `provider_ready`.
6. Snapshot success + option permission failure returns `provider_degraded`.
7. Invalid date returns `blocked_invalid_input`.
8. Non-positive history days returns `blocked_invalid_input`.
9. Unprefixed symbols are rejected in CLI/runtime.
10. Source hash changes when a check result changes.
11. Persistence is idempotent for identical report.
12. Revised source hash appends a new row.
13. Markdown includes check table and recommended actions.
14. Markdown rejects forbidden trading language.
15. Hard-boundary test confirms no trade contexts, no `unlock_trade`, no P36-P44 runtime calls.
16. CLI success prints status and returns 0.
17. CLI invalid input returns 2.
18. CLI provider unavailable returns 3.
19. Live smoke test is skipped unless `HERMES_LIVE_FUTU=1`.
20. Live smoke test, when enabled, performs read-only snapshot/history checks only.

## 21. Live Test Policy

Normal test suites must not require live Futu OpenD.

Add optional live tests:

```bash
HERMES_LIVE_FUTU=1 /opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_futu_live_smoke.py -q
```

If `HERMES_LIVE_FUTU` is not `1`, these tests must skip.

If the SDK is missing or OpenD is unavailable when live mode is enabled, the test should fail with a clear message because the operator explicitly opted into live verification.

## 22. Documentation

Update:

```text
README.md
agent/research_v1/README.md
agent/research_v1/data/README.md
```

Document:

- P45 purpose;
- Futu does not require a conventional API key in Hermes;
- OpenD must be running and logged in locally;
- Python runtime must install `futu-api`;
- current recommended SDK version is `10.4.6408`;
- `market-data-readiness-run` CLI examples;
- optional live smoke test command;
- no trading authority is added.

## 23. Acceptance Criteria

P45 is accepted when:

- focused P45 tests pass;
- CLI tests pass;
- optional live test is skipped by default and clearly documented;
- doc standards pass;
- P36-P44 regression remains green except known host-specific gaps;
- no trade context/import/order/unlock code is added;
- readiness artifacts write under `output/governance/YYYY-MM-DD/`;
- provider availability is visible as structured evidence for P46.

