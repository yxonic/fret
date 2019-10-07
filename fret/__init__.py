import logging as _logging

from .util import nonbreak, stateful
from .util import colored as _colored
from .app import workspace, configurable, command, argspec, clean, summarize

_LOGGER = _logging.getLogger()
_LOGGER.setLevel(_logging.INFO)


class _ColoredFormatter(_logging.Formatter):
    """Formatter for colored log."""
    _LOG_COLORS = {
        'WARNING': 'y',
        'INFO': 'g',
        'DEBUG': 'b',
        'CRITICAL': 'y',
        'ERROR': 'r'
    }

    def format(self, record):
        levelname = record.levelname
        if levelname in self._LOG_COLORS:
            record.levelname = _colored(
                record.levelname[0],
                self._LOG_COLORS[record.levelname],
                style='b'
            )
        return _logging.Formatter.format(self, record)


_LOG_FORMATTER = _ColoredFormatter(
    '%(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
_CONSOLE_HANDLER = _logging.StreamHandler()
_CONSOLE_HANDLER.setFormatter(_LOG_FORMATTER)
_LOGGER.addHandler(_CONSOLE_HANDLER)

__version__ = '0.2.8.beta5'
