"""Tests for subsampled_smooth_calibration_error (SSCE, Affirm/splinator#10).

Implements the Subsampled Smooth Calibration Error of Haghtalab, Qiao,
Yang & Zhao (2024), "Truthfulness of Calibration Measures"
(arXiv:2407.13979), Definition 2.1:

    SSCE(x, p) = E_{S ~ Unif(2^[T])}[ smCE(x|_S, p|_S) ],

rescaled by 2/T into [0, 1] (the paper-scale value lies in [0, T/2]).
"""

import itertools

import numpy as np
import pytest

from splinator import subsampled_smooth_calibration_error
from splinator.metrics import _smooth_calibration_error_raw


def _exact_enumerated_ssce(labels, preds):
    """Exact SSCE by enumerating all 2^T subsets (paper scale rescaled)."""
    n = len(labels)
    total = 0.0
    for r in range(n + 1):
        for combo in itertools.combinations(range(n), r):
            mask = np.zeros(n, dtype=bool)
            mask[list(combo)] = True
            total += _smooth_calibration_error_raw(labels[mask], preds[mask])
    return float(total / (2 ** n) / (n / 2.0))


class TestSmoothCalibrationErrorRaw:
    def test_empty(self):
        assert _smooth_calibration_error_raw([], []) == 0.0

    def test_single_sample(self):
        # sup_{|v|<=1} v * (1 - 0.3) = 0.7
        assert _smooth_calibration_error_raw([1], [0.3]) == pytest.approx(0.7)

    def test_constant_preds_opposite_residuals_cancel(self):
        # residuals +0.5 and -0.5 at the same prediction: single v -> 0
        assert _smooth_calibration_error_raw([1, 0], [0.5, 0.5]) == pytest.approx(0.0)

    def test_constant_preds_aligned(self):
        # residuals +0.5, +0.5 at one prediction: v=1 -> 1.0
        assert _smooth_calibration_error_raw([1, 1], [0.5, 0.5]) == pytest.approx(1.0)

    def test_lipschitz_constraint_binds(self):
        # preds 0 and 1, residuals +1 and -1: best f has f(0)=1, f(1)=0 -> 1.0
        assert _smooth_calibration_error_raw([1, 0], [0.0, 1.0]) == pytest.approx(1.0)

    def test_mismatched_lengths(self):
        with pytest.raises(ValueError):
            _smooth_calibration_error_raw([1, 0], [0.5])


class TestSSCE:
    def test_empty(self):
        assert subsampled_smooth_calibration_error([], []) == 0.0

    def test_mismatched_lengths(self):
        with pytest.raises(ValueError):
            subsampled_smooth_calibration_error([1, 0], [0.5])

    def test_range_bounds(self):
        rng = np.random.default_rng(7)
        labels = (rng.random(300) < 0.5).astype(float)
        preds = rng.random(300)
        err = subsampled_smooth_calibration_error(labels, preds, n_draws=200,
                                                  random_state=7)
        assert 0.0 <= err <= 1.0

    def test_reproducible_with_seed(self):
        rng = np.random.default_rng(3)
        labels = (rng.random(80) < 0.4).astype(float)
        preds = rng.random(80)
        a = subsampled_smooth_calibration_error(labels, preds, n_draws=200,
                                                random_state=11)
        b = subsampled_smooth_calibration_error(labels, preds, n_draws=200,
                                                random_state=11)
        assert a == b

    def test_constant_miscalibration_known_value(self):
        # All labels 0, all preds 0.8: smCE(S) = 0.8*|S| exactly, so
        # E[smCE] = 0.8*T/2 and the rescaled metric is exactly 0.8.
        n = 100
        labels = np.zeros(n)
        preds = np.full(n, 0.8)
        err = subsampled_smooth_calibration_error(labels, preds, n_draws=2000,
                                                  random_state=0)
        assert err == pytest.approx(0.8, abs=0.02)

    def test_single_sample_known_value(self):
        # smCE = 0.7 on S={1}, 0 on S=empty -> E = 0.35, rescaled x2 -> 0.7
        err = subsampled_smooth_calibration_error(np.array([1.0]),
                                                  np.array([0.3]),
                                                  n_draws=4000,
                                                  random_state=1)
        assert err == pytest.approx(0.7, abs=0.02)

    def test_monte_carlo_matches_exact_enumeration(self):
        labels = np.array([1.0, 0.0, 1.0])
        preds = np.array([0.8, 0.2, 0.6])
        exact = _exact_enumerated_ssce(labels, preds)
        approx = subsampled_smooth_calibration_error(labels, preds,
                                                     n_draws=8000,
                                                     random_state=5)
        assert approx == pytest.approx(exact, abs=0.02)

    def test_calibrated_near_zero(self):
        # Truthfully calibrated forecaster: SSCE should be small noise.
        rng = np.random.default_rng(42)
        true_probs = rng.random(400)
        labels = (rng.random(400) < true_probs).astype(float)
        err = subsampled_smooth_calibration_error(labels, true_probs,
                                                  n_draws=500,
                                                  random_state=42)
        assert err < 0.15

    def test_miscalibrated_larger_than_calibrated(self):
        rng = np.random.default_rng(9)
        true_probs = rng.random(300)
        labels = (rng.random(300) < true_probs).astype(float)
        calibrated = subsampled_smooth_calibration_error(labels, true_probs,
                                                         n_draws=500,
                                                         random_state=9)
        # Deliberately misreport: flip probabilities around 0.5
        miscalibrated = subsampled_smooth_calibration_error(
            labels, 1.0 - true_probs, n_draws=500, random_state=9)
        assert miscalibrated > 3 * calibrated
