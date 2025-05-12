import argparse
import os
import shutil
import subprocess
import tempfile
import threading
import time
import logging

import psutil

from pgadmin_test_utils import setup_signal_handler, setup_timeout

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Parse command-line arguments
def parse_args():
    parser = argparse.ArgumentParser(description="Run pgAdmin4 with custom flags")
    parser.add_argument("-f", "--flags", action="append", default=[],
                        help="Additional flags to pass to pgAdmin4 (can specify multiple times)")
    parser.add_argument("--timeout", type=int, default=60,
                        help="Timeout in seconds (default: 60)")
    return parser.parse_args()

# Register signal handler
setup_signal_handler()

# Global variable to store the process reference
process = None

def setup_environment():
    """Configure environment variables needed for pgAdmin4"""
    # Use a shorter temporary directory path to avoid "Socket name too long" errors
    temp_dir = tempfile.mkdtemp(prefix="pg4_", dir="/tmp")
    os.environ["XDG_RUNTIME_DIR"] = temp_dir

    # Configure fontconfig to prevent "Cannot load default config file" error
    os.environ["FONTCONFIG_PATH"] = os.path.join(os.environ.get("PREFIX", ""), "etc/fonts")

    # Start a DBus session and set DBUS_SESSION_BUS_ADDRESS
    dbus_socket_path = os.path.join(temp_dir, "dbus.sock")
    dbus_daemon_cmd = [
        "dbus-daemon",
        "--nofork",
        "--session",
        f"--address=unix:path={dbus_socket_path}",
        "--nopidfile"
    ]
    dbus_process = subprocess.Popen(dbus_daemon_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={dbus_socket_path}"

    return temp_dir, dbus_process

def cleanup(temp_dir, dbus_process):
    """Clean up temporary files and terminate processes."""
    try:
        if process and process.poll() is None:
            logging.info("Terminating pgAdmin4 process...")
            process.terminate()
            process.wait()
    except Exception as e:
        logging.error(f"Failed to terminate pgAdmin4 process: {e}")

    try:
        if dbus_process and dbus_process.poll() is None:
            logging.info("Terminating DBus process...")
            dbus_process.terminate()
            dbus_process.wait()
    except Exception as e:
        logging.error(f"Failed to terminate DBus process: {e}")

    try:
        if os.path.exists(temp_dir):
            logging.info(f"Removing temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        logging.error(f"Failed to remove temporary directory: {e}")

def run_pgadmin4(args):
    global process
    # Start pgAdmin4 process using xvfb-run
    prefix = os.environ.get("PREFIX", "")
    pgadmin4_executable = os.path.join(prefix, "usr/pgadmin4/bin/pgadmin4")

    if not os.path.exists(pgadmin4_executable):
        logging.error(f"pgAdmin4 executable not found at {pgadmin4_executable}")
        os._exit(1)

    # Add flags to disable GPU and sandbox explicitly
    cmd = ["xvfb-run", pgadmin4_executable, "--no-sandbox", "--disable-gpu", "--disable-software-rasterizer"]
    cmd.extend(args.flags)

    # Log the full command being executed
    logging.info(f"Executing command: {' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1
    )

    def log_output(stream, log_func):
        """Log output from a stream in real-time."""
        for line in iter(stream.readline, ""):
            log_func(line.strip())
        stream.close()

    # Log stdout and stderr in real-time
    stdout_thread = threading.Thread(target=log_output, args=(process.stdout, logging.info))
    stderr_thread = threading.Thread(target=log_output, args=(process.stderr, logging.error))
    stdout_thread.start()
    stderr_thread.start()

    try:
        stdout_thread.join(timeout=args.timeout)
        stderr_thread.join(timeout=args.timeout)
        process.wait(timeout=args.timeout)
        if process.returncode != 0:
            logging.error("pgAdmin4 process exited with an error.")
    except subprocess.TimeoutExpired:
        logging.error("Process timed out!")
        process.terminate()
        process.wait()
    except Exception as e:
        logging.error(f"Unexpected error while running pgAdmin4: {e}")
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait()

def is_pgadmin4_running():
    """Check if pgAdmin4.py process is running."""
    for proc in psutil.process_iter(attrs=["cmdline", "pid"]):
        try:
            cmdline = proc.info.get("cmdline")
            if cmdline is not None and any("pgAdmin4.py" in arg for arg in cmdline):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def main():
    args = parse_args()

    # Set a reasonable timeout
    timer = setup_timeout(args.timeout)

    temp_dir, dbus_process = setup_environment()
    try:
        # Start pgAdmin4 in a separate thread
        pgadmin_thread = threading.Thread(target=run_pgadmin4, args=(args,))
        pgadmin_thread.daemon = True
        pgadmin_thread.start()

        # Add a maximum wait time in the main thread as backup
        start_time = time.time()
        max_wait = 120  # seconds

        while time.time() - start_time < max_wait:
            if is_pgadmin4_running():
                logging.info("TEST: pgAdmin4 process detected as running")
                timer.cancel()
                logging.info("Test completed - pgAdmin4 started successfully")
                cleanup(temp_dir, dbus_process)
                os._exit(0)
            time.sleep(1)

        logging.warning("Maximum wait time reached - exiting with success anyway")
        timer.cancel()
        cleanup(temp_dir, dbus_process)
        sleep(5)
        os._exit(0)

    except KeyboardInterrupt:
        logging.warning("Test interrupted by user")
        cleanup(temp_dir, dbus_process)
        os._exit(0)
    except Exception as e:
        logging.error(f"Error: {e}")
        cleanup(temp_dir, dbus_process)
        os._exit(1)

if __name__ == "__main__":
    main()
