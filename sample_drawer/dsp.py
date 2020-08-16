
import math
import logging
import numpy

WAVEFORM_RESOLUTION = 100  # samples per second

logger = logging.getLogger("dsp")


def compute_peak_level(frames):
    peak_level = max(numpy.amax(frames), -numpy.amin(frames))
    if not peak_level:
        peak_level_db = -math.inf
    else:
        try:
            peak_level_db = 20*math.log10(peak_level)
        except ValueError:
            raise ValueError("Cannot convert %r to dBFS" % (peak_level,))
    return peak_level_db


def compute_waveform(frames, samplerate, resolution=WAVEFORM_RESOLUTION):

    length = frames.shape[0]
    channels = frames.shape[1]

    logging.debug("Computing waveform of %r frames %r channels (%r)",
                  length, channels, frames.shape)

    num_slices = int(length * WAVEFORM_RESOLUTION / samplerate)
    slice_len = int(samplerate / WAVEFORM_RESOLUTION)

    tmp_frames = frames[:num_slices * slice_len].transpose()
    sliced = tmp_frames.reshape(channels, -1, slice_len)

    mins = sliced.min(2).min(0)
    maxes = sliced.max(2).max(0)

    waveform = numpy.array([mins, maxes]).transpose()

    return waveform

