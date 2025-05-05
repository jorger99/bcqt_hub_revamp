from bcqthub.controllers.HEMTController import HEMTController
from bcqthub.controllers.HEMTController import plot_iv_pair
from bcqthub.controllers.logging_utils import get_logger
import logging


log = get_logger("power_cycle_HEMTs", debug=False)
log.info("Starting HEMT power-cycle script")

cfg = {
    "instrument_name": "HEMT_PSU",
    # "address"        : "TCPIP0::192.168.0.106::inst0::INSTR",
    "address"        : "TestInstrument",
}

ctrl = HEMTController(cfg, debug=False)

log.info("Soft-starting HEMTs")
gate_iv, drain_iv = ctrl.turn_on(
    gate_stop=1.1, drain_stop=0.7, step=0.05, delay=0.02
)

# Now show a single comprehensive dump of the instrument state
ctrl.dump_debug()

# input("Press ENTER to soft-shutdown…")
log.info("Soft-shutting down HEMTs")
# ctrl.set_debug(True)

""" #TODO "turn_off" should always start at the current voltage """
ctrl.turn_off()

log.info("Done.")
    



