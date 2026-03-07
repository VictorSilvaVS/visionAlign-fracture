import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Attempt to import PyQt5 components, but don't make them a hard requirement
# if they are only used for the console_widget.
try:
    from PyQt5.QtGui import QTextCursor # Not directly used here, but often with QTextEdit
    from PyQt5.QtCore import QObject, pyqtSignal
    from PyQt5 import sip # Keep if it was there for a reason, though often not needed explicitly
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    # Define dummy classes if PyQt is not available, so the rest of the code doesn't break
    # if console_widget is unexpectedly passed without PyQt.
    class QObject: pass
    class pyqtSignal:
        def __init__(self, *args, **kwargs): pass
        def emit(self, *args, **kwargs): pass


# --- Global Log Signal Emitter (for PyQt GUI) ---
class LogSignalEmitter(QObject if PYQT_AVAILABLE else object):
    # Make pyqtSignal conditional on PYQT_AVAILABLE
    if PYQT_AVAILABLE:
        log_signal = pyqtSignal(str)
    else:
        # Provide a dummy signal if PyQt is not available
        class DummySignal:
            def emit(self, *args, **kwargs):
                pass # Does nothing
            def connect(self, *args, **kwargs):
                pass # Does nothing
        log_signal = DummySignal()

log_emitter = LogSignalEmitter()


# --- Log Directory Setup ---
# Assumes logger_config.py is in utils, so '..' goes to the project root.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')

# Create the log directory if it doesn't exist
if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR)
        # Initial log to console if directory is created
        print(f"Log directory created: {LOG_DIR}")
    except OSError as e:
        sys.stderr.write(f"ERROR: Could not create log directory {LOG_DIR}: {e}\n")
        # Fallback to current directory if LOG_DIR creation fails
        LOG_DIR = os.path.abspath(".")
        sys.stderr.write(f"Warning: Logging to current directory instead: {LOG_DIR}\n")


# --- Custom QTextEdit Handler (for PyQt GUI) ---
if PYQT_AVAILABLE:
    class QTextEditHandler(logging.Handler):
        def __init__(self, widget):
            super().__init__()
            self.widget = widget
            # Ensure log_emitter.log_signal is connected in the GUI part
            # Example: log_emitter.log_signal.connect(self.widget.append)
            #          log_emitter.log_signal.connect(lambda text: self.widget.moveCursor(QTextCursor.End))

        def emit(self, record):
            if self.widget and not sip.isdeleted(self.widget): # Check if widget exists and not deleted
                msg = self.format(record) # No need to add '\n' if append handles it
                log_emitter.log_signal.emit(msg) # Emit signal for thread-safe update
            # else:
                # Optionally, fallback to console if widget is gone
                # print(self.format(record), file=sys.stderr)

# --- Main Logging Setup Function ---
def setup_logging(app_type, logger_name="VisionAlignApp", level=logging.DEBUG,
                  console_widget=None, specific_log_filename=None):
    """
    Configures the logging system for the application.

    Args:
        app_type (str): Type of the application ("client" or "server").
                        This determines the set of default log files.
        logger_name (str): The name of the logger instance.
        level (int): The base logging level for the logger (e.g., logging.DEBUG, logging.INFO).
        console_widget (QWidget, optional): A PyQt widget (e.g., QTextEdit) to send logs to.
                                            Used if app_type is "client".
        specific_log_filename (str, optional): Full path to a specific log file.
                                               If provided, a handler will be set up for this file.
    Returns:
        logging.Logger: The configured logger instance.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)  # Set the logger's base processing level

    # Remove existing handlers to prevent duplication and resource leaks
    for handler in logger.handlers[:]:
        try:
            handler.close()
        except Exception:
            pass # Ignore errors on close, e.g., if already closed
        logger.removeHandler(handler)

    # --- Standard Formatters ---
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # --- Handler for the specific log file requested by the caller ---
    if specific_log_filename:
        try:
            # Ensure the directory for the specific log file exists
            specific_log_dir = os.path.dirname(specific_log_filename)
            if specific_log_dir and not os.path.exists(specific_log_dir):
                os.makedirs(specific_log_dir, exist_ok=True)

            fh_specific = RotatingFileHandler(
                specific_log_filename, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8' # 5MB
            )
            fh_specific.setFormatter(detailed_formatter)
            fh_specific.setLevel(level) # Use the main level for this specific file
            logger.addHandler(fh_specific)
            logger.info(f"Logging to specific file: {specific_log_filename}")
        except Exception as e:
            sys.stderr.write(f"ERROR: Could not set up specific log file {specific_log_filename}: {e}\n")


    # --- App-type specific handlers ---
    if app_type == "client":
        # Handler for PyQt console widget (if provided and PyQt is available)
        if console_widget and PYQT_AVAILABLE:
            try:
                console_handler = QTextEditHandler(console_widget)
                console_handler.setFormatter(simple_formatter)
                console_handler.setLevel(logging.INFO)  # UI console usually INFO and above
                logger.addHandler(console_handler)
                logger.info("Client GUI console logging configured.")
            except Exception as e:
                sys.stderr.write(f"ERROR: Could not set up QTextEditHandler for client: {e}\n")
        elif console_widget and not PYQT_AVAILABLE:
            sys.stderr.write("WARNING: console_widget provided, but PyQt5 is not available. GUI logging disabled.\n")


        # Default client debug log file (always created for client)
        client_debug_log_path = os.path.join(LOG_DIR, 'client_app_debug.log')
        try:
            fh_client_debug = RotatingFileHandler(
                client_debug_log_path, maxBytes=2*1024*1024, backupCount=3, encoding='utf-8' # 2MB
            )
            fh_client_debug.setFormatter(detailed_formatter)
            fh_client_debug.setLevel(level) # Captures from the base level upwards
            logger.addHandler(fh_client_debug)
            logger.info(f"Client debug log: {client_debug_log_path}")
        except Exception as e:
            sys.stderr.write(f"ERROR: Could not set up client debug log file {client_debug_log_path}: {e}\n")

    elif app_type == "server":
        # Standard console output for server (useful for standalone servers)
        # This will log to the console where the server is run.
        # If specific_log_filename is also used, server logs go to both.
        # If run_client_only.py is a server and has no console_widget, this is its console.
        if not console_widget: # Avoid duplicate console if a widget was somehow passed
            ch_server_stdout = logging.StreamHandler(sys.stdout)
            ch_server_stdout.setFormatter(simple_formatter)
            ch_server_stdout.setLevel(level) # Or logging.INFO if too verbose
            logger.addHandler(ch_server_stdout)
            logger.info("Server console logging (stdout) configured.")

        # General server debug log file
        server_debug_log_path = os.path.join(LOG_DIR, 'server_app_debug.log')
        try:
            fh_server_debug = RotatingFileHandler(
                server_debug_log_path, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8' # 5MB
            )
            fh_server_debug.setFormatter(detailed_formatter)
            fh_server_debug.setLevel(level) # Captures from base level
            logger.addHandler(fh_server_debug)
            logger.info(f"Server debug log: {server_debug_log_path}")
        except Exception as e:
            sys.stderr.write(f"ERROR: Could not set up server debug log file {server_debug_log_path}: {e}\n")

        # General server info log file
        server_info_log_path = os.path.join(LOG_DIR, 'server_app_info.log')
        try:
            fh_server_info = RotatingFileHandler(
                server_info_log_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
            )
            fh_server_info.setFormatter(detailed_formatter)
            fh_server_info.setLevel(logging.INFO)
            logger.addHandler(fh_server_info)
            logger.info(f"Server info log: {server_info_log_path}")
        except Exception as e:
            sys.stderr.write(f"ERROR: Could not set up server info log file {server_info_log_path}: {e}\n")
        
        # General server error log file
        server_error_log_path = os.path.join(LOG_DIR, 'server_app_error.log')
        try:
            fh_server_error = RotatingFileHandler(
                server_error_log_path, maxBytes=2*1024*1024, backupCount=2, encoding='utf-8'
            )
            fh_server_error.setFormatter(detailed_formatter)
            fh_server_error.setLevel(logging.ERROR)
            logger.addHandler(fh_server_error)
            logger.info(f"Server error log: {server_error_log_path}")
        except Exception as e:
            sys.stderr.write(f"ERROR: Could not set up server error log file {server_error_log_path}: {e}\n")

    else:
        # Fallback for unknown app_type: log to standard console
        sys.stderr.write(f"WARNING: Unknown app_type '{app_type}' for logging. Defaulting to console output.\n")
        if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers): # Add only if no stream handler yet
            ch_fallback = logging.StreamHandler(sys.stdout)
            ch_fallback.setFormatter(detailed_formatter)
            ch_fallback.setLevel(level)
            logger.addHandler(ch_fallback)

    if not logger.hasHandlers():
        # Ensure there's at least one handler if all configurations failed
        sys.stderr.write(f"WARNING: Logger '{logger_name}' has no handlers configured. Adding basic console handler.\n")
        ch_emergency = logging.StreamHandler(sys.stderr)
        ch_emergency.setFormatter(simple_formatter)
        ch_emergency.setLevel(logging.WARNING) # Log at least warnings
        logger.addHandler(ch_emergency)
        logger.warning("Emergency console handler added due to lack of other configured handlers.")

    logger.debug(f"Logging setup complete for '{logger_name}' (app_type: {app_type}). Base level: {logging.getLevelName(logger.level)}.")
    return logger

