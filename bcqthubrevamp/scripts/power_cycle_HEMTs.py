# bcqthub/scripts/power_cycle_HEMTs.py

from bcqthubrevamp.controllers.HEMTController import HEMTController
from bcqthubrevamp.controllers.logging_utils import get_logger

log = get_logger("power_cycle_HEMTs", debug=False)
# log.info("Starting HEMT power-cycle script")


###########################################################################
#######  set fake_instrument_mode = True for testing purposes  ############
###########################################################################

cfg = {
    "instrument_name"        : "HEMT_PSU",
    "address"                : "TCPIP0::192.168.0.106::inst0::INSTR",
    "gate_channel"           : 1,
    "drain_channel"          : 2,
    "fake_instrument_mode"   : False,   # <-------- used for testing
} 

ctrl = HEMTController(cfg, debug=False)

script_stepsize = 0.02      # voltage step between.. steps  -> around 0.02 is good
script_delay = 0.008        # time between voltage step     -> around 0.1 is good

###########################################################################
##################     using the turn_on() commands      ##################
###########################################################################

# ping machine for current channel voltage values
gate_start = ctrl.psu.get_channel_voltage(ctrl.gate_channel)
drain_start = ctrl.psu.get_channel_voltage(ctrl.drain_channel)

# create arrays for turn on & turn off using create_voltage_ramp().
gate_ramp_on = ctrl.create_voltage_ramp(
    start = gate_start,    # volts
    stop  = 1.1,           # volts
    step  = script_stepsize,          # volts
)

drain_ramp_on = ctrl.create_voltage_ramp(
    start = drain_start,   # volts
    stop  = 0.7,           # volts
    step  = script_stepsize,          # volts
)

# send a turn_on() command, using our ramp arrays
iv_curves_on, times_on = ctrl.turn_on(gate_voltages=gate_ramp_on, 
                                       drain_voltages=drain_ramp_on,
                                       delay=script_delay)

# separate all the data arrays
gate_iv_on, drain_iv_on = iv_curves_on
gate_times_on, drain_times_on = times_on

# plotting method, adding 'optional_times' creates a second figure
ctrl.plot_iv_pair(gate_iv_on, drain_iv_on, optional_times=(gate_times_on, drain_times_on))


###########################################################################
#################     using the turn_off() commands      ##################
###########################################################################

# if cfg["fake_instrument_mode"] is True:
#     ctrl.psu.channel_outputs = [True, True, True]

# send a turn_off() command, ramps from current voltage to zero, no need for array
iv_curves_off, times_off = ctrl.turn_off(delay=script_delay, 
                                         step=script_stepsize)

# separate all the data
gate_iv_off, drain_iv_off = iv_curves_off
gate_times_off, drain_times_off = times_off

# plotting method, adding 'optional_times' creates a second figure
ctrl.plot_iv_pair(gate_iv_off, drain_iv_off,  optional_times=(gate_times_off, drain_times_off))

# Now show a single comprehensive dump of the instrument state
# log.info("Done!")
ctrl.dump_debug()
     



