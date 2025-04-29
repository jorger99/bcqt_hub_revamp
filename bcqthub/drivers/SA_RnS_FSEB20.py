import logging
from bcqthub.core.BaseDriver import BaseDriver

# Factory limits
_FACTORY_MIN_CH1_VOLTAGE = 0.0
_FACTORY_MAX_CH1_VOLTAGE = 6.18
_FACTORY_MIN_CH2_VOLTAGE = 0.0
_FACTORY_MAX_CH2_VOLTAGE = 30.9
_FACTORY_MIN_CH3_VOLTAGE = 0.0
_FACTORY_MAX_CH3_VOLTAGE = 30.9

_FACTORY_MIN_CH1_CURRENT = 0.002
_FACTORY_MAX_CH1_CURRENT = 5.15
_FACTORY_MIN_CH2_CURRENT = 0.001
_FACTORY_MAX_CH2_CURRENT = 1.03
_FACTORY_MIN_CH3_CURRENT = 0.001
_FACTORY_MAX_CH3_CURRENT = 1.03

# User limits default to factory
_USER_MIN_CH1_VOLTAGE = _FACTORY_MIN_CH1_VOLTAGE
_USER_MAX_CH1_VOLTAGE = _FACTORY_MAX_CH1_VOLTAGE
_USER_MIN_CH2_VOLTAGE = _FACTORY_MIN_CH2_VOLTAGE
_USER_MAX_CH2_VOLTAGE = _FACTORY_MAX_CH2_VOLTAGE
_USER_MIN_CH3_VOLTAGE = _FACTORY_MIN_CH3_VOLTAGE
_USER_MAX_CH3_VOLTAGE = _FACTORY_MAX_CH3_VOLTAGE

_USER_MIN_CH1_CURRENT = _FACTORY_MIN_CH1_CURRENT
_USER_MAX_CH1_CURRENT = _FACTORY_MAX_CH1_CURRENT
_USER_MIN_CH2_CURRENT = _FACTORY_MIN_CH2_CURRENT
_USER_MAX_CH2_CURRENT = _FACTORY_MAX_CH2_CURRENT
_USER_MIN_CH3_CURRENT = _FACTORY_MIN_CH3_CURRENT
_USER_MAX_CH3_CURRENT = _FACTORY_MAX_CH3_CURRENT

_SUPPLY_RESOLVED_DIGITS = 4


class PSU_Keysight_E36311A(BaseDriver):
    """Keysight EDU36311A triple-output DC power supply driver."""

    def __init__(self, configs: dict, debug: bool = False, **kwargs):
        """
        :param configs: must include 'instrument_name' and 'address'; may include 'rm_backend'
        :param debug: enable debug-level logging
        """
        address = configs.get('address')
        if not address:
            raise ValueError("configs must include 'address' key with VISA resource string")
        super().__init__(configs, instr_resource=None, instr_address=address, debug=debug, **kwargs)

    def idn(self) -> str:
        """Query instrument identity."""
        return self.query_check('*IDN?')

    def _validate_channel(self, channel):
        """Convert channel to integer 1,2,3 and validate."""
        if isinstance(channel, str) and channel.lower().startswith('ch'):
            ch = int(channel[2])
        elif isinstance(channel, (int, float)) and int(channel) in (1,2,3):
            ch = int(channel)
        else:
            raise ValueError("Channel must be 1,2,3 or 'ch1','ch2','ch3'")
        return ch

    def get_channel_voltage(self, channel) -> float:
        """Query the voltage of a given channel."""
        ch = self._validate_channel(channel)
        resp = self.query_check(f'APPLy? ch{ch}')
        volt_str, _ = resp.split(',')
        return float(volt_str.strip().strip('"'))

    def set_channel_voltage(self, channel, voltage: float):
        """Set voltage for a given channel, respecting limits."""
        ch = self._validate_channel(channel)
        if ch == 1 and not (_USER_MIN_CH1_VOLTAGE <= voltage <= _USER_MAX_CH1_VOLTAGE):
            raise ValueError(f"Voltage out of range for CH{ch}")
        if ch == 2 and not (_USER_MIN_CH2_VOLTAGE <= voltage <= _USER_MAX_CH2_VOLTAGE):
            raise ValueError(f"Voltage out of range for CH{ch}")
        if ch == 3 and not (_USER_MIN_CH3_VOLTAGE <= voltage <= _USER_MAX_CH3_VOLTAGE):
            raise ValueError(f"Voltage out of range for CH{ch}")
        voltage = round(voltage, _SUPPLY_RESOLVED_DIGITS)
        current = self.get_channel_current(ch)
        self.write_check(f'APPLy ch{ch},{voltage},{current}')
        new_v = self.get_channel_voltage(ch)
        self.logger.info(f"CH{ch} voltage set to {new_v} V")

    def get_channel_current(self, channel) -> float:
        """Query the current of a given channel."""
        ch = self._validate_channel(channel)
        resp = self.query_check(f'APPLy? ch{ch}')
        _, cur_str = resp.split(',')
        return float(cur_str.strip().strip('"'))

    def set_channel_current(self, channel, current: float):
        """Set current for a given channel, respecting limits."""
        ch = self._validate_channel(channel)
        if ch == 1 and not (_USER_MIN_CH1_CURRENT <= current <= _USER_MAX_CH1_CURRENT):
            raise ValueError(f"Current out of range for CH{ch}")
        if ch == 2 and not (_USER_MIN_CH2_CURRENT <= current <= _USER_MAX_CH2_CURRENT):
            raise ValueError(f"Current out of range for CH{ch}")
        if ch == 3 and not (_USER_MIN_CH3_CURRENT <= current <= _USER_MAX_CH3_CURRENT):
            raise ValueError(f"Current out of range for CH{ch}")
        current = round(current, _SUPPLY_RESOLVED_DIGITS)
        voltage = self.get_channel_voltage(ch)
        self.write_check(f'APPLy ch{ch},{voltage},{current}')
        new_c = self.get_channel_current(ch)
        self.logger.info(f"CH{ch} current set to {new_c} A")

    def beep(self):
        """Send a beep command."""
        return self.write_check('SYST:BEEP')

    def return_instrument_parameters(self, print_output=False) -> dict:
        """Run all get_* methods and return values."""
        return super().return_instrument_parameters(print_output)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG,
                        format='[%(name)s] %(levelname)s: %(message)s')
    cfg = {'instrument_name': 'PSU_E36311A', 'address': 'GPIB::22::INSTR'}
    with PSU_Keysight_E36311A(cfg, debug=True) as psu:
        print(psu.idn())
        psu.set_channel_voltage(1, 5.0)
        print(psu.get_channel_voltage(1))
        psu.set_channel_current(2, 0.5)
        print(psu.get_channel_current(2))
