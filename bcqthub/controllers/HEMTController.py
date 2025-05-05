# bcqthub/controllers/hemt_controller.py

import time, logging
import numpy as np

# absolute import of your helper
from bcqthub.controllers.logging_utils import get_logger, run_with_progress
from bcqthub.drivers.KeysightEDU36311A_PowerSupply import KeysightEDU36311A_PowerSupply
import time
import numpy as np
import logging

from bcqthub.controllers.logging_utils import get_logger, run_with_progress
from bcqthub.drivers.KeysightEDU36311A_PowerSupply import KeysightEDU36311A_PowerSupply

class HEMTController:
    """Controlled soft-start and shutdown for HEMT amplifiers"""


    def __init__(self, configs, debug=False, driver=KeysightEDU36311A_PowerSupply, **kwargs):
        
        # pick real or fake
        if driver is None:
            from bcqthub.drivers.keysight_edu36311a import KeysightEDU36311A
            self.psu = KeysightEDU36311A(cfg, debug=debug)
        elif isinstance(driver, BaseDriver):
            self.psu = driver
        elif issubclass(driver, BaseDriver):
            self.psu = driver(cfg, debug=debug)
        else:
            raise ValueError("driver must be None, a BaseDriver subclass, or instance")



        self.debug = debug
        self.log   = get_logger("HEMTController", debug)

        self.log.info("Connecting to Keysight PSU for HEMT control")
        
        # add the ability to insert a different driver besides EDU36311
        driver_cls    = driver_cls or KeysightEDU36311A_PowerSupply
        driver_kwargs = driver_kwargs or {}
        self.psu      = driver_cls(configs, debug=debug, **driver_kwargs)
        
        self.gate_channel  = kwargs.get("gate_channel", 1)
        self.drain_channel = kwargs.get("drain_channel", 2)
        
        
    def reset(self):
        """Reset (clear faults, zero, turn off) just the HEMT channels."""
        self.log.info("Resetting PSU to safe state for HEMT channels")
        self.psu.reset(channels=[self.gate_channel, self.drain_channel])
        

    def dump_debug(self):
        """Convenience to dump the PSU’s debug snapshot."""
        self.log.info("=== HEMTController: Dumping PSU debug info ===")
        self.psu.dump_debug_info()
        self.log.info("===============================================")


    def set_debug(self, dbg: bool):
        """Enable or disable debug logging on both controller + PSU."""
        self.debug = dbg
        lvl = logging.DEBUG if dbg else logging.INFO
        self.log.setLevel(lvl)
        self.psu.log.setLevel(lvl)
        

    def ramp_voltage(self, channel, start, stop, step, delay):
        """
        Smoothly ramp a channel from start→stop in increments of step,
        returning a list of (voltage, current) pairs, with a live tqdm bar.

        During the bar, driver DEBUG logs will appear only if self.debug is True.
        """
        # Build the voltage setpoint list
        direction = 1 if stop > start else -1
        volts = list(
            np.arange(start, stop + direction * step, direction * abs(step))
        )
        total = len(volts)

        # Log the overall plan at INFO
        self.log.info(f"Ramping CH{channel}: {start:.3f}→{stop:.3f} V over {total} steps")

        # Temporarily suppress or allow all PSU logs under the bar
        prev_disabled        = self.psu.log.disabled
        self.psu.log.disabled = not self.debug

        # Define the per-step action
        def step_fn(v):
            self.psu.set_channel_voltage(channel, v)
            return v, self.psu.get_channel_current(channel)

        # Run the tqdm helper
        data = run_with_progress(
            iterable=volts,
            step_fn=step_fn,
            desc=f"CH{channel} {start:.3f}→{stop:.3f}V",
            delay=delay,
            metrics=("V", "I"),
        )

        # Restore the PSU logger’s enabled/disabled state
        self.psu.log.disabled = prev_disabled

        return data


    def turn_on(self, gate_stop, drain_stop, step, delay):
        """
            Full soft-start: reset → enable outputs → ramp gate → ramp drain.
            Returns (gate_trace, drain_trace).
        """
        self.log.info("Beginning HEMT soft-start sequence")
        
        # cancel this method if the channel is on- 
        # we cannot go from on to off without ramping!!!
        if self.psu.get_output() is False:
            raise ZeroDivisionError("We cannot turn the HEMT on if it is currently on!!!!")
        
        # get current start values
        gate_start = self.psu.get_channel_voltage(self.gate_channel)
        drain_start = self.psu.get_channel_voltage(self.drain_channel)
        
        # enable outputs
        self.psu.set_output(True, channel=self.gate_channel)
        self.psu.set_output(True, channel=self.drain_channel)
        self.log.info(
            f"Outputs enabled on CH{self.gate_channel} & CH{self.drain_channel}"
        )
        
        # turn on gate first!
        gate_data  = self.ramp_voltage(
            channel=self.gate_channel,
            start=gate_start,
            stop=gate_stop,
            step=step,
            delay=delay,
        )
        # turn on drain second!!
        drain_data = self.ramp_voltage(
            channel=self.drain_channel,
            start=drain_start,
            stop=drain_stop,
            step=step,
            delay=delay,
        )

        self.log.info("HEMT soft-start complete")
        return gate_data, drain_data


    def turn_off(self, gate_start, drain_start, step, delay):
        """
            Full soft-shutdown: ramp drain down → ramp gate down → reset.
            Returns (gate_trace, drain_trace).
        """
        self.log.info("Beginning HEMT soft-shutdown sequence")

        # cancel this method if the channel is on- 
        # we cannot go from on to off without ramping!!!
        if self.psu.get_output() is True:
            raise ZeroDivisionError("We cannot turn the HEMT OFF if it is currently OFF!!!!")
        
        gate_start = self.psu.get_channel_voltage(self.gate_channel)
        drain_start = self.psu.get_channel_voltage(self.drain_channel)
        
        # turn off drain first!!
        drain_data = self.ramp_voltage(
            channel=self.drain_channel,
            start=drain_start,
            stop=0.0,
            step=-1*abs(step),
            delay=delay,
        )
        # turn off voltage second!!
        gate_data = self.ramp_voltage(
            channel=self.gate_channel,
            start=gate_start,
            stop=0.0,
            step=-1*abs(step),
            delay=delay,
        )

        self.reset()
        self.log.info("HEMT soft-shutdown complete")
        return gate_data, drain_data

#################################################
#################################################
#################################################
    
import matplotlib.pyplot as plt

def plot_iv_pair(gate_data, drain_data):
    """
    Plot Gate and Drain I–V curves side by side.

    :param gate_data: list of (voltage, current) tuples for gate channel
    :param drain_data: list of (voltage, current) tuples for drain channel
    """
    # Unpack data
    gate_v, gate_i = zip(*gate_data)
    drain_v, drain_i = zip(*drain_data)

    # Create subplots
    # fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, figsize=(8, 8))
    fig, ax1 = plt.subplots(nrows=1, ncols=1, figsize=(8, 5))

    # Gate I–V curve
    ax1.plot(gate_v, gate_i, 'b*-', label="Ch1 [Gate]")
    ax1.set_xlabel("Voltage (V)")
    ax1.set_ylabel("Current (A)")

    # Drain I–V curve
    ax1.plot(drain_v, drain_i, 'r*-', label="Ch2 [Drain]")
    ax1.set_xlabel("Voltage (V)")
    ax1.set_ylabel("Current (A)")

    ax1.legend()
    fig.suptitle("HEMT I-V Curves")
    
    fig.tight_layout()
    
    return fig



