import argparse
import os
import shutil
import subprocess
import sys
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
    parser.add_argument("--timeout", type=int, default=120,
                        help="Timeout in seconds (default: 120)")
    return parser.parse_args()

# Register signal handler
setup_signal_handler()

# Global variable to store the process reference
process = None

def setup_environment():
    """Configure environment variables needed for pgAdmin4"""
    # Use platform-specific temporary directory
    if os.name == "nt":  # Windows
        temp_dir = tempfile.mkdtemp(prefix="pg4_", dir=os.environ.get("TEMP", tempfile.gettempdir()))
    else:  # macOS and Linux
        temp_dir = tempfile.mkdtemp(prefix="pg4_", dir="/tmp")
    os.environ["XDG_RUNTIME_DIR"] = temp_dir

    # Configure fontconfig to prevent "Cannot load default config file" error
    os.environ["FONTCONFIG_PATH"] = os.path.join(os.environ.get("PREFIX", ""), "etc/fonts")

    # macOS-specific: No DBus setup required
    if os.name == "posix" and "darwin" in os.sys.platform.lower():
        logging.info("Skipping DBus setup on macOS")
        return temp_dir, None

    # Windows-specific: No DBus setup required
    if os.name == "nt":
        logging.info("Skipping DBus setup on Windows")
        return temp_dir, None

    # Start a DBus session and set DBUS_SESSION_BUS_ADDRESS (Linux only)
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

def terminate_process(proc, name):
    """Terminate a process safely."""
    try:
        # Support both psutil.Process and subprocess.Popen objects
        if proc:
            if hasattr(proc, "poll"):  # subprocess.Popen
                if proc.poll() is None:
                    logging.info(f"Terminating {name} process...")
                    proc.terminate()
                    proc.wait()
            elif hasattr(proc, "is_running"):  # psutil.Process
                if proc.is_running():
                    logging.info(f"Terminating {name} process...")
                    proc.terminate()
                    proc.wait(timeout=5)
    except Exception as e:
        logging.error(f"Failed to terminate {name} process: {e}")

def cleanup(temp_dir, dbus_process):
    """Clean up temporary files and terminate processes."""
    terminate_process(process, "pgAdmin4")
    terminate_process(dbus_process, "DBus")

    try:
        if os.path.exists(temp_dir):
            logging.info(f"Removing temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        logging.error(f"Failed to remove temporary directory: {e}")
    time.sleep(10)

def log_environment_variables():
    """Log environment variables for debugging."""
    logging.debug(f"Environment variables: {os.environ}")

def log_processes():
    """Log only new unique process command lines since the last check.
    Print a '.' if nothing changed. Do not repeat unchanged lines."""
    if not hasattr(log_processes, "last_seen_cmds"):
        log_processes.last_seen_cmds = set()
    current_cmds = set()
    for proc in psutil.process_iter(attrs=["cmdline"]):
        try:
            if cmdline := tuple(proc.info.get("cmdline") or []):
                current_cmds.add(cmdline)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    new_cmds = current_cmds - log_processes.last_seen_cmds
    if not new_cmds:
        print('.', end='', flush=True)
    else:
        for cmdline in sorted(new_cmds):
            logging.debug(f"New process: {list(cmdline)}")

    log_processes.last_seen_cmds |= new_cmds


def monitor_pgadmin4_process(timeout):
    """Monitor the pgAdmin4 process and log its status."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if pgadmin_process := is_pgadmin4_running():
            logging.info("TEST: pgAdmin4 process detected as running")
            return pgadmin_process
        log_processes()
        time.sleep(1)
    return None

def log_output(stream, log_func):
    """Log output from a stream in real-time."""
    for line in iter(stream.readline, ""):
        log_func(line.strip())
    stream.close()

def run_pgadmin4(args, stop_event=None):
    global process

    # Start pgAdmin4 process
    prefix = os.environ.get("PREFIX", "")
    pgadmin4_executable = get_pgadmin4_executable(prefix)

    if not os.path.exists(pgadmin4_executable):
        logging.error(f"pgAdmin4 executable not found at {pgadmin4_executable}")
        sys.exit(1)

    # Add flags to disable GPU and sandbox explicitly
    cmd = [pgadmin4_executable, "--no-sandbox", "--disable-gpu", "--disable-software-rasterizer"]
    cmd.extend(args.flags)

    # Check if xvfb-run is needed
    if os.environ.get("HEADLESS", "false").lower() == "true" and os.name != "nt" and "darwin" not in os.sys.platform.lower():
        cmd = ["xvfb-run", "--auto-servernum"] + cmd

    # Log the full command and environment variables
    logging.info(f"Executing command: {' '.join(cmd)}")
    log_environment_variables()

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )

        # Log stdout and stderr in real-time
        stdout_thread = threading.Thread(target=log_output, args=(process.stdout, logging.info))
        stderr_thread = threading.Thread(target=log_output, args=(process.stderr, logging.error))
        stdout_thread.start()
        stderr_thread.start()

        # Wait for process or stop_event
        while True:
            if stop_event and stop_event.is_set():
                terminate_process(process, "pgAdmin4")
                break
            if process.poll() is not None:
                break
            time.sleep(0.2)

        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)

        if process.returncode == -15:
            logging.info(f"pgAdmin4 process terminated by SIGTERM (expected). Return code: {process.returncode}")
        elif process.returncode != 0:
            logging.error(f"pgAdmin4 process exited with an error. Return code: {process.returncode}")
    except subprocess.TimeoutExpired:
        logging.error("Process timed out!")
        terminate_process(process, "pgAdmin4")
    except Exception as e:
        logging.error(f"Unexpected error while running pgAdmin4: {e}")
    finally:
        terminate_process(process, "pgAdmin4")

def get_pgadmin4_executable(prefix):
    """Get the platform-specific pgAdmin4 executable path."""
    if os.name == "posix" and "darwin" in os.sys.platform.lower():
        # macOS-specific: Use the .app bundle
        return os.path.join(prefix, "usr/pgadmin4.app/Contents/MacOS/pgadmin4")
    elif os.name == "nt":
        # Windows-specific: Use the .exe file
        return os.path.join(prefix, "Library", "usr", "pgadmin4", "bin", "pgadmin4.exe")
    else:
        # Default executable path for Linux
        return os.path.join(prefix, "usr/pgadmin4/bin/pgadmin4")

def is_pgadmin4_running():
    """Check if pgAdmin4.py process is running and return the process if found."""
    for proc in psutil.process_iter(attrs=["cmdline", "pid", "name"]):
        try:
            cmdline = proc.info.get("cmdline")
            name = proc.info.get("name", "").lower()
            if os.name == "nt":
                # On Windows, check for pgadmin4.exe or python.exe running pgAdmin4.py
                if name == "pgadmin4.exe":
                    logging.info(f"pgadmin4.exe is running with PID: {proc.info['pid']} {cmdline}")
                    return proc
                if name == "python.exe" and cmdline and any("pgAdmin4.py" in arg for arg in cmdline):
                    logging.info(f"python.exe running pgAdmin4.py is running with PID: {proc.info['pid']} {cmdline}")
                    return proc
            elif cmdline is not None and any("pgAdmin4.py" in arg for arg in cmdline):
                logging.info(f"pgAdmin4.py is running with PID: {proc.info['pid']} {cmdline}")
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def shutdown_and_exit(exit_code, temp_dir, dbus_process, stop_event, pgadmin_thread, timer=None):
    """Unified cleanup and exit routine."""
    cleanup(temp_dir, dbus_process)
    stop_event.set()
    if pgadmin_thread:
        pgadmin_thread.join(timeout=10)
        if pgadmin_thread.is_alive():
            logging.warning("pgAdmin4 thread still alive after cleanup.")
    if timer:
        timer.cancel()
    sys.exit(exit_code)

def main():
    args = parse_args()
    timer = setup_timeout(args.timeout)
    temp_dir, dbus_process = setup_environment()
    stop_event = threading.Event()
    pgadmin_thread = None

    try:
        pgadmin_thread = threading.Thread(target=run_pgadmin4, args=(args, stop_event))
        pgadmin_thread.daemon = True
        pgadmin_thread.start()

        pgadmin_process = monitor_pgadmin4_process(args.timeout)
        if pgadmin_process:
            try:
                logging.info("Test completed - pgAdmin4 started successfully")
                terminate_process(pgadmin_process, "python pgAdmin4.py")
                if process and (not pgadmin_process or process.pid != pgadmin_process.pid):
                    terminate_process(process, "pgAdmin4")
                terminate_process(dbus_process, "DBus")
                shutdown_and_exit(0, temp_dir, dbus_process, stop_event, pgadmin_thread, timer)
            except Exception as e:
                logging.error(f"Failed to terminate pgAdmin4.py process: {e}")
                shutdown_and_exit(1, temp_dir, dbus_process, stop_event, pgadmin_thread, timer)
        else:
            logging.warning("Maximum wait time reached - exiting with success anyway")
            terminate_process(process, "pgAdmin4")
            terminate_process(dbus_process, "DBus")
            shutdown_and_exit(1, temp_dir, dbus_process, stop_event, pgadmin_thread, timer)

    except KeyboardInterrupt:
        logging.warning("Test interrupted by user")
        terminate_process(process, "pgAdmin4")
        terminate_process(dbus_process, "DBus")
        shutdown_and_exit(0, temp_dir, dbus_process, stop_event, pgadmin_thread, timer)
    except Exception as e:
        logging.error(f"Error: {e}")
        terminate_process(process, "pgAdmin4")
        terminate_process(dbus_process, "DBus")
        shutdown_and_exit(1, temp_dir, dbus_process, stop_event, pgadmin_thread, timer)

if __name__ == "__main__":
    main()
