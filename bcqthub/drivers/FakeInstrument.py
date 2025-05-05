# bcqthub/drivers/fake_instrument.py
from bcqthub.core.driver import BaseDriver
from bcqthub.logging import get_logger

class FakeInstrument(BaseDriver):
    """
    Stand‐in for any SCPI driver: records history and returns canned responses.
    Note: DOES NOT call BaseDriver.__init__, so no VISA session is opened.
    """
    def __init__(self, cfg, debug=False, responses=None):
        # intentionally do *not* call super().__init__, so no pyvisa.ResourceManager
        self.cfg       = cfg
        self.log       = get_logger(cfg["instrument_name"], debug)
        self.debug     = debug
        self.history   = []
        self.responses = responses or {}
        self.log.info("Initialized FakeInstrument (no VISA session)")

    def write(self, cmd):
        self.history.append(("write", cmd))
        if self.debug:
            self.log.debug(f"[FAKE WRITE] {cmd}")

    def query(self, cmd):
        self.history.append(("query", cmd))
        if self.debug:
            self.log.debug(f"[FAKE QUERY] {cmd}")
        for prefix, resp in sorted(self.responses.items(), key=lambda kv: -len(kv[0])):
            if cmd.startswith(prefix):
                return resp() if callable(resp) else resp
        return ""

    def get_history(self):
        return list(self.history)
