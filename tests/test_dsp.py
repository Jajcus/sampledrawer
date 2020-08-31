
import math

import numpy
import pytest

from jajcus.sample_drawer.dsp import compute_peak_level


class TestComputePeakLevel:
    def test_stereo_silence(self):
        frames = numpy.array([[0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]])
        level = compute_peak_level(frames)
        assert level == -math.inf

    def test_mono_full_scale(self):
        frames = numpy.array([[0.0], [1.0], [0.0], [-1.0], [0.0]])
        level = compute_peak_level(frames)
        assert level == 0

    def test_stereo_full_scale(self):
        frames = numpy.array([[0.0, 0.0], [0.9, 1.0], [0.0, 0.0], [-0.9, -1.0], [0.0, 0.0]])
        level = compute_peak_level(frames)
        assert level == 0

    def test_stereo_half_scale(self):
        frames = numpy.array([[0.0, 0.0], [0.5, 0.5], [0.0, 0.0], [-0.5, -0.5], [0.0, 0.0]])
        level = compute_peak_level(frames)
        assert level == pytest.approx(-6.02059991)

    def test_stereo_half_scale_asymmetric(self):
        frames = numpy.array([[0.0, 0.0], [0.25, 0.25], [0.5, 0.5], [0.25, 0.25], [0.0, 0.0]])
        level = compute_peak_level(frames)
        # is this really the value we want here in this case?
        assert level == pytest.approx(-6.02059991)

    def test_stereo_half_scale_asymmetric_negative(self):
        frames = numpy.array([[0.0, 0.0], [0.25, 0.25], [-0.5, -0.5], [-0.25, -0.25], [0.0, 0.0]])
        level = compute_peak_level(frames)
        # is this really the value we want here in this case?
        assert level == pytest.approx(-6.02059991)
