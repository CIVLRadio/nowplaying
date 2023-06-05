# civl_util.py 0.0.1 - common utility functions, classes, etc. for CIVL Python scripts
# written by Emma Hones and Anastasia Mayer

# Copyright (c) 2022-2023 Emma Hones and Anastasia Mayer
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import logging, datetime, sys, os

### LOGGING ###
# adapted from https://alexandra-zaharia.github.io/posts/make-your-own-custom-color-formatter-with-python-logging/

class CustomFormatter(logging.Formatter):
    """Logging coloured formatter, adapted from https://stackoverflow.com/a/56944256/3638629"""

    grey = '\x1b[38;20m'
    green = '\x1b[38;5;41m'
    yellow = '\x1b[38;5;226m'
    red = '\x1b[38;5;196m'
    bold_red = '\x1b[31;1m'
    reset = '\x1b[0m'

    def __init__(self, fmt):
        super().__init__()
        self.fmt = fmt
        self.FORMATS = {
            logging.DEBUG: self.grey + self.fmt + self.reset,
            logging.INFO: self.green + self.fmt + self.reset,
            logging.WARNING: self.yellow + self.fmt + self.reset,
            logging.ERROR: self.red + self.fmt + self.reset,
            logging.CRITICAL: self.bold_red + self.fmt + self.reset
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def logger_initialise():
    # Create custom logger logging all five levels
    log = logging.getLogger(__name__)
    # Define format for logs
    fmt = '[%(filename)s] %(levelname)8s: %(message)s'
    # Create stdout handler for logging to the console (logs all five levels)
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(CustomFormatter(fmt))
    # Add handler to the logger
    log.addHandler(stdout_handler)
    log.setLevel(logging.INFO)
    return log
