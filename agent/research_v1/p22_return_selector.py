"""Return-basis selection for P22 diagnostics.

P22 IC/ICIR/decay diagnostics default to net_return_pct.
Gross returns are available for comparison but never the default.
"""

from __future__ import annotations


def select_forward_return(observation: dict, return_basis: str = "net") -> float:
    """Select return value based on return_basis.

    Args:
        observation: ForwardReturnObservation dict (or similar) with return fields.
        return_basis: "net" (default) or "gross".

    Returns:
        float return value.

    Raises:
        ValueError: if required field is missing or return_basis is unknown.
    """
    if return_basis == "net":
        if "net_return_pct" in observation and observation["net_return_pct"] is not None:
            return float(observation["net_return_pct"])
        raise ValueError("net_return_pct is required for net return_basis")
    if return_basis == "gross":
        if "gross_return_pct" in observation and observation["gross_return_pct"] is not None:
            return float(observation["gross_return_pct"])
        if "return_value" in observation and observation["return_value"] is not None:
            return float(observation["return_value"])
        raise ValueError("gross_return_pct or return_value is required for gross return_basis")
    raise ValueError(f"unknown return_basis: {return_basis}")
