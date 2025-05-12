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

log.info("Soft-starting HEMTs")
gate_iv_on, drain_iv_on = ctrl.turn_on(
    gate_stop=1.1, drain_stop=0.7,   # volts, volts
    step=0.02, delay=0.2,            # volts, seconds
    dry_run=False,
)

plot_iv_pair(gate_iv_on, drain_iv_on)

# Now show a single comprehensive dump of the instrument state
# ctrl.dump_debug()

log.info("Soft-shutting down HEMTs")
gate_iv_off, drain_iv_off = ctrl.turn_off(
    step=0.02, delay=0.2,   # volts, seconds
    dry_run=False,          
)

log.info("Done.")
plot_iv_pair(gate_iv_off, drain_iv_off)
    



