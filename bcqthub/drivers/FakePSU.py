# bcqthub/drivers/FakePSU.py
""" 
fake_instrument.py

A simple fake instrument driver for testing measurement logic.
Uses BaseDriver.start_instrument factory, Pydantic config, and context manager support.
"""
from bcqthub.drivers.rohde_schwarz_fseb20_spectrumanalyzer import RnS_FSEB20_SA
from bcqthub.core.BaseDriver import BaseDriver
from bcqthub.core.BaseInstrumentConfig import InstrumentConfig


class FakePSU(BaseDriver):
    
    """ Fake instrument: logs commands and returns fake responses in the log. """
    def __init__(self, cfg: InstrumentConfig, debug=False, **kwargs):
        # set this up before running super.__init__()
        self._log_buffer = []
          
        # super().__init__ calls connect(), but we don't make a VISA call in our connect()
        super().__init__(cfg, debug=debug, **kwargs)
        
        self.fake_log = self._log_buffer
        self.channel_outputs = [False, False, False]  # never do this for a real instrument...! always query
        self.channel_currents = [0.0, 0.0, 0.0]
        self.channel_voltages = [0.0, 0.0, 0.0]
        self.gate_resistance = 70  
        self.drain_resistance = 40  
        
    ##################################
    ##########  standards  ###########
    ##################################
        
    def connect(self):
        """ Simulate opening a connection. """
        self._log_buffer.append(("connect", self.configs))
        
    def write(self, cmd: str):
        """ Record the SCPI command instead of sending it. """
        self._log_buffer.append(("write", cmd))
        self._last_scpi = cmd

    def reset(self, channels: str):
        """ set output to zero and nothing else :)  """
        self._log_buffer.append(("reset", f"ch={channels}"))
        self._last_scpi = "reset"
        for ch in channels:
            self.set_output(False, ch)
        
    def read(self) -> str:
        """ Return last SCPI command as a simple response. """
        response = "last cmd was " + getattr(self, "_last_scpi", "")
        self._log_buffer.append(("read", response))
        return response

    def close(self):
        """ Simulate closing the connection. """
        self._log_buffer.append(("close", None))

    def idn(self) -> str:
        """ Return a fake identification string instead of querying VISA. """
        self._log_buffer.append(("idn", None))
        return "FAKE_INSTR,MODEL,1234,1.0"
    
    
    ##################################
    ############  output  ############
    ##################################
    
    def get_output(self) -> bool:
        """ Return fake channel outputs """
        self._log_buffer.append(("get_output", None))
        return self.channel_outputs
        # return (True, True, True)
        
    def set_output(self, output, channel) -> bool:
        """ Flip a given output"""
        self._log_buffer.append(("set_output", None))
        self.channel_outputs[channel] = output
        
        
    ##################################
    ###########  current  ############
    ##################################
    
    def get_channel_current(self, channel) -> float:
        """ Return the fake current value """
        self._log_buffer.append(("get_channel_current", None))
        return self.channel_currents[channel]
    
    def set_channel_current(self, current, channel) -> float:
        """ Set the fake current value """
        self._log_buffer.append(("set_channel_current", None))
        self.channel_currents[channel] = current
    
    
    ##################################
    ###########  voltage  ############
    ##################################
    
    def get_channel_voltage(self, channel) -> float:
        """ Return a fake voltage value """
        self._log_buffer.append(("get_channel_voltage", None))
        return self.channel_voltages[channel] 
    
    def set_channel_voltage(self, voltage, channel) -> float:
        """ Set the fake voltage output, increase current by V=iR, R=50Ω """
        self._log_buffer.append(("set_channel_voltage", None))
        resistance = self.gate_resistance if channel == 1 else self.drain_resistance
        
        self.channel_voltages[channel] = voltage
        self.channel_currents[channel] = voltage/resistance
        