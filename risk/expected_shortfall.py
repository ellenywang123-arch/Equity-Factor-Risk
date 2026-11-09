"""One-day historical ES with exact probability mass at the empirical boundary."""
import numpy as np
from .var import sorted_losses


def historical_es(returns, confidence=0.95):
    """Average worst (1-confidence) mass, fractionally weighting the boundary."""
    descending = sorted_losses(returns, confidence)[::-1]
    mass = (1-confidence) * len(descending)
    whole = int(np.floor(mass))
    fraction = mass - whole
    total = descending[:whole].sum()
    if fraction > 0 and whole < len(descending):
        total += fraction * descending[whole]
    return float(total / mass)
