# bcqthub/controllers/hemt_controller.py

from bcqthubrevamp.controllers.logging_utils import get_logger, run_with_progress
from bcqthubrevamp.drivers.keysight_edu36311a_power_supply import Keysight_EDU36311A_PSU
import numpy as np
import logging
import matplotlib.pyplot as plt
import time
from datetime import datetime

class HEMTController:
    """Controlled soft-start and shutdown for HEMT amplifiers"""

    def __init__(self, configs, suppress_logs=False, driver=Keysight_EDU36311A_PSU, **kwargs):
        
        self.fake_mode = configs.get("fake_instrument_mode", False)
        self.debug = suppress_logs
        self.log   = get_logger("HEMTController", suppress_all_logs=suppress_logs)
        self.log.info("Connecting to Keysight PSU for HEMT control")
        
        
        # if the user asked for dry_run, force the fake as driver
        if self.fake_mode is True:
            from bcqthubrevamp.drivers.FakePSU import FakePSU
            driver_cls = FakePSU
        else:
            driver_cls = driver or Keysight_EDU36311A_PSU
        
        kwargs             = kwargs or {}
        self.psu           = driver_cls(configs, debug=suppress_logs, **kwargs)
        self.gate_channel = configs.get("gate_channel",1)
        self.drain_channel = configs.get("drain_channel",2)
        

        self.log.info(f"Using Ch{self.gate_channel} for Gate, Ch{self.drain_channel} for Drain.")
        
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
        """ Enable or disable debug logging on both controller + PSU. """
        self.debug = dbg
        lvl = logging.DEBUG if dbg else logging.INFO
        self.log.setLevel(lvl)
        self.psu.log.setLevel(lvl)
        
    def create_voltage_ramp(self, start, stop, step):
        """ Create an array to use for ramp_voltage, without sending any instructions"""
        
        # Build the voltage setpoint list
        direction = 1 if stop > start else -1
        voltage_array = list(
            np.arange(start, stop + direction * step, direction * abs(step))
        )
        
        # np.arange intentionally does not include the stop value.........
        # just going to add it in instead of trying to use linspace, don't 
        # care about evenly spaced values, # of steps is more important
        voltage_array.append(stop)
        
        # stupid floating point errors
        voltage_array = np.round(voltage_array, 3)
        
        # DEBUG:
        self.log.info(f"Voltage array:")
        self.log.info(f"   {voltage_array}")

        return voltage_array

    def ramp_voltage(self, channel, voltages, delay):
        """
            Smoothly ramp a channel from start→stop in increments of step,
            returning a list of (voltage, current) pairs, with a live tqdm bar.

            During the bar, driver DEBUG logs will appear only if self.debug is True.
        """
        # for making the time array through datetime calls
        timestamps = [] 
        
        # get values from input array
        start, stop, total = voltages[0], voltages[-1], len(voltages)
        
        # Log the overall plan at log.INFO
        self.log.info(f"Ramping CH{channel}: {start:.3f}→{stop:.3f} V over {total} steps")
        
        # DEBUG: suppress or allow all PSU logs under the bar
        prev_setting          = self.psu.log.disabled
        self.psu.log.disabled = not self.debug

        # per-step action to run within run_with_progress
        def step_fn(voltage, channel):
            timestamps.append(time.perf_counter())  # better for elapsed times
            self.psu.set_channel_voltage(channel, voltage)
            V, I = self.psu.get_channel_voltage(channel), self.psu.get_channel_current(channel)
            return (V, I)

        # Run the tqdm helper
        data = run_with_progress(
            iterable=voltages,
            step_fn=step_fn,
            desc=f"CH{channel} {start:.3f}→{stop:.3f}V",
            delay=delay,
            metrics=("V", "I"),
            # fn_kwargs
            channel=channel,
        )

        # DEBUG: Restore the PSU logger’s prior state
        self.psu.log.disabled = prev_setting

        # shift all timestamps to t=0
        times = np.array(timestamps) - timestamps[0]

        return data, times


    def turn_on(self, gate_voltages, drain_voltages, delay):
        """
            Full soft-start: reset → enable outputs → ramp gate → ramp drain.
            Returns (gate_trace, drain_trace).
        """
        
        self.log.info("Beginning HEMT soft-start sequence")
        output_status = self.psu.get_output()
        gate_ch, drain_ch = self.gate_channel, self.drain_channel
        
        # abort this method if the channels are on
        if output_status[gate_ch] is True or output_status[drain_ch] is True:
            print(f"\n"*3)
            raise RuntimeError("We cannot turn the HEMT on if it is currently on!")
        
        # enable outputs
        self.psu.set_output(True, channel=self.gate_channel)
        self.psu.set_output(True, channel=self.drain_channel)
        self.log.info(
            f"Outputs enabled on CH{self.gate_channel} & CH{self.drain_channel}"
        )
        
        ###############################
        ####  turn on gate first!  ####
        ###############################
        
        gate_data, gate_times = self.ramp_voltage(
            channel=self.gate_channel,
            voltages=gate_voltages,
            delay=delay
        )
        
        # check that gate successfully turned on
        gate_voltage = self.psu.get_channel_voltage(self.gate_channel)
        
        if gate_voltage < gate_voltages[-1]:
            error_text = (
            f"\nGate channel {self.gate_channel} did not reach correct gate voltage?"
            f" \n    Target={gate_voltages[-1]}"
            f" \n    Value={gate_voltage}"
            f" \n    Aborting start-up sequence, resetting system to default off state"
            )
            self.reset()
            raise ValueError(error_text)
        
        #################################
        ####  turn on drain second!  ####
        #################################
        
        drain_data, drain_times = self.ramp_voltage(
            channel=self.drain_channel,
            voltages=drain_voltages,
            delay=delay
        )

        self.log.info("HEMT soft-start complete")
        
        return (gate_data, drain_data), (gate_times, drain_times)


    def turn_off(self, step, delay):
        """
            Full soft-shutdown: ramp drain down → ramp gate down → reset.
            Returns (gate_trace, drain_trace).
        """
        
        self.log.info("Beginning HEMT soft-shutdown sequence")
        output_status = self.psu.get_output()
        gate_ch, drain_ch = self.gate_channel, self.drain_channel
        
        # abort this method if the channels are off
        if output_status[gate_ch] is False or output_status[drain_ch] is False:
            raise ZeroDivisionError("We cannot turn the HEMT OFF if it is currently OFF!!!!")
        
        gate_start = self.psu.get_channel_voltage(self.gate_channel)
        drain_start = self.psu.get_channel_voltage(self.drain_channel)
        
        gate_voltages = self.create_voltage_ramp(start=gate_start,
                                                  stop=0.0,
                                                  step= -1*abs(step))
        
        drain_voltages = self.create_voltage_ramp(start=drain_start,
                                                  stop=0.0,
                                                  step= -1*abs(step))
        
        ################################
        ####  turn on drain first!  ####
        ################################
        
        drain_data, drain_times = self.ramp_voltage(
            channel=self.drain_channel,
            voltages=drain_voltages,
            delay=delay,
        )        
        
        # check that drain successfully turned off
        drain_voltage = self.psu.get_channel_voltage(self.drain_channel)
        
        if drain_voltage < drain_voltages[-1]:
            error_text = f"Drain channel {self.drain_channel} did not reach correct drain voltage?" + \
            f" \n    Target={drain_voltages[-1]}" +   \
            f" \n    Value={drain_voltage}"
            raise ValueError(error_text)
        
        
        ################################
        ####  turn on gate second!  ####
        ################################
        
        gate_data, gate_times = self.ramp_voltage(
            channel=self.gate_channel,
            voltages=gate_voltages,
            delay=delay,
        )

        self.reset()
        self.log.info("HEMT soft-shutdown complete")
        return (gate_data, drain_data), (gate_times, drain_times)


    def preview_ramp():
        return 
            

    def plot_iv_pair(self, gate_data, drain_data, optional_times=None):
        """
        Plot Gate and Drain I–V curves side by side.

        gate_data: list of (voltage, current) tuples for gate channel
        drain_data: list of (voltage, current) tuples for drain channel
        """
        # put all figs in one list
        figs = []
        
        # Unpack data
        gate_v, gate_i = zip(*gate_data)
        drain_v, drain_i = zip(*drain_data)

        gate_v, gate_i = np.array(gate_v), np.array(gate_i)
        drain_v, drain_i = np.array(drain_v), np.array(drain_i)

        # unpack the final values for plots later
        final_gate_v, final_drain_v  = gate_v[-1], drain_v[-1]
        final_gate_i, final_drain_i  = gate_i[-1], gate_i[-1]
        
        # Create subplots
        # fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, figsize=(8, 8))
        fig1, ax1_1 = plt.subplots(nrows=1, ncols=1, figsize=(8, 5))
        figs.append(fig1)
        
        # several arrows on the line
        # compute deltas
        dVg = np.diff(gate_v)
        dIg = np.diff(gate_i*1e3)
        dVd = np.diff(drain_v)
        dId = np.diff(drain_i*1e3)

        has_many_points = True if len(gate_v) > 25 else False
        mostly_positive = np.count_nonzero(dVg > 0)
        skip_idx = 8 if has_many_points else 4
        scale = 0.3 if has_many_points else 0.8
        markersize = 3 if has_many_points else 4
        
        if mostly_positive:
            dVg, dIg = np.abs(dVg), np.abs(dIg)
            dVd, dId = np.abs(dVd), np.abs(dId)
        else:
            dVg, dIg = -1*np.abs(dVg), -1*np.abs(dIg)
            dVd, dId = -1*np.abs(dVd), -1*np.abs(dId)
        
        # gate IV curve
        ax1_1.quiver(
            gate_v[:-1:skip_idx], gate_i[:-1:skip_idx]*1e3,  # origins
            dVg[::skip_idx],         dIg[::skip_idx],              # deltas
            angles="xy", scale_units="xy", scale=scale, pivot='mid', 
            alpha=0.9, width=0.0045, color="black"
        )
        
        # drain IV curve
        ax1_1.quiver(
            drain_v[:-1:skip_idx], drain_i[:-1:skip_idx]*1e3,
            dVd[::skip_idx],          dId[::skip_idx],
            angles="xy", scale_units="xy", scale=scale, pivot='mid',
            alpha=0.9, width=0.0045, color="black"
        )
        
        # Gate I–V curve
        ax1_1.plot(gate_v, gate_i*1e3, 'bo', label="Ch1 [Gate]", alpha=1.0, markersize=markersize)
        ax1_1.plot(drain_v, drain_i*1e3, 'ro', label="Ch2 [Drain]", alpha=1.0, markersize=markersize)

        ax1_1.set_xlabel("Voltage (V)")
        ax1_1.set_ylabel("Current (mA)")

        ax1_1.legend()
        
        ax1_1.axhline(0, color='k', linestyle='--', alpha=0.8)
        ax1_1.axvline(0, color='k', linestyle='--', alpha=0.8)

        if self.fake_mode is True:
            fig1.suptitle("FakePSU IV Curve (Ω=40, Ω=70)")
            
        else:
            fig1.suptitle("HEMT I-V Curves")
        
        fig1.tight_layout()
        figs.append(fig1)
        
        
        ax1_1.text(0.1, 0.93, f"\n[Ch{self.gate_channel}] → Final $V_g$ = {final_gate_v:.2f} V", transform=ax1_1.transAxes)
        ax1_1.text(0.1, 0.88, f"\n[Ch{self.drain_channel}] → Final $V_d$ = {final_drain_v:.2f} V", transform=ax1_1.transAxes)


        # create V(t) and I(t) graphs
        if optional_times is not None:
            # unpack container
            gate_times, drain_times = optional_times
            
            # convert to milliseconds if necessary
            if max(gate_times) < 1:
                gate_times *= 1e3
            if max(drain_times) < 1:
                drain_times *= 1e3
            
            # start plotting
            fig2, (ax2_1, ax2_2) = plt.subplots(nrows=2, ncols=1, figsize=(8, 8))
            
            # Gate V(t) curve
            ax2_1.plot(gate_times, gate_v*1e3, 'bo-', label="Ch1 [Gate Voltage]", alpha=1.0, markersize=markersize)
            ax2_1.plot(drain_times, drain_v*1e3, 'ro-', label="Ch2 [Drain Voltage]", alpha=1.0, markersize=markersize)

            # Gate I(t) curve
            ax2_2.plot(gate_times, gate_i*1e3, 'bo-', label="Ch1 [Gate Current]", alpha=0.8, markersize=markersize)
            ax2_2.plot(drain_times, drain_i*1e3, 'ro-', label="Ch2 [Drain Current]", alpha=0.8, markersize=markersize)

            ax2_1.set_ylabel("Voltage (V)")
            ax2_2.set_ylabel("Current (mA)")
            
            ax2_1.set_title("Gate & Drain Voltages")
            ax2_2.set_title("Gate & Drain Currents")
                       
            for ax in [ax2_1, ax2_2]:
                ax.set_xlabel("Time [ms]")
                ax.axhline(0, color='k', linestyle='--', alpha=0.8)
                ax.axvline(0, color='k', linestyle='--', alpha=0.8)
                ax.legend()

        # make sure that user knows a test instrument was used
        if self.fake_mode is True:
            for ax in [ax1_1, ax2_1, ax2_2]:
                ax.text(0.6, 0.7, "FakeInstrument in use", transform=ax.transAxes, color='red')
                    
        # Build a dynamic title and set it on each figure
        # e.g. "2025-05-18 16:42:03 | Gate→1.10V, Drain→0.70V"
        ts = datetime.now().strftime("%B %d, %Y %I:%M:%S %p")
        
        # create titles
        title = f"{ts}\n"
        final_title_fig1 = "HEMTController - IV Curve\n" + title
        final_title_fig2 = "HEMTController - V(t) and I(t) plots\n" + title
        
        fig1.suptitle(final_title_fig1)
        fig2.suptitle(final_title_fig2)
        
        # Apply to all figures
        #   fig1 -> IV curve
        #   fig2 -> optional times
        for fig in [fig1, fig2]:
            fig.tight_layout()
            
        
        return figs


