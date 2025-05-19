import time
import math

from bcqthubrevamp.core.BaseDriver import BaseDriver
from bcqthubrevamp.controllers.logging_utils import get_logger

# Factory limits (from manufacturer data sheet)
_FACTORY_MIN_VOLTAGE = {
    1: 0.0,    # CH1 P6V
    2: 0.0,    # CH2 P30V
    3: 0.0,    # CH3 N30V
}

_FACTORY_MAX_VOLTAGE = {
    1: 6.18,   # CH1 P6V
    2: 30.9,   # CH2 P30V
    3: 30.9,   # CH3 N30V
}

_FACTORY_MIN_CURRENT = {
    1: 0.002,  # CH1 P6V
    2: 0.001,  # CH2 P30V
    3: 0.001,  # CH3 N30V
}

_FACTORY_MAX_CURRENT = {
    1: 5.15,   # CH1 P6V
    2: 1.03,   # CH2 P30V
    3: 1.03,   # CH3 N30V
}

# values chosen for HEMTs!! 04/30/2025
_USER_MIN_CH_VOLTAGE = {
    1: 0.0,
    2: 0.0,
    3: 0.0,
}
_USER_MAX_CH_VOLTAGE = {
    1: 6.18,
    2: 30.9,
    3: 30.9,
}
_USER_MIN_CH_CURRENT = {
    1: 0.000,
    2: 0.000,
    3: 0.000,
}
_USER_MAX_CH_CURRENT = {
    1: 0.005,  # gate current - we want no leakage!
    2: 0.05,   # drain current - limit the amount of flow!
    3: 1.03,
}

_SUPPLY_RESOLVED_DIGITS = 4

class Keysight_EDU36311A_PSU(BaseDriver):

    debug_getters = [
        "get_channel_voltage",   
        "get_channel_current",
        "get_output",           
    ]
    default_channels = [1,2]
    
    def __init__(self, configs, debug=False, **kwargs):
        """
        :param configs: dict with keys
            - 'instrument_name': str
            - 'address': VISA resource string (e.g. 'GPIB::22::INSTR')
            optional 'rm_backend'
        :param debug: enable debug-level logging
        """
        self.debug = debug
        if not configs.get("address"):
            raise ValueError("configs must include non-empty 'address'")
        
        super().__init__(configs, debug=debug, **kwargs)
        self.use_factory_limits = bool(configs.get("use_factory_limits", False))
        # override BaseDriver's logger with a named one
        self.log = get_logger(self.instrument_name, self.debug)
        
        # Point these four attributes at either the factory or user dicts:
        if self.use_factory_limits:
            self._min_voltage = _FACTORY_MIN_VOLTAGE
            self._max_voltage = _FACTORY_MAX_VOLTAGE
            self._min_current = _FACTORY_MIN_CURRENT
            self._max_current = _FACTORY_MAX_CURRENT
        else:
            self._min_voltage = _USER_MIN_CH_VOLTAGE
            self._max_voltage = _USER_MAX_CH_VOLTAGE
            self._min_current = _USER_MIN_CH_CURRENT
            self._max_current = _USER_MAX_CH_CURRENT
        
        # Initialize stored setpoints:
        #   voltages = min (safe default), currents = max (so voltage ramp isn't stuck)
        for ch in (1,2,3):
            setattr(self, f"_CH{ch}_voltage", self._min_voltage[ch])
            setattr(self, f"_CH{ch}_current", self._max_current[ch])
    
    def _get_limits(self, channel):
        """
        Return (vmin, vmax, imin, imax) for the given channel,
        based on self.use_factory_limits, and log which set was used.
        """
        if self.use_factory_limits:
            src = "FACTORY"
            vmin = _FACTORY_MIN_VOLTAGE[channel]
            vmax = _FACTORY_MAX_VOLTAGE[channel]
            imin = _FACTORY_MIN_CURRENT[channel]
            imax = _FACTORY_MAX_CURRENT[channel]
        else:
            src = "USER"
            vmin = _USER_MIN_CH_VOLTAGE[channel]
            vmax = _USER_MAX_CH_VOLTAGE[channel]
            imin = _USER_MIN_CH_CURRENT[channel]
            imax = _USER_MAX_CH_CURRENT[channel]

        # Log at DEBUG so you can see it when debug=True
        self.log.debug(
            f"CH{channel} limits from {src}: "
            f"V[{vmin}–{vmax}], I[{imin}–{imax}]"
        )
        return vmin, vmax, imin, imax


    def idn(self):
        """Query instrument identity."""
        return self.query_check("*IDN?")
    
    def set_output(self, state, channel=None):
        """
        Turn output ON (True) or OFF (False).
        Must first select the channel with INST:NSEL, then use OUTP.
        If channel is None, applies to all three channels.
        """
        chans = [channel] if channel else [1, 2, 3]
        for ch in chans:
            # 1) select channel
            self.write_check(f"INST:NSEL {ch}")
            # 2) turn output on/off
            self.write_check(f"OUTP {int(state)}")
            self.log.info(f"CH{ch} output {'ON' if state else 'OFF'}")

    def get_output(self, channel=None):
        """
        Query output state(s). Must select channel first, then ask OUTP?.
        Returns single bool if channel given, else a dict {ch:state}.
        """
        chans = [channel] if channel else [1, 2, 3]
        result = {}
        for ch in chans:
            self.write_check(f"INST:NSEL {ch}")
            val = self.query_check("OUTP?", fmt=int)
            result[ch] = bool(val)
        return result[channel] if channel else result

    def _validate_channel(self, channel): 
        """Convert and validate channel (1,2,3)."""
        if isinstance(channel, str) and channel.lower().startswith("ch"):
            num = int(channel[2])
        elif isinstance(channel, (int, float)) and int(channel) in (1, 2, 3):
            num = int(channel)
        else:
            raise ValueError("Channel must be 1,2,3 or 'ch1','ch2','ch3'")
        return num

    def get_channel_voltage(self, channel):
        """
        Query the actual output voltage on the given channel
        using MEAS:VOLT? (@n).
        """
        ch = self._validate_channel(channel)
        # MEASure:VOLTage? returns the real voltage
        return self.query_check(f"MEAS:VOLT? (@{ch})", fmt=float)
    
    def set_channel_voltage(self, channel, voltage):
        ch = self._validate_channel(channel)

        # 1) pull the correct min/max
        vmin, vmax, imin, imax = self._get_limits(ch)

        # 2) validate voltage
        if not (vmin <= voltage <= vmax):
            raise ValueError(f"Voltage {voltage} out of range for CH{ch}: {vmin}–{vmax}")
        voltage = round(voltage, _SUPPLY_RESOLVED_DIGITS)

        # 3) clamp the stored current limit
        cur_limit = getattr(self, f"_CH{ch}_current", imin)
        cur_limit = min(max(cur_limit, imin), imax)

        # 4) issue the SCPI
        self.write_check(f"APPL CH{ch},{voltage},{cur_limit}")

        # 5) remember & read back…
        setattr(self, f"_CH{ch}_voltage", voltage)
        setattr(self, f"_CH{ch}_current", cur_limit)
        meas_v = self.get_channel_voltage(ch)
        meas_i = self.get_channel_current(ch)
        self.log.debug(f"CH{ch} set → V={meas_v:.3f} V, I={meas_i:.3e} A")


    def get_channel_current(self, channel):
        """
        Query the actual output current on the given channel
        using MEAS:CURR? (@n).
        """
        ch = self._validate_channel(channel)
        # MEASure:CURRent? returns the real current
        return self.query_check(f"MEAS:CURR? (@{ch})", fmt=float)
    
    def set_channel_current(self, channel, current):
        ch = self._validate_channel(channel)
        vmin, vmax, imin, imax = self._get_limits(ch)

        if not (imin <= current <= imax):
            raise ValueError(f"Current {current} out of range for CH{ch}: {imin}–{imax}")
        current = round(current, _SUPPLY_RESOLVED_DIGITS)

        volt_limit = getattr(self, f"_CH{ch}_voltage", vmin)
        volt_limit = min(max(volt_limit, vmin), vmax)

        self.write_check(f"APPL CH{ch},{volt_limit},{current}")
        setattr(self, f"_CH{ch}_current", current)

        meas_v = self.get_channel_voltage(ch)
        meas_i = self.get_channel_current(ch)
        self.log.debug(f"CH{ch} set → V={meas_v:.3f} V, I={meas_i:.3e} A")

    def reset(self, channels=None):
        """
        Instrument‐level reset:
          1) Turn outputs OFF
          2) Zero voltages
          3) Clear any OVP/OCP latches

        :param channels: list of channel numbers to reset; defaults to [1,2,3]
        """
        if channels is None:
            channels = [1, 2, 3]

        # 1) disable outputs
        for ch in channels:
            self.write_check(f"OUTP OFF,(@{ch})")
        
        # 2) zero voltages  # TODO: ramp voltage to be safe
        for ch in channels:
            # select & zero
            self.write_check(f"INST:NSEL {ch}")
            self.write_check(f"VOLT 0.0")
            # update stored state
            setattr(self, f"_CH{ch}_voltage", 0.0)

        # 3) clear any protection latches
        for ch in channels:
            # select then clear
            self.write_check(f"INST:NSEL {ch}")
            self.write_check(f"OUTP:PROT:CLE (@{ch})")
            self.log.info(f"Cleared OVP/OCP protection on CH{ch}")


    def clear_protection(self, channel):
        """
        Clear any OCP/OVP latch for the given channel:
          OUTP:PROT:CLE (@<channel>)
        """
        ch = self._validate_channel(channel)
        # send the clear‐protection SCPI
        self.write_check(f"OUTP:PROT:CLE (@{ch})")
        self.log.info(f"Protection cleared on CH{ch}")

    def beep(self):
        """Send a beep command."""
        return self.write_check("SYSTem:BEEPer:IMMediate")

    def return_instrument_parameters(self, print_output=False):
        """Run all get_* methods and return their results as a dict."""
        return super().return_instrument_parameters(print_output)


if __name__ == "__main__":
    """Example usage for KeysightEDU36311APowerSupply."""

    cfg = {
        "instrument_name": "PSU_E36311A",
        "address": "",
    }

    psu = Keysight_EDU36311A_PSU(cfg)
    print(psu.idn())
    psu.set_output(False)           # turn _off_ all channels
    psu.set_channel_voltage(1, 5.0)
    print(psu.get_channel_voltage(1))
    psu.set_channel_current(2, 0.5)
    print(psu.get_channel_current(2))
    psu.beep()
    print(psu.return_instrument_parameters(print_output=True))
