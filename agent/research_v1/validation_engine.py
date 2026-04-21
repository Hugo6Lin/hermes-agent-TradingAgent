"""
Phase 17: Validation Engine.

Lightweight validation annotation layer for the bullish decision system.
Provides historical support, environment fit, failure mode, and confidence
assessment WITHOUT overriding thesis or instrument recommendation.

Not a new decision authority — purely advisory annotation.
"""

from __future__ import annotations

from typing import Any

from agent.research_v1.contracts import ValidationResult


# ---------------------------------------------------------------------------
# Regime detection
# ---------------------------------------------------------------------------

def detect_regime(ticker_context: dict[str, Any]) -> str:
    """
    Detect market regime from available context.

    Uses price candles and market data to classify regime:
    - trend_up: price above rising SMA, low realized vol
    - range_bound: price oscillating near SMA, moderate realized vol
    - high_volatility: elevated realized vol or IV percentile
    - risk_off: elevated vol + bearish price signal
    - unknown: insufficient data

    All rules are transparent and rule-based — no black-box models.
    """
    candles = ticker_context.get("candles") or []
    market_data = ticker_context.get("market_data") or {}
    iv_percentile = float(market_data.get("iv_percentile", 0.5))
    last_price = float(market_data.get("last_price", 0.0))

    if not candles or len(candles) < 5:
        return "unknown"

    try:
        close_prices = [float(c.get("close", 0)) for c in candles if c.get("close")]
    except (TypeError, ValueError):
        return "unknown"

    if len(close_prices) < 5 or last_price <= 0:
        return "unknown"

    # Compute 20-day SMA (or available length)
    sma_period = min(20, len(close_prices))
    sma = sum(close_prices[-sma_period:]) / sma_period

    # Compute realized volatility proxy: average of daily range / price
    ranges = []
    for i in range(1, min(20, len(close_prices))):
        high_val = float(candles[-i].get("high", close_prices[-i]))
        low_val = float(candles[-i].get("low", close_prices[-i]))
        if low_val > 0:
            ranges.append((high_val - low_val) / low_val)
    realized_vol = sum(ranges) / len(ranges) if ranges else 0.0

    # Regime classification
    price_vs_sma = (last_price - sma) / sma if sma > 0 else 0.0
    vol_threshold = 0.03  # 3% average daily range = high vol
    iv_high = iv_percentile >= 0.75
    iv_very_high = iv_percentile >= 0.88

    # High volatility: elevated realized vol OR very high IV
    if realized_vol >= vol_threshold or iv_very_high:
        # Distinguish risk_off from plain high_volatility
        if price_vs_sma < -0.05:
            return "risk_off"
        return "high_volatility"

    # Trend up: price above SMA and not high vol
    if price_vs_sma > 0.03:
        return "trend_up"

    # Range bound: price near SMA, moderate vol
    return "range_bound"


# ---------------------------------------------------------------------------
# Historical support assessment
# ---------------------------------------------------------------------------

def assess_historical_support(
    thesis: Any,
    valuation: dict[str, Any],
    catalysts: dict[str, Any],
    regime: str,
) -> str:
    """
    Assess how well the current thesis is historically supported.

    Rule-based (no real backtesting):
    - strong: thesis=Investable + good regime fit + clear catalyst + valuation supports
    - moderate: thesis=Investable but regime mixed OR catalyst moderate
    - weak: thesis=Watchlist/NoTrade OR regime=high_volatility/risk_off OR iv too high
    """
    quality = getattr(thesis, "quality_score", 0.0) if thesis else 0.0
    classification = getattr(thesis, "classification", "Watchlist") if thesis else "Watchlist"
    catalyst_score = catalysts.get("clarity", 0.0) if catalysts else 0.0
    valuation_upside = float(valuation.get("upside_pct", 0.0)) if valuation else 0.0

    # Weak signals
    if classification == "No Trade":
        return "weak"
    if regime in {"high_volatility", "risk_off"}:
        return "weak"
    if quality < 0.45:
        return "weak"

    # Strong signals
    is_investable = classification == "Investable"
    has_upside = valuation_upside >= 0.15
    has_catalyst = catalyst_score >= 0.5
    regime_ok = regime in {"trend_up", "range_bound"}

    strong_count = sum([is_investable, has_upside, has_catalyst, regime_ok])
    if strong_count >= 3 and quality >= 0.65:
        return "strong"

    # Moderate: everything in between
    return "moderate"


# ---------------------------------------------------------------------------
# Environment fit
# ---------------------------------------------------------------------------

def assess_environment_fit(
    regime: str,
    iv_percentile: float,
    liquidity_ok: bool = True,
) -> str:
    """
    Assess how well the current environment fits an options/equity trade.

    - good: regime=trend_up + low/moderate IV + liquid
    - mixed: regime=range_bound OR moderate IV
    - poor: regime=risk_off OR very high IV OR illiquid
    """
    if regime == "risk_off":
        return "poor"
    if not liquidity_ok:
        return "poor"
    if iv_percentile >= 0.88:
        return "poor"
    if regime == "trend_up" and iv_percentile < 0.65:
        return "good"
    if regime == "range_bound" and iv_percentile < 0.70:
        return "good"
    return "mixed"


# ---------------------------------------------------------------------------
# Failure mode inference
# ---------------------------------------------------------------------------

def infer_failure_mode(
    instrument_action: str,
    regime: str,
    iv_percentile: float,
    liquidity_ok: bool = True,
) -> str:
    """
    Infer the most likely failure mode for a given instrument action.

    Rules (transparent, no black-box):
    - liquidity problems: always liquidity if liquidity_ok=False
    - Buy Stock: primarily direction risk
    - Buy Call: timing risk OR iv risk (calls expensive in high IV)
    - Bull Call Spread: timing (needs move within spread width)
    - Sell Cash-Secured Put: direction (needs stock to not fall hard)
    - Covered Call: primarily timing / opportunity cost
    """
    if not liquidity_ok:
        return "liquidity"

    action_lower = instrument_action.lower() if instrument_action else ""

    if "buy call" in action_lower:
        if regime == "high_volatility" or iv_percentile >= 0.75:
            return "iv"
        return "timing"

    if "bull call spread" in action_lower:
        return "timing"

    if "sell cash-secured put" in action_lower or "cash-secured put" in action_lower:
        return "direction"

    if "covered call" in action_lower:
        return "timing"

    if "buy stock" in action_lower or action_lower == "buy":
        return "direction"

    return "none"


# ---------------------------------------------------------------------------
# Validation confidence
# ---------------------------------------------------------------------------

def compute_validation_confidence(
    thesis: Any,
    instrument_action: str,
    regime: str,
    iv_percentile: float,
    liquidity_ok: bool,
    catalyst_score: float,
) -> float:
    """
    Compute a 0.0–1.0 validation confidence score.

    Factors weighted:
    - Thesis classification (Investable adds confidence)
    - Regime fit (trend_up/range_bound OK, risk_off/high_volatility reduces)
    - IV environment (very high IV reduces confidence for long options)
    - Liquidity (illiquid reduces)
    - Catalyst clarity (strong catalyst adds)

    Simple additive model with bounds — no complex formula.
    """
    confidence = 0.5  # baseline

    # Thesis quality boosts confidence
    if thesis:
        quality = getattr(thesis, "quality_score", 0.0)
        if quality >= 0.75:
            confidence += 0.15
        elif quality >= 0.55:
            confidence += 0.08

        classification = getattr(thesis, "classification", "")
        if classification == "Investable":
            confidence += 0.10

    # Regime adjustments
    if regime == "trend_up":
        confidence += 0.08
    elif regime == "range_bound":
        confidence += 0.03
    elif regime in {"high_volatility", "risk_off"}:
        confidence -= 0.12

    # IV: very high IV hurts long options confidence
    if instrument_action and any(kw in instrument_action.lower() for kw in ["buy call", "bull call spread"]):
        if iv_percentile >= 0.88:
            confidence -= 0.15
        elif iv_percentile >= 0.75:
            confidence -= 0.07

    # Liquidity
    if not liquidity_ok:
        confidence -= 0.10

    # Catalyst
    if catalyst_score >= 0.7:
        confidence += 0.08
    elif catalyst_score < 0.4:
        confidence -= 0.06

    # Bound to [0.3, 0.95] — never claim total certainty, never claim worthless
    return max(0.3, min(0.95, confidence))


# ---------------------------------------------------------------------------
# Main evaluation entry point
# ---------------------------------------------------------------------------

def evaluate(
    ticker: str,
    thesis: Any,
    instrument_action: str,
    ticker_context: dict[str, Any],
    valuation: dict[str, Any],
    catalysts: dict[str, Any],
) -> ValidationResult:
    """
    Produce a ValidationResult for a given ticker + thesis + instrument.

    This is the main public API of the ValidationEngine.

    Args:
        ticker: Stock ticker symbol.
        thesis: UnderlyingThesis object (or None).
        instrument_action: Primary instrument action string (e.g. "Buy Call").
        ticker_context: Market data context dict with candles, market_data, etc.
        valuation: Valuation dict (may include upside_pct).
        catalysts: Catalysts dict (may include clarity score).

    Returns:
        ValidationResult with regime, historical_support, environment_fit,
        main_failure_mode, validation_confidence, and notes.
    """
    market_data = ticker_context.get("market_data") or {}
    iv_percentile = float(market_data.get("iv_percentile", 0.5))
    liquidity_ok = bool(market_data.get("liquidity_ok", True))

    regime = detect_regime(ticker_context)
    historical_support = assess_historical_support(thesis, valuation, catalysts, regime)
    environment_fit = assess_environment_fit(regime, iv_percentile, liquidity_ok)
    main_failure_mode = infer_failure_mode(instrument_action, regime, iv_percentile, liquidity_ok)
    catalyst_score = catalysts.get("clarity", 0.0) if catalysts else 0.0
    validation_confidence = compute_validation_confidence(
        thesis, instrument_action, regime, iv_percentile, liquidity_ok, catalyst_score
    )

    # Build notes summary
    notes_parts = [
        f"Regime: {regime}",
        f"Historical support: {historical_support}",
        f"Environment fit: {environment_fit}",
        f"Primary failure mode: {main_failure_mode}",
    ]
    if thesis:
        notes_parts.append(f"Thesis quality: {getattr(thesis, 'quality_score', 0.0):.0%}")
    notes_parts.append(f"Validation confidence: {validation_confidence:.0%}")
    notes = "; ".join(notes_parts)

    return ValidationResult(
        ticker=ticker,
        regime=regime,
        historical_support=historical_support,
        environment_fit=environment_fit,
        main_failure_mode=main_failure_mode,
        validation_confidence=validation_confidence,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# ValidationEngine class
# ---------------------------------------------------------------------------

class ValidationEngine:
    """
    Phase 17 engine: produces ValidationResult annotations for bullish decisions.

    All methods are stateless — no side effects, no persistence.
    Persistence is handled by the app layer calling database.save_validation_result().
    """

    def detect_regime(self, ticker_context: dict[str, Any]) -> str:
        return detect_regime(ticker_context)

    def assess_historical_support(
        self, thesis: Any, valuation: dict, catalysts: dict, regime: str
    ) -> str:
        return assess_historical_support(thesis, valuation, catalysts, regime)

    def infer_failure_mode(
        self,
        instrument_action: str,
        regime: str,
        iv_percentile: float,
        liquidity_ok: bool,
    ) -> str:
        return infer_failure_mode(instrument_action, regime, iv_percentile, liquidity_ok)

    def evaluate(
        self,
        ticker: str,
        thesis: Any,
        instrument_action: str,
        ticker_context: dict[str, Any],
        valuation: dict[str, Any],
        catalysts: dict[str, Any],
    ) -> ValidationResult:
        """
        Main entry point. Returns a ValidationResult annotation.

        Does NOT override thesis, instrument recommendation, or any decision.
        Purely advisory — annotation layer only.
        """
        return evaluate(
            ticker=ticker,
            thesis=thesis,
            instrument_action=instrument_action,
            ticker_context=ticker_context,
            valuation=valuation,
            catalysts=catalysts,
        )
