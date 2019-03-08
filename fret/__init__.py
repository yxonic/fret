from .util import nonbreak, stateful
from .util import colored as _colored
from .app import workspace, configurable, command, argspec

import logging as _logging

_logger = _logging.getLogger()
_logger.setLevel(_logging.INFO)


class _ColoredFormatter(_logging.Formatter):
    """"""
    _LOG_COLORS = {
        'WARNING': 'y',
        'INFO': 'g',
        'DEBUG': 'b',
        'CRITICAL': 'y',
        'ERROR': 'r'
    }

    def format(self, record):  # pragma: no cover
        """"""
        levelname = record.levelname
        if levelname in self._LOG_COLORS:
            record.levelname = _colored(
                record.levelname[0],
                self._LOG_COLORS[record.levelname],
                style='b'
            )
        return _logging.Formatter.format(self, record)


_log_formatter = _ColoredFormatter(
    '%(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
_console_handler = _logging.StreamHandler()
_console_handler.setFormatter(_log_formatter)
_logger.addHandler(_console_handler)
