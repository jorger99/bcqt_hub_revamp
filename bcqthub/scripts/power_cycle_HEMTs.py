from bcqthub.controllers.HEMTController import HEMTController
from bcqthub.controllers.HEMTController import plot_iv_pair
from bcqthub.controllers.logging_utils import get_logger

log = get_logger("power_cycle_HEMTs", debug=False)
log.info("Starting HEMT power-cycle script")

cfg = {
    "instrument_name": "HEMT_PSU",
    "address"        : "TCPIP0::192.168.0.106::inst0::INSTR",
    # "address"        : "TestInstrument",
}

ctrl = HEMTController(cfg, debug=False)

sweep_turn_on = [1.1, 0.7, 0.02]  # [gate stop, drain stop, step]

log.info("Soft-starting HEMTs")
gate_iv_on, drain_iv_on = ctrl.turn_on(
    *sweep_turn_on, delay=0.5,     # if dry_run = True, everything 
    dry_run=True,                  # runs without sending cmds to instrument
)

log.info("Plotting IV curves for turn_on()")
plot_iv_pair(gate_iv_on, drain_iv_on)

# Now show a single comprehensive dump of the instrument state
# ctrl.dump_debug()

log.info("Soft-shutting down HEMTs")
gate_iv_off, drain_iv_off = ctrl.turn_off(
    step=0.02, delay=0.2,          # takes whatever the input is, ramps to zero
    dry_run=True,                  # runs without sending cmds to instrument
)

log.info("Plotting IV curves for turn_off()")
plot_iv_pair(gate_iv_off, drain_iv_off)


log.info("Done.")

    



