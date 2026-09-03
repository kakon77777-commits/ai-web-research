from __future__ import annotations

from .models import SaturationPolicy, SaturationState, SearchProgressSample


_SCOPE_NOTE = "bounded to current methods/providers/budget"


def assess_saturation(
    samples: tuple[SearchProgressSample, ...],
    policy: SaturationPolicy,
) -> SaturationState:
    recent = tuple(sample.marginal_gain for sample in samples[-policy.window_size:])

    if len(samples) < policy.minimum_samples or len(recent) < policy.window_size:
        return SaturationState(
            saturated=False,
            recent_gains=recent,
            reason_codes=("INSUFFICIENT_HISTORY",),
            scope_note=_SCOPE_NOTE,
        )

    saturated = all(gain <= policy.marginal_gain_threshold for gain in recent)
    if saturated:
        reasons = ["LOW_MARGINAL_GAIN_WINDOW"]
        if any(sample.not_found_count > 0 for sample in samples[-policy.window_size:]):
            reasons.append("NOT_FOUND_OBSERVED")
        return SaturationState(
            saturated=True,
            recent_gains=recent,
            reason_codes=tuple(reasons),
            scope_note=_SCOPE_NOTE,
        )

    return SaturationState(
        saturated=False,
        recent_gains=recent,
        reason_codes=("MARGINAL_GAIN_ABOVE_THRESHOLD",),
        scope_note=_SCOPE_NOTE,
    )
