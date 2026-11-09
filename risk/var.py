"""One-day empirical historical VaR of fixed-current-weight return shocks."""
import numpy as np


def sorted_losses(returns, confidence):
    """Finite observations only; preserve a negative loss threshold if all gains."""
    r = np.asarray(returns, dtype=float)
    if r.ndim != 1 or len(r) < 2 or not np.isfinite(r).all():
        raise ValueError("Provide at least two finite portfolio returns")
    if not 0 < confidence < 1:
        raise ValueError("Confidence must lie strictly between zero and one")
    return np.sort(-r)


def historical_var(returns, confidence=0.95):
    """VaR is the inverse empirical loss CDF, in return units (0.01 = 1%)."""
    losses = sorted_losses(returns, confidence)
    index = min(int(np.ceil(confidence * len(losses))) - 1, len(losses) - 1)
    return float(losses[index])
