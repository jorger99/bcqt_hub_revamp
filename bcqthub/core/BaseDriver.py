import logging
import time
from abc import ABC, abstractmethod
import pyvisa


class BaseDriver(ABC):
    """Abstract base for all VISA instrument drivers."""

    _rm = None  # shared PyVISA ResourceManager singleton

    def __init__(self, configs: dict, debug: bool = False, **kwargs):
        """
        :param configs: dict with keys:
            - 'instrument_name': human-readable name
            - 'address': VISA resource string (e.g., 'GPIB::9::INSTR')
            - optional 'rm_backend': PyVISA backend specifier
        :param debug: if True, set logger to DEBUG level
        """
        # Required configs
        self.configs = configs
        self.instrument_name = configs.get("instrument_name", "Unknown")
        self.address = configs.get("address")
        if not self.address:
            raise ValueError("configs must include 'address' key with VISA resource string")
        self.debug = debug

        # Internal state
        self.resource = None
        self.debug_writes = 0

        # Logger setup
        self.logger = logging.getLogger(self.instrument_name)
        self.logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            fmt = logging.Formatter(f"[{self.instrument_name}] %(levelname)s: %(message)s")
            handler.setFormatter(fmt)
            self.logger.addHandler(handler)

        # Apply extra attributes
        self.set_default_attrs(**kwargs)

        # Connect to instrument
        self.connect()

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
                self.logger.debug("ResourceManager initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize ResourceManager: {e}")
                raise
        self.rm = BaseDriver._rm

        # Close existing session
        if self.resource:
            try:
                self.resource.close()
                self.logger.debug("Closed previous session")
            except Exception as e:
                self.logger.warning(f"Error closing session: {e}")

        # Open resource
        try:
            self.resource = self.rm.open_resource(self.address)
            self.logger.info(f"Connected to {self.address}")
        except Exception as e:
            self.logger.error(f"Failed to open resource {self.address}: {e}")
            raise

    def disconnect(self):
        """Cleanly close the instrument session."""
        if self.resource:
            try:
                self.resource.close()
                self.logger.info("Session closed")
            except Exception as e:
                self.logger.warning(f"Error during disconnect: {e}")
            finally:
                self.resource = None

    @abstractmethod
    def idn(self) -> str:
        """Query *IDN? for identification."""
        ...

    # --- SCPI wrappers ---
    def write(self, cmd: str):
        """Write command to instrument with debug logging."""
        self.logger.debug(f"WRITE: {cmd}")
        return self.resource.write(cmd)

    def read(self) -> str:
        """Read raw string from instrument."""
        self.logger.debug("READ")
        return self.resource.read()

    def write_check(self, cmd: str):
        """Write then clear ESR for synchronization."""
        self.write(cmd)
        try:
            self.resource.write("*ESE 1")
            self.resource.query("*ESR?")
        except Exception as e:
            self.handle_VisaIOError(cmd, e)
        return True

    def query(self, cmd: str) -> str:
        """Send query and return raw string."""
        self.logger.debug(f"QUERY: {cmd}")
        return self.resource.query(cmd)

    def query_check(self, cmd: str, fmt=str) -> any:
        """Query with error handling and formatting."""
        try:
            val = self.resource.query(cmd)
        except pyvisa.InvalidSession as e:
            self.handle_InvalidSession_error(cmd, e)
            val = self.resource.query(cmd)
        except pyvisa.VisaIOError as e:
            self.handle_VisaIOError(cmd, e)
            raise
        return fmt(val)

    # --- Utility methods ---
    def strip_specials(self, msg: str) -> str:
        """Strip CR/LF and pluses."""
        return msg.replace("\r", "").replace("\n", "").replace("+", "")

    def return_instrument_parameters(self, print_output=False) -> dict:
        """Run all get_* methods and return a dict of their results."""
        params = {}
        for name in dir(self):
            if name.startswith("get_") and callable(getattr(self, name)):
                try:
                    val = getattr(self, name)()
                    params[name] = val
                    if print_output:
                        self.logger.info(f"{name}: {val}")
                except Exception as e:
                    self.logger.warning(f"Error in {name}: {e}")
        return params

    def set_default_attrs(self, **kwargs):
        """Set and log extra attributes from configs."""
        for k, v in kwargs.items():
            setattr(self, k, v)
            self.logger.debug(f"Set attribute {k}={v}")

    # --- Error handlers ---
    def handle_VisaIOError(self, cmd: str, err: Exception):
        self.logger.error(f"VisaIOError on '{cmd}': {err}")
        queue = self.check_instr_error_queue(print_output=True)
        self.logger.error(f"Error queue: {queue}")

    def handle_InvalidSession_error(self, cmd: str, err: Exception):
        self.logger.warning(f"InvalidSession on '{cmd}': {err}, reconnecting...")
        time.sleep(1)
        self.connect()

    # --- Debug utilities ---
    def debug_read(self, extra="") -> str:
        self.logger.debug(f"{extra} Attempting read (writes={self.debug_writes})")
        result = self.read()
        self.debug_writes = max(0, self.debug_writes - 1)
        self.logger.debug(f"Read success (writes={self.debug_writes}): {result}")
        return result

    def debug_write(self, cmd: str, extra="", count=True):
        self.logger.debug(f"{extra} Attempting write '{cmd}' (writes={self.debug_writes})")
        self.write(cmd)
        if count:
            self.debug_writes += 1
        self.logger.debug(f"Write success (writes={self.debug_writes})")

    def debug_force_clear(self):
        """Continuously read until exception to clear buffer."""
        self.debug_writes = 0
        self.logger.debug("Starting force clear loop")
        try:
            i = 0
            while True:
                time.sleep(1)
                self.logger.debug(f"Force clear iteration {i}")
                self.debug_read()
                i += 1
        except Exception as e:
            self.logger.info(f"Force clear stopped: {e}")

    def debug_queue_script(self, init_cmd=None, sleep_time=0.5, write_cmd_loop=None):
        """Loop read/write to stress-test session stability."""
        self.debug = True
        self.logger.debug("Starting debug_queue_script")
        if init_cmd:
            self.debug_write(init_cmd, extra="INIT", count=False)
        count = 0
        try:
            while True:
                if write_cmd_loop:
                    self.debug_write(write_cmd_loop)
                else:
                    self.debug_read()
                count += 1
                time.sleep(sleep_time)
        except KeyboardInterrupt:
            self.logger.info(f"debug_queue_script stopped after {count} iterations")
