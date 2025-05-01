import logging, time
from tqdm.notebook import tqdm

def run_with_progress(
    iterable,
    step_fn,
    desc="Progress",
    delay=0.0,
    metrics=("V","I"),
    ascii=True,
    dynamic_ncols=True,
    mininterval=0.1,
):
    """
    Iterate over `iterable`, calling `step_fn(item)` on each one,
    and draw a tqdm bar with two metric postfixes.

    :param iterable: any iterable (e.g. list of voltages)
    :param step_fn: function(item) -> tuple of two numbers (v, i)
    :param desc: text to show left of bar
    :param delay: seconds to sleep after each step
    :param metrics: names for the two returned values, e.g. ("V","I")
    :return: list of step_fn(item) results
    """
    data = []
    # build a tqdm bar over the iterable
    with tqdm(
        iterable,
        desc=desc,
        ascii=ascii,
        dynamic_ncols=dynamic_ncols,
        mininterval=mininterval,
    ) as pbar:
        for item in pbar:
            result = step_fn(item)
            data.append(result)
            # unpack and show the two metrics
            try:
                a, b = result
                pbar.set_postfix({metrics[0]: f"{a:.3f}", metrics[1]: f"{b:.3e}"})
            except Exception:
                pass
            if delay:
                time.sleep(delay)
    return data

def get_logger(
    name: str,
    debug: bool = False,
    fmt: str = "[%(name)s] %(levelname)s: %(message)s",
) -> logging.Logger:
    """
        Return a logger for `name`, configured with a tqdm-based handler
        so that records go above any progress bars. Subsequent calls
        won’t add duplicate handlers.
    """
    logger = logging.getLogger(name)
    logger.propagate = False  # prevent double-logging to root

    if not logger.handlers:
        handler = TqdmLoggingHandler(fmt)
        logger.addHandler(handler)

    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    return logger

class TqdmLoggingHandler(logging.Handler):
    """
        A logging handler that writes via tqdm.write(), so logs
        appear above any active tqdm bars without clobbering them.
    """
    def __init__(self, fmt):
        super().__init__()
        self.setFormatter(logging.Formatter(fmt))

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
        except Exception:
            self.handleError(record)