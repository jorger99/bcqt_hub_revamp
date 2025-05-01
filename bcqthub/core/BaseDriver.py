import time, inspect
import pyvisa

from abc import ABC, abstractmethod
from bcqthub.controllers.logging_utils import get_logger
from collections import OrderedDict  # or just dict() in 3.7+


class BaseDriver(ABC):
    """Abstract base for all VISA instrument drivers."""

    _rm = None  # shared PyVISA ResourceManager singleton

    def __init__(self, configs: dict, debug: bool=True, **kwargs):
        """
        :param configs: dict with keys:
            - 'instrument_name': human-readable name
            - 'address': VISA resource string (e.g., 'GPIB::9::INSTR')
            - optional 'rm_backend': PyVISA backend specifier
        :param debug: if True, set logger to DEBUG level
        """
        self.configs = configs
        self.debug   = debug
        self.log     = get_logger(self.configs.get("instrument_name", "Driver"), self.debug)
        self.instrument_name = self.configs.get("instrument_name", "UnknownInstrument")
        self.address = self.configs.get("address")
        if not self.address:
            raise ValueError("configs must include 'address' key with VISA resource string")

        # Internal state
        self.resource = None
        self.debug_writes = 0

        # Apply extra attributes
        self.set_default_attrs(**kwargs)

        # Connect to instrument
        self.connect()
        
        # used for debugging purposes        
        self._last_scpi = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def __del__(self):
        self.disconnect()

    def connect(self):
        """Initialize or reuse ResourceManager and open instrument session."""
        backend = self.configs.get("rm_backend")
        if BaseDriver._rm is None:
            try:
                BaseDriver._rm = (pyvisa.ResourceManager(backend)
                                  if backend else pyvisa.ResourceManager())
                self.log.debug("ResourceManager initialized")
            except Exception as e:
                self.log.error(f"Failed to initialize ResourceManager: {e}")
                raise
        self.rm = BaseDriver._rm

        # Close existing session
        if self.resource:
            try:
                self.resource.close()
                self.log.debug("Closed previous session")
            except Exception as e:
                self.log.warning(f"Error closing session: {e}")

        # Open resource
        try:
            self.resource = self.rm.open_resource(self.address)
            self.log.info(f"Connected to {self.address}")
        except Exception as e:
            self.log.error(f"Failed to open resource {self.address}: {e}")
            raise

    def disconnect(self):
        """Cleanly close the instrument session."""
        if self.resource:
            try:
                self.resource.close()
                self.log.info("Session closed")
            except Exception as e:
                self.log.warning(f"Error during disconnect: {e}")
            finally:
                self.resource = None

    @abstractmethod
    def idn(self) -> str:
        """Query *IDN? for identification."""

    # -------------------------------------------------------------------------
    # Instrument‐level error querying
    # -------------------------------------------------------------------------

    def _visa_error_check(self, op_name, func, *args, **kwargs):
        """
        Wrap any pyvisa call to catch VisaIOError uniformly.
        :param op_name: “write”, “read” or “query”
        :param func: the bound VISA method (e.g. self.resource.write)
        """
        # Before calling, stash the SCPI text if it’s a write or query
        if op_name in ("write", "query") and args:
            # e.g. args[0] is the SCPI string for write/query
            self._last_scpi = args[0]
            
        try:
            return func(*args, **kwargs)
        except pyvisa.VisaIOError as e:
            self.log.error(f"VISA {op_name} error on `{self._last_scpi}`: {e}", exc_info=True)
            raise    
        
    def _check_instrument_errors(self):
        resp = self.resource.query("SYST:ERR?").strip()
        code_str, msg = resp.split(",", 1)
        code = int(code_str)
        msg = msg.strip().strip('"')
        if code != 0:
            self.log.error(
                f"Instrument error {code} on `{self._last_scpi}`: {msg}"
            )
            # don’t swallow it—let it bubble so you can catch it
            raise RuntimeError(f"SYST:ERR? → {code}: {msg}")
        
    def write_check(self, cmd: str):
        """
        Write a command, catch VISA issues, then poll SYST:ERR?.
        """
        # 1) VISA transport error check
        self._visa_error_check("write", self.resource.write, cmd)
        # 2) SCPI‐level error check
        self._check_instrument_errors()

    def read_check(self, fmt=str):
        """
        Read raw response, catch VISA issues, no SCPI error polling.
        Returns casted result.
        """
        raw = self._visa_error_check("read", self.resource.read)
        return fmt(raw)

    def query_check(self, cmd: str, fmt=str):
        """
        Send query, catch VISA issues, no SCPI error polling.
        Returns casted result.
        """
        raw = self._visa_error_check("query", self.resource.query, cmd)
        return fmt(raw)


    # --- SCPI wrappers ---
    def write(self, cmd: str):
        """Write command to instrument with debug logging."""
        self.log.debug(f"WRITE: {cmd}")
        return self.resource.write(cmd)

    def read(self) -> str:
        """Read raw string from instrument."""
        self.log.debug("READ")
        return self.resource.read()


    def query(self, cmd: str) -> str:
        """Send query and return raw string."""
        self.log.debug(f"QUERY: {cmd}")
        return self.resource.query(cmd)


    # --- Utility methods ---
    def strip_specials(self, msg: str) -> str:
        """Strip CR/LF and pluses."""
        return msg.replace("\r", "").replace("\n", "").replace("+", "")

    def return_instrument_parameters(self, print_output=False):
        """
        Calls each zero-arg get_* method and returns an OrderedDict.
        If it finds a get_* that requires args, it logs a warning and skips it.
        """
        params = OrderedDict()

        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            # skip dunders and non-get_ methods
            if not name.startswith("get_") or name.startswith("__"):
                continue

            sig = inspect.signature(method)
            if sig.parameters:
                self.log.warning(
                    f"Skipping {name}(): requires parameters, cannot auto-dump."
                )
                continue

            try:
                val = method()
                params[name] = val
                if print_output:
                    self.log.info(f"{name} -> {val}")
            except Exception as e:
                self.log.warning(f"{name}() raised: {e}")

        return params

    
    def set_default_attrs(self, **kwargs):
        """Set and log extra attributes from configs."""
        for k, v in kwargs.items():
            setattr(self, k, v)
            self.log.debug(f"Set attribute {k}={v}")

    # --- Error handlers ---
    def handle_VisaIOError(self, cmd: str, err: Exception):
        self.log.error(f"VisaIOError on '{cmd}': {err}")
        queue = self.check_instr_error_queue(print_output=True)
        self.log.error(f"Error queue: {queue}")

    def handle_InvalidSession_error(self, cmd: str, err: Exception):
        self.log.warning(f"InvalidSession on '{cmd}': {err}, reconnecting...")
        time.sleep(1)
        self.connect()

    # --- Debug utilities ---
    def dump_debug_info(self):
        """
        One-shot dump: identity plus *all* of the zero-arg get_* methods
        as defined by return_instrument_parameters.
        """
        self.log.debug("=== dump_debug_info start ===")
        # 1) IDN
        try:
            idn = self.query_check("*IDN?")
            self.log.debug(f"IDN: {idn}")
        except Exception as e:
            self.log.warning(f"IDN() failed: {e}")

        # 2) All the get_* values
        try:
            # print_output=True will log each param at INFO (or DEBUG level
            # depending on your handler), so you don’t need an explicit loop here
            self.return_instrument_parameters(print_output=True)
        except Exception as e:
            self.log.warning(f"auto-dump of get_* failed: {e}")

        self.log.debug("=== dump_debug_info end ===")




    # def debug_read(self, extra="") -> str:
    #     self.log.debug(f"{extra} Attempting read (writes={self.debug_writes})")
    #     result = self.read()
    #     self.debug_writes = max(0, self.debug_writes - 1)
    #     self.log.debug(f"Read success (writes={self.debug_writes}): {result}")
    #     return result

    # def debug_write(self, cmd: str, extra="", count=True):
    #     self.log.debug(f"{extra} Attempting write '{cmd}' (writes={self.debug_writes})")
    #     self.write(cmd)
    #     if count:
    #         self.debug_writes += 1
    #     self.log.debug(f"Write success (writes={self.debug_writes})")

    # def debug_force_clear(self):
    #     """Continuously read until exception to clear buffer."""
    #     self.debug_writes = 0
    #     self.log.debug("Starting force clear loop")
    #     try:
    #         i = 0
    #         while True:
    #             time.sleep(1)
    #             self.log.debug(f"Force clear iteration {i}")
    #             self.debug_read()
    #             i += 1
    #     except Exception as e:
    #         self.log.info(f"Force clear stopped: {e}")

    # def debug_queue_script(self, init_cmd=None, sleep_time=0.5, write_cmd_loop=None):
    #     """Loop read/write to stress-test session stability."""
    #     self.debug = True
    #     self.log.debug("Starting debug_queue_script")
    #     if init_cmd:
    #         self.debug_write(init_cmd, extra="INIT", count=False)
    #     count = 0
    #     try:
    #         while True:
    #             if write_cmd_loop:
    #                 self.debug_write(write_cmd_loop)
    #             else:
    #                 self.debug_read()
    #             count += 1
    #             time.sleep(sleep_time)
    #     except KeyboardInterrupt:
    #         self.log.info(f"debug_queue_script stopped after {count} iterations")
