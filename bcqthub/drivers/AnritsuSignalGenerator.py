import logging
from bcqthub.core.BaseDriver import BaseDriver

class AnritsuMG369XX_SignalGenerator(BaseDriver):
    """Anritsu signal generator driver using SCPI."""

    def __init__(self, configs: dict, debug: bool = False, **kwargs):
        """
        :param configs: must include 'instrument_name' and 'address';
                        may include 'suppress_warnings' and 'rm_backend'
        :param debug: enable debug-level logging
        """
        address = configs.get("address")
        if not address:
            raise ValueError("configs must include 'address' with VISA resource string")
        super().__init__(configs, instr_resource=None, instr_address=address, debug=debug, **kwargs)
        self.suppress_warnings = configs.get("suppress_warnings", False)

    def idn(self) -> str:
        """Query instrument identity."""
        return self.query_check("*IDN?")

    def return_instrument_parameters(self, print_output: bool = False, old_output: bool = False):
        """
        Return dict of all get_* parameters; or in old‐style tuple if requested.
        """
        params = super().return_instrument_parameters(print_output=print_output)
        if old_output and print_output:
            power = self.get_power()
            freq = self.get_freq()
            output = self.get_output()
            self.logger.info("Instrument parameters (old style):")
            self.logger.info(f"  Output = {output}")
            self.logger.info(f"  Frequency = {freq/1e9:.2f} GHz")
            self.logger.info(f"  Power = {power} dBm")
            return power, freq, output
        return params

    # --- Output Control ---
    def get_output(self, print_output: bool = False) -> bool:
        """Query the output state."""
        status = bool(self.query_check("OUTP:STAT?", fmt=int))
        if print_output:
            self.logger.info(f"Output status: {status}")
        return status

    def set_output(self, setting: bool):
        """Set the output state."""
        current = self.get_output()
        if current == setting:
            self.logger.warning(f"Output already {'ON' if setting else 'OFF'}")
        else:
            self.logger.info(f"Setting output to {'ON' if setting else 'OFF'}")
            self.write_check(f"OUTP:STAT {int(setting)}")

    # --- Power Methods ---
    def get_power(self) -> float:
        """Query the current power level in dBm."""
        return float(self.query_check("SOUR:POW:LEV:IMM:AMPL?", fmt=float))

    def set_power(self, power_dBm: float, override_safety: bool = False):
        """Set the power level, enforcing safety unless overridden."""
        if not override_safety and power_dBm > 0:
            self.logger.error("Power > 0 dBm without override_safety; aborting")
            raise ValueError("Use override_safety=True to override safety limit")
        if override_safety and power_dBm >= 0:
            self.logger.warning("Override safety: setting power ≥ 0 dBm")
        self.write_check(f"SOUR:POW:LEV:IMM:AMPL {power_dBm} dBm")
        new_power = self.get_power()
        self.logger.info(f"Power set to {new_power} dBm")

    # --- Frequency Methods ---
    def get_freq(self) -> float:
        """Query the current frequency in Hz."""
        return float(self.query_check("SOUR:FREQ:CW?", fmt=float))

    def set_freq(self, frequency: float):
        """Set the frequency in Hz, with optional unit warnings."""
        if not self.suppress_warnings:
            if frequency <= 1e0:
                self.logger.error(f"Received {frequency}: likely GHz instead of Hz")
                raise ValueError("Check frequency units; expected Hz")
            elif frequency <= 1e3:
                self.logger.error(f"Received {frequency}: likely MHz instead of Hz")
                raise ValueError("Check frequency units; expected Hz")
            elif frequency <= 1e6:
                self.logger.warning(f"Received {frequency}: likely kHz instead of Hz; proceeding")
        self.write_check(f"SOUR:FREQ:CW {frequency} HZ")
        new_freq = self.get_freq()
        self.logger.info(f"Frequency set to {new_freq} Hz")


if __name__ == "__main__":
    """Example usage for SG_Anritsu driver."""
    import logging
    logging.basicConfig(level=logging.DEBUG, format="[%(name)s] %(levelname)s: %(message)s")

    cfg = {"instrument_name": "TEST_ANRITSU", 
           "address": "GPIB::9::INSTR", 
           "suppress_warnings": False}
    
    SG_Anritsu = AnritsuMG369XX_SignalGenerator(cfg)
    print(SG_Anritsu.idn())
    
    SG_Anritsu.set_output(True)
    print(SG_Anritsu.get_output())
    
    SG_Anritsu.set_freq(1e9)
    print(SG_Anritsu.get_freq())
    
    SG_Anritsu.set_power(-10)
    print(SG_Anritsu.get_power())
