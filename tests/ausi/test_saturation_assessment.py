from ai_web_research.stopping.models import SaturationPolicy, SearchProgressSample
from ai_web_research.stopping.progress import assess_saturation


def sample(index: int, gain: float, *, not_found_count: int = 0) -> SearchProgressSample:
    return SearchProgressSample(
        epoch_index=index,
        new_candidates=0,
        new_independent_source_roots=0,
        new_verified_evidence=0,
        material_gap_reduction=0,
        coverage_gain=0.0,
        marginal_gain=gain,
        not_found_count=not_found_count,
    )


def test_insufficient_history_is_not_saturation():
    state = assess_saturation(
        (sample(0, 0.0), sample(1, 0.0)),
        SaturationPolicy(window_size=3, minimum_samples=3, marginal_gain_threshold=0.1),
    )
    assert state.saturated is False
    assert state.reason_codes == ("INSUFFICIENT_HISTORY",)
    assert state.recent_gains == (0.0, 0.0)


def test_recent_gain_above_threshold_breaks_saturation():
    state = assess_saturation(
        (sample(0, 0.0), sample(1, 0.0), sample(2, 0.5)),
        SaturationPolicy(window_size=3, minimum_samples=3, marginal_gain_threshold=0.1),
    )
    assert state.saturated is False
    assert state.reason_codes == ("MARGINAL_GAIN_ABOVE_THRESHOLD",)


def test_sustained_low_gain_marks_bounded_saturation():
    state = assess_saturation(
        (sample(0, 0.1), sample(1, 0.05), sample(2, 0.0), sample(3, 0.02)),
        SaturationPolicy(window_size=3, minimum_samples=3, marginal_gain_threshold=0.1),
    )
    assert state.saturated is True
    assert state.recent_gains == (0.05, 0.0, 0.02)
    assert state.reason_codes == ("LOW_MARGINAL_GAIN_WINDOW",)
    assert state.scope_note == "bounded to current methods/providers/budget"
    assert "complete" not in state.scope_note.lower()


def test_not_found_only_history_can_signal_local_saturation_but_not_falsity():
    state = assess_saturation(
        (
            sample(0, 0.0, not_found_count=1),
            sample(1, 0.0, not_found_count=2),
            sample(2, 0.0, not_found_count=1),
        ),
        SaturationPolicy(window_size=3, minimum_samples=3, marginal_gain_threshold=0.0),
    )
    assert state.saturated is True
    assert state.reason_codes == ("LOW_MARGINAL_GAIN_WINDOW", "NOT_FOUND_OBSERVED")
    joined = " ".join(state.reason_codes).lower()
    assert "false" not in joined
    assert "complete" not in joined
