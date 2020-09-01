
import math

import numpy
import pytest

from numpy.testing import assert_array_equal, assert_allclose

from jajcus.sample_drawer.dsp import compute_peak_level, compute_waveform


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


class TestComputeWaveform:
    def test_mono_silence(self):
        frames = numpy.zeros((1000, 1))
        waveform = compute_waveform(frames, 10000, 10)
        assert_array_equal(waveform, numpy.zeros((10, 2)))

    def test_stereo_silence(self):
        frames = numpy.zeros((1000, 2))
        waveform = compute_waveform(frames, 10000, 10)
        assert_array_equal(waveform, numpy.zeros((10, 2)))

    def test_mono_full_scale(self):
        frames = numpy.resize(numpy.array([[0], [1], [0], [-1]]), (1000, 1))
        waveform = compute_waveform(frames, 10000, 10)
        assert_array_equal(waveform, numpy.array([[-1, 1]]*10))

    def test_stereo_full_scale(self):
        frames = numpy.resize(numpy.array([[0, 0], [1, 0.5], [0, 0], [-0.5, -1]]), (1000, 2))
        waveform = compute_waveform(frames, 10000, 10)
        assert_array_equal(waveform, numpy.array([[-1, 1]]*10))

    def test_rising(self):
        frames = numpy.linspace(0.0, 1.0, 1000).reshape(1000, 1)
        waveform = compute_waveform(frames, 10000, 10)
        expected = numpy.array([
                                [0.0, 0.1],
                                [0.1, 0.2],
                                [0.2, 0.3],
                                [0.3, 0.4],
                                [0.4, 0.5],
                                [0.5, 0.6],
                                [0.6, 0.7],
                                [0.7, 0.8],
                                [0.8, 0.9],
                                [0.9, 1.0]])
        assert_allclose(waveform, expected, atol=0.001)
