# Futu OpenD Integration for Hermes

Hermes now treats **Futu OpenD** as the preferred local market-data gateway for:

- U.S. equities
- Hong Kong equities
- U.S. stock options
- Hong Kong stock options

If Futu OpenD is unavailable for historical prices, Hermes falls back to Yahoo history.

## What Was Added

- Official Futu skills copied into:
  - `E:\hermes-agent\skills\futuapi`
  - `E:\hermes-agent\skills\install-futu-opend`
- Official legal notices copied into:
  - `E:\hermes-agent\docs\skills\LEGAL_Futu_api_en.md`
  - `E:\hermes-agent\docs\skills\LEGAL_Futu_api_cn.md`
- Hermes provider integration:
  - `agent/research_v1/data/futu_opend.py`
  - `agent/research_v1/data/providers.py`
- Hermes CLI additions:
  - `python -m agent.research_v1.app quote --symbols AAPL,HK.00700`
  - `python -m agent.research_v1.app option-chain --symbol GLW --start 2027-01-01 --end 2027-01-31`

## OpenD Location

Downloaded archive:

- `D:\FutuOpenD\Futu_OpenD_10.3.6308_Windows.7z`

Extracted package:

- `D:\FutuOpenD\Futu_OpenD_10.3.6308_Windows\...`

The GUI installer launched from:

- `D:\FutuOpenD\Futu_OpenD_10.3.6308_Windows\Futu_OpenD_10.3.6308_Windows\Futu_OpenD-GUI_10.3.6308_Windows\Futu_OpenD-GUI_10.3.6308_Windows.exe`

## Required User Step

OpenD requires you to complete the GUI install and login flow yourself.

If the installer or OpenD asks for:

- login account
- login password
- two-factor confirmation

complete that step in the GUI, then return here.

## Hermes Runtime Defaults

Hermes reads these environment variables:

- `FUTU_OPEND_HOST`
  - default: `127.0.0.1`
- `FUTU_OPEND_PORT`
  - default: `11111`
- `FUTU_DEFAULT_MARKET`
  - default: `US`

Examples:

```powershell
$env:FUTU_OPEND_HOST="127.0.0.1"
$env:FUTU_OPEND_PORT="11111"
$env:FUTU_DEFAULT_MARKET="US"
```

## CLI Usage

Query stock snapshots:

```bash
python -m agent.research_v1.app quote --symbols AAPL,HK.00700
```

Query an option chain:

```bash
python -m agent.research_v1.app option-chain --symbol GLW --start 2027-01-01 --end 2027-01-31
```

Symbols without a market prefix default to `US.`.

Examples:

- `AAPL` -> `US.AAPL`
- `GLW` -> `US.GLW`
- `HK.00700` stays `HK.00700`

## Provider Priority

For historical market data, Hermes now prefers:

1. `FutuMarketDataProvider`
2. `YahooMarketDataProvider`

This is wired through `build_default_market_data_provider()`.

## Official References

- Futu OpenD overview: https://openapi.futunn.com/futu-api-doc/en/opend/opend-intro.html
- Command line OpenD: https://openapi.futunn.com/futu-api-doc/en/opend/opend-cmd.html
- Market snapshot: https://openapi.futunn.com/futu-api-doc/en/quote/get-market-snapshot.html
- Option chain: https://openapi.futunn.com/futu-api-doc/en/quote/get-option-chain.html
- Futu API skills page: https://openapi.futunn.com/futu-api-doc/en/file/futu-openapi-skills-EN.html

## Notes

- The Futu option-chain endpoint returns static chain rows. To inspect dynamic option quote fields, use the returned option codes with snapshot queries.
- If OpenD is offline or not logged in, Hermes quote commands will fail until OpenD is available.
- For historical price fallback, Hermes skips failing providers and continues down the chain.
