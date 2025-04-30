import time
import numpy as np
from bcqthub.drivers.KeysightEDU36311A_PowerSupply import KeysightEDU36311A_PowerSupply
from bcqthub.controllers.logging_utils import get_logger


class HEMTController:
    """Controller for HEMT IV sweeps using a Keysight EDU36311A PSU."""

    def __init__(self, configs: dict, debug: bool = False, **kwargs):
        """
        :param configs: must include 'instrument_name' and 'address'; may include 'rm_backend'
        :param debug: enable debug-level logging
        Additional kwargs passed to the PSU driver.
        """
        self.instrument_name = configs.get('instrument_name', 'HEMTController')
        self.log = get_logger(self.instrument_name, debug=debug)


        # Instantiate the underlying PSU driver
        self.psu = KeysightEDU36311A_PowerSupply(configs, debug=debug, **kwargs)

        # Default channels (can override via kwargs)
        self.gate_channel = kwargs.get('gate_channel', 1)
        self.drain_channel = kwargs.get('drain_channel', 2)

    def idn(self) -> str:
        """Proxy *IDN? to the PSU."""
        return self.psu.idn()

    def reset(self):
        """Turn off outputs and zero both channels."""
        self.log.info("Resetting PSU outputs and voltages to zero.")
        self.psu.set_output(False)
        for ch in (self.gate_channel, self.drain_channel):
            self.psu.set_channel_voltage(ch, 0.0)

    def ramp_voltage(self, channel: int, start: float, stop: float,
                     step: float = 0.01, delay: float = 1.0) -> list:
        """
        Ramp a channel from start to stop in increments of step, waiting delay seconds.
        Returns a list of (voltage, current) tuples.
        """
        if stop > start:
            volts = np.arange(start, stop + step, abs(step))
        else:
            volts = np.arange(start, stop - step, -abs(step))

        data = []
        for v in volts:
            self.log.info(f"Setting CH{channel} -> {v:.3f} V")
            self.psu.set_channel_voltage(channel, v)
            try:
                i = self.psu.get_channel_current(channel)
            except Exception as e:
                self.log.error(f"Failed to read current at {v} V: {e}")
                i = float('nan')
            data.append((v, i))
            time.sleep(delay)
        return data

    def monitor_iv(self, channel: int, target: float=None, tol: float=1e-6) -> tuple:
        """
        Read current and voltage once. If a target is given, returns
        (True, (v,i)) when |i-target|<tol, else (False, (v,i)).
        """
        v = self.psu.get_channel_voltage(channel)
        i = self.psu.get_channel_current(channel)
        hit = False
        if target is not None and abs(i - target) < tol:
            hit = True
        return hit, (v, i)

    def turn_on(self, gate_stop: float=1.1, drain_stop: float=0.7,
                step: float=0.01, delay: float=1.0) -> tuple:
        """
        Full HEMT turn-on sequence: reset → ramp gate → ramp drain.
        Returns (gate_trace, drain_trace).
        """
        self.reset()
        gate_trace = self.ramp_voltage(self.gate_channel, 0.0, gate_stop, step, delay)
        drain_trace = self.ramp_voltage(self.drain_channel, 0.0, drain_stop, step, delay)
        self.psu.set_output(True)
        return gate_trace, drain_trace

    def turn_off(self, gate_start: float=1.1, drain_start: float=0.7,
                 step: float=0.01, delay: float=1.0):
        """
        Full HEMT turn-off sequence: ramp drain down → ramp gate down → reset.
        """
        self.ramp_voltage(self.drain_channel, drain_start, 0.0, -abs(step), delay)
        self.ramp_voltage(self.gate_channel, gate_start, 0.0, -abs(step), delay)
        self.reset()


if __name__ == "__main__":
    """Example usage of HEMTController."""

    cfg = {
        'instrument_name': 'HEMT_PSU',
        'address': 'TCPIP0::192.168.0.106::inst0::INSTR'
    }
    HEMT_PSU = HEMTController(cfg, debug=True)
    print("PSU IDN:", HEMT_PSU.idn())
    gate_iv, drain_iv = HEMT_PSU.turn_on()
    print("Gate I–V points:", gate_iv)
    print("Drain I–V points:", drain_iv)
    HEMT_PSU.turn_off()
