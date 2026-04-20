# Hermes Agent Roadmap

## Positioning

Hermes is not a general product, collaboration platform, or trading terminal.

Hermes is a boss-only signal engine for a narrow quantitative trading workflow.

The system's job is to generate high-quality buy/sell signals with:

- higher win rate
- better profit/loss ratio
- stronger long-term ROI
- clearer execution rules

The system does **not** optimize around the boss's discretionary behavior.
If the signal engine is strong enough, disciplined follow-through will come from trust in results.

## Core Objective

Build Hermes into a signal system that can answer:

- Which stock is actionable now?
- What is the exact entry, stop, take-profit, and holding horizon?
- Among multiple strong signals, which should be executed first?
- What is the measured historical win rate, drawdown, and ROI of each signal class?
- How does the signal behave under extreme market stress?

## Mainline

The mainline is:

1. Standardize signals
2. Prove signal edge through backtesting
3. Turn research output into executable trade plans
4. Improve signal quality with stronger data and ranking logic
5. Upgrade valuation and risk modules
6. Make the system reliable as a background macOS service
7. Provide a minimal viewer for signals, positions, and alerts

## Priorities

### P0 - Signal Structure Standardization

Goal:
Turn Hermes from a research grader into a real signal engine.

Scope:

- Extend current grading output so every actionable signal includes:
  - `rating`
  - `confidence`
  - `entry_price`
  - `stop_loss`
  - `take_profit`
  - `holding_horizon`
  - `signal_valid_until`
  - `priority_score`
- Add a `signals` table for canonical signal records
- Add a `price_snapshots` table for market price reference at signal time
- Add a `signal_revisions` table so rating and plan changes are traceable
- Update grading logic to include signal validity, not just static letter grades
- Define a uniform signal schema used by grading, monitor, backtest, and viewer

Success condition:

- Every new `S/A/B/C` output can be stored as a structured, executable signal
- Signal records are versioned and tied to a price snapshot

### P1 - Backtest Closed Loop

Goal:
Prove that the signal engine has measurable edge.

Scope:

- Add a `signal_outcomes` table
- Integrate Yahoo Finance historical price data
- Build backtest functions for:
  - 5 trading days
  - 20 trading days
  - 60 trading days
- Compute and store:
  - win rate
  - average return
  - median return
  - max drawdown
  - profit/loss ratio
  - ROI by rating bucket
- Include basic transaction assumptions:
  - commission
  - slippage
- Handle data gaps gracefully:
  - skip or interpolate missing price points based on backtest rules
- Account for survivorship bias in historical backtest scope
- Output statistics by:
  - signal grade
  - holding horizon
  - market regime when available

Success condition:

- Hermes can quantify whether `S` or `A` signals are actually worth following
- The system can produce business-grade evidence, not just narratives

### P2 - Trading Assistant Layer

Goal:
Convert signal output into explicit trading instructions.

Scope:

- Implement a `Trade Plan Generator`
- Every strong signal must produce:
  - buy or no-buy decision
  - entry zone
  - stop-loss
  - take-profit
  - holding horizon
  - invalidation condition
  - suggested position size
- Add position recording and tracking tables
- Upgrade monitor logic from generic alerts to position decision alerts
- Add notification support for actionable events
- Add a minimal paper-trade path so signals can be simulated before real adoption

Success condition:

- Hermes no longer says only "bullish" or "S"
- Hermes says exactly how to act on the signal

### P3 - Signal Quality Improvement

Goal:
Increase signal precision and ranking quality.

Scope:

- Build a provider abstraction layer for market and fundamentals data
- Formalize Yahoo Finance integration under the provider layer
- Add field validation, missing-field handling, freshness checks, and fallback rules
- Add AkShare integration only when A-share coverage is needed
- Introduce lightweight signal portfolio context:
  - sector exposure overlap
  - cross-signal priority ranking among simultaneous strong signals
- Add evidence conflict detection:
  - conflicting source fields
  - analyst/data mismatch
  - confidence penalties for unresolved conflicts
- Introduce analyst dynamic weighting based on historical usefulness

Success condition:

- Hermes ranks multiple strong signals better
- Data quality and evidence quality both begin to affect confidence and priority

### P4 - Valuation And Risk Engine

Goal:
Strengthen the underlying alpha logic and downside control.

Scope:

- Add DCF valuation
- Add DDM valuation where applicable
- Add relative valuation models
- Add risk metrics including:
  - Sharpe ratio
  - Max Drawdown
  - VaR
- Add stress test workflows for extreme market regimes:
  - 2008 financial crisis
  - 2020 COVID crash
  - 2022 rate-hike bear market
- Ensure extreme-regime weakness can be reflected in signal confidence or warnings

Success condition:

- Hermes does not rely only on debate and heuristics
- Hermes has stronger model-based support for signal generation and risk framing

### P5 - macOS Service Mode

Goal:
Make Hermes reliable as a continuously available boss-side signal service.

Scope:

- Add `launchd` plist auto-start
- Add health checks and process recovery
- Add safe idle polling after market close
- Add operational rules for degraded mode when data is unavailable
- Ensure the service can run without manual terminal supervision

Success condition:

- Hermes can stay alive and dependable on macOS with minimal manual care

### P6 - Minimal Viewer

Goal:
Provide the smallest possible interface needed to inspect signals and act on them.

Scope:

- Add a minimal web page for:
  - current signals
  - signal priority
  - open positions
  - alerts
  - paper-trade status
- Keep UI intentionally narrow and non-productized
- Add a lightweight end-of-day review summary generation path

Success condition:

- The boss can open one page and see what matters
- No complex productization or terminal-style build-out is introduced

## Explicit Non-Goals

Hermes will not prioritize:

- Figma work
- multi-user collaboration
- a general terminal product
- broad productization
- adapting strategy around the boss's discretionary behavior

## Execution Rule

Implementation should always protect the mainline:

1. Signal quality first
2. Statistical proof second
3. Execution clarity third
4. Reliability and convenience after that

If a new idea does not improve win rate, profit/loss ratio, ROI, signal ranking, or execution clarity, it is not core work.

## What Success Looks Like

Hermes succeeds when it can consistently do the following:

- generate structured signals worth following
- show measured historical edge
- tell the boss exactly how to execute
- prioritize the best opportunities
- survive bad market regimes with bounded damage

That is the operating definition of the system.
