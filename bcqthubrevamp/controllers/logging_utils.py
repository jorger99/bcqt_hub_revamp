"""
logging_utils.py

Minimal logging utilities:
- run_with_progress: show tqdm bar with two metrics
- TqdmHandler: print logs above tqdm bars
- RotatingTxtHandler: rotate .txt logs by size, keep all files
- FolderWarnHandler: warn once if logs folder grows too big
- get_logger: set up handlers with defaults
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tqdm.notebook import tqdm
import time


def run_with_progress(iterable, step_fn, desc="Progress", delay=0.0,
                      metrics=("V", "I"), ascii=True,
                      dynamic_ncols=True, mininterval=0.1,
                      **fn_kwargs):
    
    """
    Loop items with tqdm and label two returned values.

    Use `metrics` to name the two values from step_fn:
      - e.g. metrics=("V","I") for voltage/current
      - e.g. metrics=("Iter","Meas") for iteration vs measurement

    Example:
        data = run_with_progress(voltages, measure_fn, desc="Sweep",
                                  metrics=("V","I"))
        data = run_with_progress(range(5), lambda i: (i, measure(i)),
                                  desc="Test", metrics=("Iter","Meas"))
                                  
    """
    
    
    data = []
    with tqdm(iterable, desc=desc, ascii=ascii,
              dynamic_ncols=dynamic_ncols,
              mininterval=mininterval) as progress_bar:
        for item in progress_bar:
            result = step_fn(item, **fn_kwargs)
            data.append(result)
            try:
                v, i = result
                progress_bar.set_postfix({metrics[0]: f"{v:.3f}", metrics[1]: f"{i:.3e}"})
            except Exception:
                pass
            if delay:
                time.sleep(delay)
    return data


class TqdmHandler(logging.Handler):
    """ Write log messages above active tqdm bars. """
    
    def __init__(self, fmt):
        super().__init__()
        self.setFormatter(logging.Formatter(fmt))
    def emit(self, record):
        tqdm.write(self.format(record))


class RotatingTxtHandler(RotatingFileHandler):
    """ Rotate logs by size into .txt files without deleting old ones. """
    
    def __init__(self, fn, maxBytes, encoding='utf-8', delay=False):
        super().__init__(fn, 'a', maxBytes, backupCount=0,
                         encoding=encoding, delay=delay)
    def getFilesToDelete(self):
        return []


class FolderWarnHandler(logging. Handler):
    """ Check and warn if total size of .txt logs in a folder exceeds threshold. Never deletes. """
    
    def __init__(self, folder, threshold):
        super().__init__()
        self.folder = Path(folder)
        self.threshold = threshold
        self.warned = False
    def emit(self, record):
        total = sum(f.stat().st_size for f in self.folder.glob('*.txt') if f.is_file())
        if total >= self.threshold and not self.warned:
            logging.getLogger(record.name).warning(
                f"Log folder {self.folder} size {total/1024**2:.1f}MB > "
                f"{self.threshold/1024**2:.1f}MB"
            )
            self.warned = True


def get_logger(name, debug=False, suppress_all_logs=False,
               fmt="[%(asctime)s] [%(name)s] %(levelname)s: %(message)s", 
               log_file=None, max_bytes=10*1024*1024, delay=False, 
               encoding='utf-8', log_folder='logs', folder_threshold=100*1024*1024):
    """ Implements RotatingTxt and TQDM methods to return a fully functional logger. """
    
    logger = logging.getLogger(name)
    logger.propagate = False
    
    if not logger.handlers:
        logger.setLevel(logging.DEBUG if debug else logging.INFO)
        Path(log_folder).mkdir(parents=True, exist_ok=True)
        logger.addHandler(TqdmHandler(fmt))
        path = log_file or f"{name}.txt"
        fh = RotatingTxtHandler(path, max_bytes, encoding, delay)
        fh.setFormatter(logging.Formatter(fmt))
        logger.addHandler(fh)
        logger.addHandler(FolderWarnHandler(log_folder, folder_threshold))
    
    # patch to disable logs
    if suppress_all_logs is True:
        logging.disable(logging.CRITICAL)    
    
    return logger
