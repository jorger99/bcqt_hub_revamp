from bcqthub.controllers.HEMTController import HEMTController
from bcqthub.controllers.logging_utils import get_logger
import logging

def main():
    log = get_logger("power_cycle_HEMTs", debug=True)
    log.info("Starting HEMT power‐cycle script")

    cfg = {
        "instrument_name": "HEMT_PSU",
        "address":         "TCPIP0::192.168.0.106::inst0::INSTR",
        "use_factory_limits": True,
    }

    ctrl = HEMTController(cfg, debug=False)
    log.info("Soft-starting HEMTs")
    gate_iv, drain_iv = ctrl.turn_on(
        gate_stop=1.1, drain_stop=0.7, step=0.5, delay=0.2
    )

    gate_data  = ctrl.ramp_voltage(1,  0.0, 2.0,  0.1, 0.2)
    ctrl.psu.debug = True
    drain_data = ctrl.ramp_voltage(2, 0.0, 2.0, 0.1, 0.2)
    
    log.info("Soft-shutting down HEMTs")
    ctrl.turn_off(
        gate_start=1.1, drain_start=0.7, step=0.05, delay=0.2
    )

    log.info("Done.")

def main2():
    log = get_logger("power_cycle_HEMTs", debug=False)
    log.info("Starting HEMT power-cycle script")

    cfg = {
        "instrument_name": "HEMT_PSU",
        "address"        : "TCPIP0::192.168.0.106::inst0::INSTR",
        "use_factory_limits": True,
    }

    ctrl = HEMTController(cfg, debug=False)

    # Do a clean ramp
    # log.info("Soft-starting HEMTs")
    # gate_iv, drain_iv = ctrl.turn_on(
    #     gate_stop=1.1, drain_stop=0.7, step=0.05, delay=0.02
    # )

    # Now show a single comprehensive dump of the instrument state
    ctrl.dump_debug()

    # input("Press ENTER to soft-shutdown…")
    log.info("Soft-shutting down HEMTs")
    ctrl.set_debug(True)
    
    ctrl.turn_off(
        gate_start=1.1, drain_start=0.7, step=0.05, delay=0.02
    )

    log.info("Done.")
    
if __name__ == "__main__":
    main2()


