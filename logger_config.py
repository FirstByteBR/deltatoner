import logging
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from logging.handlers import TimedRotatingFileHandler
import os
import gzip
import glob
import time
from datetime import datetime, timedelta

LOG_DIR = "logs"
LOG_BASENAME = "application.log"
LOG_PATH = os.path.join(LOG_DIR, LOG_BASENAME)
ROTATE_WHEN = 'midnight'
ROTATE_INTERVAL = 1
LOG_RETENTION_DAYS = 3

os.makedirs(LOG_DIR, exist_ok=True)

class GzTimedRotatingFileHandler(TimedRotatingFileHandler):
    """Handler that compresses old log files after rotation and purges very old files."""
    def doRollover(self):
        super().doRollover()
        self._compress_old_logs()
        self._delete_very_old_logs()
  
    def _compress_old_logs(self):
        for log_file in glob.glob(os.path.join(LOG_DIR, f"{LOG_BASENAME}.*")):
            if log_file.endswith('.gz'):
                continue
            # Compress only if not the current log
            if not log_file.endswith(LOG_BASENAME):
                gz_file = log_file + ".gz"
                with open(log_file, "rb") as f_in, gzip.open(gz_file, "wb") as f_out:
                    f_out.writelines(f_in)
                os.remove(log_file)

    def _delete_very_old_logs(self):
        now = time.time()
        for gz_file in glob.glob(os.path.join(LOG_DIR, f"{LOG_BASENAME}.*.gz")):
            # Parse the timestamp from the rotated file name, format: application.log.YYYY-MM-DD
            date_portion = gz_file.split('.')[-2]
            try:
                log_time = time.mktime(time.strptime(date_portion, '%Y-%m-%d'))
            except Exception:
                log_time = os.path.getmtime(gz_file)
            if now - log_time > LOG_RETENTION_DAYS * 86400:
                os.remove(gz_file)

def setup_logger():
    logger = logging.getLogger("AppLogger")
    logger.setLevel(logging.INFO)
    handler = GzTimedRotatingFileHandler(
        LOG_PATH, 
        when=ROTATE_WHEN, 
        interval=ROTATE_INTERVAL, 
        backupCount=LOG_RETENTION_DAYS,
        encoding='utf-8'
    )
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    return logger

logger = setup_logger()