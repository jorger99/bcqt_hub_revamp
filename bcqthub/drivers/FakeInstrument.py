"""
fake_instrument.py

A simple fake instrument driver for testing measurement logic.
Uses BaseDriver.start_instrument factory, Pydantic config, and context manager support.
"""
from controllers.base_driver import BaseDriver, InstrumentConfig


class FakeInstrument(BaseDriver):
    """Fake instrument: logs commands and returns canned responses."""
    def __init__(self, cfg: InstrumentConfig, debug=False, **kwargs):
        super().__init__(cfg, debug=debug, **kwargs)
        self.log = []

    def connect(self):
        """Simulate opening a connection."""
        self.log.append(("connect", self.cfg.dict()))

    def write(self, cmd: str):
        """Record the SCPI command instead of sending it."""
        super().write(cmd)
        self.log.append(("write", cmd))

    def read(self) -> str:
        """Return last SCPI command as a simple response."""
        response = self._last_scpi or ""
        self.log.append(("read", response))
        return response

    def close(self):
        """Simulate closing the connection."""
        super().close()
        self.log.append(("close", None))


# Example usage:
# raw = {"instrument_name": "FakePSU", "address": "FAKE0"}
# fake = FakeInstrument.start_instrument(raw, debug=True)
# with fake as inst:
#     inst.write("*IDN?")
#     resp = inst.read()
# print(fake.log)
