
import importlib
import logging

from .driver import AudioDriver, AudioDriverError, AudioState  # noqa: F401

DRIVER_MODULES = ["qt"]

logger = logging.getLogger("audiodrivers")


def load_drivers():
    for name in DRIVER_MODULES:
        try:
            logger.debug("loading: %s.%s", __name__, name)
            importlib.import_module("." + name, package=__name__)
        except Exception as err:
            logger.debug("Could not load %r audio driver: %s", name, err, exc_info=True)


def get_audio_driver(args=None):
    logger.debug("get_audio_driver(%r)", args)

    load_drivers()

    if args and args.audio_driver:
        driver = AudioDriver.registered_drivers[args.audio_driver]()
    else:
        for name, cls in AudioDriver.registered_drivers.items():
            try:
                driver = cls(args)
                break
            except AudioDriverError as err:
                logger.debug("Cannot initialize audio driver %r: %s", err)
        else:
            logger.warning("Could not find any audio driver!")
            return None
    logger.debug("Selected driver: %r", driver)
    return driver
