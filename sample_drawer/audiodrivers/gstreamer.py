"""Audio decoding and playback through GStreamer."""

import logging
import threading

import gi; gi.require_version('Gst', '1.0')  # noqa: E702 prevent E402 in subsequent imports
from gi.repository import Gst, GLib

from .driver import AudioState, PositionPollingAudioDriver, AudioDriverError

logger = logging.getLogger("audiodrivers.gstreamer")

STATE_CHANGE_TIMEOUT = 10000000000


def _get_gst_sinks():
    try:
        reg = Gst.Registry.get()
        features = reg.get_feature_list(Gst.ElementFactory)
        result = [(el.get_name(), el.get_metadata('long-name'))
                  for el in features
                  if el.get_metadata('klass') == "Sink/Audio"]
    except GLib.Error as err:
        logger.debug("Cannot retrieve GStreamer registry: %s", err)
        return []
    return result


class GStreamerAudioDriver(PositionPollingAudioDriver):
    driver_name = "gstreamer"

    def __init__(self, args=None):
        self._glib_context = None
        self._glib_loop = None
        self._glib_thread = None
        self._sink_string = None
        self._sink = None
        self._pipeline = None
        self._filesrc = None

        logger.debug("GStreamerAudioDriver.__init__(args=%r)", args)

        PositionPollingAudioDriver.__init__(self, args)

        # initialize GLib application name if not reasonably initialized yet
        # this will be used as client name in Jack and PulseAudio sinks
        prgname = GLib.get_prgname()
        if not prgname or 'python' in prgname.lower():
            prgname = "sampledrawer"
            GLib.set_prgname(prgname)
        appname = GLib.get_application_name()
        if not appname or appname == prgname or 'python' in appname.lower():
            GLib.set_application_name("Sample Drawer")

        try:
            Gst.init(None)
        except GLib.Error as err:
            raise AudioDriverError("Cannot initialize GStreamer: {}".format(err))

        self._init_glib_loop()
        self._init_sink(args)

        self._rewind()

    def _init_sink(self, args):
        if args and args.audio_device:
            self._sink_string = args.audio_device
        else:
            self._sink_string = "autoaudiosink"

        logger.debug("Using sink: %r", self._sink_string)

        try:
            self._sink = Gst.parse_launch(self._sink_string)
        except GLib.Error as err:
            logger.warning("Cannot parse or load GStreamer sink/pipeline %r: %s",
                           self._sink_string, err)
            logger.info("Provide proper sink or pipeline string (gst-launch format)"
                        " with --audio-device")
            sinks = _get_gst_sinks()
            if sinks:
                logger.info("Available sinks:")
                for name, long_name in _get_gst_sinks():
                    logger.info("    %r: %s", name, long_name)
            raise AudioDriverError("Unsupported audio device")

        # we couldn't care less about that name, but jackaudisink uses it in port names
        self._sink.set_name("p")

        if isinstance(self._sink, Gst.Bin) and not self._sink.get_static_pad("sink"):
            logger.debug("Selected sink is a bin, creating a sink pad")
            pad = self._sink.find_unlinked_pad(Gst.PadDirection.SINK)
            logger.debug("First unlinked sink pad in the pipeline: %r", pad)
            if not pad:
                logger.error("No usable sink pad found in %r", self._sink_string)
                raise AudioDriverError("Unsuitable pipeline passed as audio device")
            self._sink.add_pad(Gst.GhostPad.new("sink", pad))

        # setup and start dummy pipeline to open the device
        # especially for Jack we want the ports allocated and ready from the beginning
        tmp_pipeline = Gst.parse_launch("audiotestsrc wave=silence"
                                        " ! capsfilter name=decend caps=audio/x-raw,channels=2")
        dec_end = tmp_pipeline.get_by_name("decend")
        tmp_pipeline.add(self._sink)
        dec_end.link(self._sink)
        self._set_gst_state(tmp_pipeline, Gst.State.PAUSED)
        self._set_gst_state(tmp_pipeline, Gst.State.READY)
        dec_end.unlink(self._sink)
        tmp_pipeline.remove(self._sink)
        self._set_gst_state(tmp_pipeline, Gst.State.NULL)
        del tmp_pipeline

    def _init_glib_loop(self):
        self._glib_context = GLib.MainContext()
        self._glib_loop = GLib.MainLoop(self._glib_context)
        self._glib_thread = threading.Thread(target=self._main_loop,
                                             name="GStreamer driver main loop",
                                             daemon=True)
        self._glib_thread.start()

    def __del__(self):
        self.close()

    def close(self):
        loop = self._glib_loop  # prevent race condition – can be reset by the thread
        if loop:
            loop.quit()

    def __repr__(self):
        return "<{} ({}) device={!r}>".format(self.__class__.__name__,
                                              self.driver_name,
                                              self._sink_string)

    def _main_loop(self):
        logger.debug("Starting GLib main loop.")
        self._glib_context.acquire()
        try:
            self._glib_loop.run()
            logger.debug("Stopped GLib main loop.")
        except Exception as err:
            logger.debug("Main loop exception:", exc_info=True)
            logger.error("GStreamer driver main loop failed: %s", err)
        finally:
            self._glib_loop = None
            self._glib_context = None

    def _set_gst_state(self, element, state):
        logger.debug("Setting %r to %r", element, state)
        res = element.set_state(state)
        logger.debug("set_state() returned %r", res)
        while res not in (Gst.StateChangeReturn.SUCCESS, Gst.StateChangeReturn.NO_PREROLL):
            if res == Gst.StateChangeReturn.ASYNC:
                res = element.get_state(STATE_CHANGE_TIMEOUT)[0]
                logger.debug("get_state() returned %r", res)
            else:
                raise AudioDriverError("GStreamer state change returned: %s", res.value_name)

    def _bus_call(self, bus, message, loop):
        mtype = message.type
        mstruct = message.get_structure()
        if mstruct:
            logger.debug("Gst message: %r: %r", mtype, mstruct.to_string())
        else:
            logger.debug("Gst message: %r", mtype)
        if mtype == Gst.MessageType.EOS:
            logger.debug("End-of-stream")
            self._rewind()
        elif mtype == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error("%s: %s\n" % (err, debug))
        return True

    def get_position(self):
        if not self._pipeline:
            return 0.0
        ok, pos = self._pipeline.query_position(Gst.Format.TIME)
        if ok:
            return pos / 1000000000.0
        return 0.0

    def set_source(self, filename):
        super().set_source(filename)
        self._rewind()

    def _rewind(self):
        if self._pipeline:
            self._set_gst_state(self._pipeline, Gst.State.READY)
            self._decoderend.unlink(self._sink)
            self._pipeline.remove(self._sink)
            self._set_gst_state(self._pipeline, Gst.State.NULL)
            self._decoderend = None
            self._pipeline = None

        self._pipeline = Gst.parse_launch("filesrc name=source"
                                          " ! decodebin ! audioconvert ! audioresample"
                                          " ! capsfilter name=decend caps=audio/x-raw,channels=2")
        self._filesrc = self._pipeline.get_by_name("source")
        logger.debug("source element: %r", self._filesrc)
        self._decoderend = self._pipeline.get_by_name("decend")
        logger.debug("decoder final element: %r", self._decoderend)
        self._pipeline.add(self._sink)
        self._decoderend.link(self._sink)

        self._bus = self._pipeline.get_bus()
        self._bus.add_signal_watch()
        self._bus.connect("message", self._bus_call, self._glib_loop)

        if self.source:
            self._filesrc.set_property("location", self.source)
            self._set_gst_state(self._pipeline, Gst.State.READY)
            self._set_audio_state(AudioState.STOPPED)
        else:
            self.audio_state = AudioState.UNINITIALIZED

    def play(self):
        logger.debug("playing")
        self._set_gst_state(self._pipeline, Gst.State.PLAYING)
        self._set_audio_state(AudioState.PLAYING)

    def stop(self):
        logger.debug("stopping")
        self._rewind()

    def pause(self):
        logger.debug("pausing")
        self._set_gst_state(self._pipeline, Gst.State.PAUSED)
        self._set_audio_state(AudioState.PAUSED)


GStreamerAudioDriver.register_driver()
