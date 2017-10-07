# -*- coding: utf-8 -*-

import logging
from logging.handlers import RotatingFileHandler

# Directory paths
DIR_LOGS        = 'logs/'

# Flask website paths
DIR_WEBSITE     = 'website_files/'
DIR_W_STATIC    = DIR_WEBSITE + 'static'
DIR_W_TEMPLATES = DIR_WEBSITE + 'templates'
DIR_W_UPLOADS   = DIR_WEBSITE + 'ups'

# Nginx prefix
NGINX_PREFIX    = "/umatrix-converter"
# Don't touch that (it's the prefix of static files from web user point of view)
STATIC_PREFIX   = NGINX_PREFIX + '/static'

# Upload size restriction
# In case of client_max_body_size 100k; restriction not set in NGinx config
MAX_CONTENT_LENGTH = 100 * 1024

# Logging
LOGGER_NAME     = 'uMatrixConverter'
LOG_LEVEL       = logging.DEBUG

# Piwik analytics
PIWIK_SITE_ID   = '1'
PIWIK_URL       = ''

################################################################################

def logger(name=LOGGER_NAME, logfilename=None):
    """Return logger of given name, without initialize it.

    Equivalent of logging.getLogger() call.
    """
    return logging.getLogger(name)



_logger = logging.getLogger(LOGGER_NAME)
_logger.setLevel(LOG_LEVEL)

# log file
formatter    = logging.Formatter(
    '%(asctime)s :: %(levelname)s :: %(message)s'
)
file_handler = RotatingFileHandler(
    DIR_LOGS + LOGGER_NAME + '.log',
    'a', 1000000, 1
)
file_handler.setLevel(LOG_LEVEL)
file_handler.setFormatter(formatter)
_logger.addHandler(file_handler)

# terminal log
stream_handler = logging.StreamHandler()
formatter      = logging.Formatter('%(levelname)s: %(message)s')
stream_handler.setFormatter(formatter)
stream_handler.setLevel(LOG_LEVEL)
_logger.addHandler(stream_handler)


def log_level(level):
    """Set terminal log level to given one"""
    handlers = (_ for _ in _logger.handlers
                if _.__class__ is logging.StreamHandler
               )
    for handler in handlers:
        handler.setLevel(level.upper())
