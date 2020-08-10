
import logging
import os
import signal

from PySide2.QtCore import QObject, QTimer, Slot, QSocketNotifier
from PySide2.QtWidgets import QApplication

logger = logging.getLogger("signal_handler")

# Hack from: https://stackoverflow.com/questions/35305920/pyqt-core-application-doesnt-return-to-caller-on-quit
# should really be properly implemented in Qt itself
class SignalHandler(QObject):
    """Handler responsible for handling OS signals (SIGINT, SIGTERM, etc.).
    """
    def __init__(self):
        QObject.__init__(self)
        self._notifier = None
        self._timer = QTimer()
        self._orig_handlers = {}
        self._activated = False
        self._orig_wakeup_fd = None

    def activate(self):
        """Set up signal handlers.

        On Windows this uses a QTimer to periodically hand control over to
        Python so it can handle signals.

        On Unix, it uses a QSocketNotifier with os.set_wakeup_fd to get
        notified.
        """
        self._orig_handlers[signal.SIGINT] = signal.signal(signal.SIGINT, self.interrupt)
        self._orig_handlers[signal.SIGTERM] = signal.signal(signal.SIGTERM, self.interrupt)

        if os.name == 'posix' and hasattr(signal, 'set_wakeup_fd'):
            # pylint: disable=import-error,no-member,useless-suppression
            import fcntl
            read_fd, write_fd = os.pipe()
            for fd in (read_fd, write_fd):
                flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            self._notifier = QSocketNotifier(read_fd, QSocketNotifier.Read, self)
            self._notifier.activated.connect(self.handle_signal_wakeup)
            self._orig_wakeup_fd = signal.set_wakeup_fd(write_fd)
        else:
            self._timer.start(500)
            self._timer.timeout.connect(lambda: None)
        self._activated = True

    @Slot()
    def deactivate(self):
        """Deactivate all signal handlers."""
        if not self._activated:
            return
        if self._notifier is not None:
            self._notifier.setEnabled(False)
            rfd = self._notifier.socket()
            wfd = signal.set_wakeup_fd(self._orig_wakeup_fd)
            os.close(rfd)
            os.close(wfd)
        for sig, handler in self._orig_handlers.items():
            signal.signal(sig, handler)
        self._timer.stop()
        self._activated = False

    @Slot()
    def handle_signal_wakeup(self):
        """Handle a newly arrived signal.

        This gets called via self._notifier when there's a signal.

        Python will get control here, so the signal will get handled.
        """
        logging.debug("Handling signal wakeup!")
        self._notifier.setEnabled(False)
        read_fd = self._notifier.socket()
        try:
            os.read(read_fd, 1)
        except OSError:
            logging.exception("Failed to read wakeup fd.")
        self._notifier.setEnabled(True)

    def interrupt(self, signum, frame):
        """Handler for signals to gracefully shutdown (SIGINT/SIGTERM)."""
        logger.info("Signal %i received", signum)
        logger.debug("stack:", stack_info=frame)
        QApplication.quit()

