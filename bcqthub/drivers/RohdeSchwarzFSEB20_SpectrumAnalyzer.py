import time
import datetime
from bcqthub.core.BaseDriver import BaseDriver

class RohdeSchwarzFSEB20_SpectrumAnalyzer(BaseDriver):
    """Rohde & Schwarz FSEB20 spectrum analyzer driver."""

    def __init__(self, configs: dict, debug: bool = False, **kwargs):
        """
        :param configs: must include 'instrument_name' and 'address'; may include 'rm_backend'
        :param debug: enable debug-level logging
        """
        address = configs.get("address")
        if not address:
            raise ValueError("configs must include 'address' with VISA resource string")
        super().__init__(configs, instr_resource=None, instr_address=address, debug=debug, **kwargs)
        self.write_check("TRIG:SOUR IMM")

    def idn(self) -> str:
        """Query instrument identity."""
        return self.query_check("*IDN?")

    # IF Bandwidth
    def get_IF_bandwidth(self) -> float:
        """Query IF bandwidth in Hz."""
        return float(self.query_check("SENS:BAND?", fmt=float))

    def set_IF_bandwidth(self, ifbw: float):
        """Set IF bandwidth in Hz."""
        self.write_check(f"SENS:BAND {ifbw}")
        bw = self.get_IF_bandwidth()
        self.log.info(f"IF bandwidth set to {bw} Hz")

    # Center Frequency
    def get_freq_center_Hz(self) -> float:
        return float(self.query_check("FREQ:CENT?", fmt=float))

    def set_freq_center_Hz(self, freq_center_hz: float):
        self.write_check(f"FREQ:CENT {freq_center_hz} HZ")
        cf = self.get_freq_center_Hz()
        self.log.info(f"Center frequency set to {cf} Hz")

    # Frequency Span
    def get_freq_span_Hz(self) -> float:
        return float(self.query_check("FREQ:SPAN?", fmt=float))

    def set_freq_span_Hz(self, freq_span_hz: float):
        self.write_check(f"FREQ:SPAN {freq_span_hz}")
        span = self.get_freq_span_Hz()
        self.log.info(f"Frequency span set to {span} Hz")

    # Averaging
    def get_num_averages(self) -> int:
        return int(self.query_check("AVER:COUN?", fmt=int))

    def set_num_averages(self, num_averages: int):
        self.write_check(f"AVER:COUN {num_averages}")
        navg = self.get_num_averages()
        self.log.info(f"Number of averages set to {navg}")

    # Continuous Sweep
    def toggle_continuous_sweep(self, sweep_mode: bool = None):
        if sweep_mode is None:
            curr = self.query_check("INIT:CONT?", fmt=str).strip()
            new_state = "ON" if curr == "0" else "OFF"
        else:
            new_state = "ON" if sweep_mode else "OFF"
        self.write_check(f"INIT:CONT {new_state}")
        state = self.query_check("INIT:CONT?", fmt=str)
        self.log.info(f"Continuous sweep mode = {state}")

    # Trigger Sweep
    def trigger_sweep(self):
        st = self.query_check("SENSE:SWE:TIME?", fmt=str)
        sweep_time = float(self.strip_specials(st))
        self.log.debug(f"Sweep time = {sweep_time}")
        self.write_check("*TRG")
        self.write_check("INIT:DISP ON")
        start = time.time()
        while True:
            time.sleep(0.5)
            elapsed = time.time() - start
            status = self.query_check("STAT:OPER:COND?", fmt=str).strip()
            self.log.debug(f"Sweep status = {status}")
            if status != "0":
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.log.info(f"[{ts}] Sweep finished in {elapsed:.2f}s")
                break
        self.write_check("INIT:CONT OFF")

    # Marker Methods
    def send_marker_to_max(self):
        self.write_check("CALC:MARK:MAX")
        self.log.info("Marker set to max peak")

    def read_marker_freq_amp(self) -> tuple:
        freq = float(self.query_check("CALC:MARK:X?", fmt=float))
        amp = float(self.query_check("CALC:MARK:Y?", fmt=float))
        self.log.info(f"Marker: freq = {freq} Hz, amp = {amp} dBm")
        return freq, amp

    # Data Retrieval
    def return_data(self, trace_num: int = 1) -> list:
        data_str = self.query_check(f"TRAC:DATA? TRACE{trace_num}", fmt=str)
        return [float(x) for x in data_str.split(",")]


if __name__ == "__main__":
    """Example usage for RohdeSchwarzFSEB20SpectrumAnalyzer."""

    cfg = {
        "instrument_name": "RS_SpectrumAnalyzer",
        "address": "GPIB::20::INSTR",
    }
    RS_SpectrumAnalyzer = RohdeSchwarzFSEB20_SpectrumAnalyzer(cfg)
    
    print(RS_SpectrumAnalyzer.idn())
    
    RS_SpectrumAnalyzer.set_IF_bandwidth(1000)
    print(RS_SpectrumAnalyzer.get_IF_bandwidth())
    
    RS_SpectrumAnalyzer.set_freq_center_Hz(1e9)
    print(RS_SpectrumAnalyzer.get_freq_center_Hz())
    
    RS_SpectrumAnalyzer.set_freq_span_Hz(1e6)
    print(RS_SpectrumAnalyzer.get_freq_span_Hz())


    RS_SpectrumAnalyzer.set_num_averages(10)
    print(RS_SpectrumAnalyzer.get_num_averages())
    
    RS_SpectrumAnalyzer.trigger_sweep()
    RS_SpectrumAnalyzer.send_marker_to_max()
    
    freq, amp = RS_SpectrumAnalyzer.read_marker_freq_amp()
    
    print(f"Marker freq: {freq} Hz, amp: {amp} dBm")
