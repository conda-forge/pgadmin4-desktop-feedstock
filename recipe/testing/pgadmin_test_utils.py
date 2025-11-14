import os
import signal
import subprocess
import sys
import threading
import time
import requests


def setup_signal_handler():
    """Set up a signal handler for graceful shutdown."""
    def signal_handler(sig, frame):
        print("Shutting down gracefully...")
        time.sleep(1)
        os._exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)


def setup_timeout(seconds=60):
    """Set up a timeout that will terminate the program if exceeded."""
    def timeout_handler():
        print(f"Timeout reached after {seconds} seconds - terminating test")
        # Print thread info to help diagnose where it might be stuck
        print("Active threads at timeout:")
        for thread in threading.enumerate():
            print(f"  - {thread.name}")
        os._exit(2)
    
    timer = threading.Timer(seconds, timeout_handler)
    timer.start()
    return timer


def wait_for_server(url="http://127.0.0.1:5050/login", max_attempts=10,
                    wait_seconds=2, timeout=5):
    """Wait for server to start by repeatedly checking the URL."""
    print(f"Waiting for server to start at {url}...")

    for attempt in range(max_attempts):
        try:
            time.sleep(wait_seconds)
            response = requests.get(url, timeout=timeout)
            # Consider both 200 and 401 as successful responses for the login page
            if response.status_code in [200, 401]:
                print(f"Server is up! Status code: {response.status_code}")
                return True
        except requests.exceptions.RequestException:
            print(f"Attempt {attempt+1}/{max_attempts} - Server not ready yet")

    print("Server failed to start properly")
    return False


def check_cpu_compatibility():
    """
    Check if the CPU supports the minimum instruction sets required by Electron.
    Electron 34+ requires SSE4.2 and may use AVX2 if available.

    Returns:
        tuple: (is_compatible: bool, missing_features: list, reason: str)
    """
    try:
        # Read CPU flags from /proc/cpuinfo
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read()

        # Extract flags line (all CPUs should have same flags, so use first one)
        flags_line = None
        for line in cpuinfo.split("\n"):
            if line.startswith("flags"):
                flags_line = line
                break

        if not flags_line:
            # Can't determine CPU features, assume compatible to avoid false negatives
            return True, [], "CPU flags not available, assuming compatible"

        flags = set(flags_line.split(":")[1].strip().split())

        # Minimum required features for Electron 34
        required_features = {"sse2", "sse4_2"}
        missing = required_features - flags

        if missing:
            return False, list(missing), f"CPU missing required instructions: {', '.join(missing)}"

        # Check for recommended features
        recommended_features = {"avx", "avx2"}
        missing_recommended = recommended_features - flags

        if missing_recommended:
            print(f"Warning: CPU missing recommended features: {', '.join(missing_recommended)}")
            print("Electron may run slower or encounter compatibility issues")

        return True, [], "CPU compatible"

    except Exception as e:
        # On error, assume compatible to avoid breaking tests on systems where we can't check
        print(f"Warning: Could not check CPU compatibility: {e}")
        return True, [], f"CPU check failed: {e}, assuming compatible"


def test_electron_binary_loadable(binary_path, use_xvfb=False):
    """
    Test if an Electron binary can be loaded and started without crashing.
    This helps detect SIGILL before running the full test.

    The test performs multiple checks:
    1. --version flag (tests binary loader)
    2. Actual startup with --no-sandbox (tests Chromium/V8 initialization)

    Returns:
        tuple: (is_loadable: bool, error_message: str)
    """
    if not os.path.exists(binary_path):
        return False, f"Binary not found: {binary_path}"

    # Test 1: Check if binary loader works with --version
    try:
        result = subprocess.run(
            [binary_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 132 or result.returncode == -4:
            return False, "Binary loader crashed with SIGILL - CPU incompatible"

    except subprocess.TimeoutExpired:
        pass  # Timeout is acceptable
    except Exception as e:
        return False, f"Error testing binary loader: {e}"

    # Test 2: Try actual startup (this is where V8/Chromium CPU instructions are used)
    # This is more comprehensive and catches runtime SIGILL errors
    try:
        cmd = [
            binary_path,
            "--no-sandbox",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
            "--use-gl=swiftshader"
        ]

        # Use xvfb-run if requested (for headless environments)
        if use_xvfb:
            cmd = ["xvfb-run", "--auto-servernum"] + cmd

        # Start the process and wait briefly
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait 10 seconds to see if it crashes during initialization
        # pgAdmin4 needs time to load Python backend and initialize
        try:
            returncode = proc.wait(timeout=10)
            # If it exited within 10 seconds, check the return code
            if returncode == 132 or returncode == -4:
                return False, "Binary crashed with SIGILL during initialization - CPU incompatible with Chromium/V8"
            # Exit code 1 might indicate missing dependencies or config issues (acceptable)
            if returncode != 0:
                return True, f"Binary started but exited with code {returncode} (acceptable for pre-test)"
        except subprocess.TimeoutExpired:
            # Still running after 10 seconds = success
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
            return True, "Binary started successfully (ran for 10+ seconds)"

    except Exception as e:
        return False, f"Error testing binary startup: {e}"

    return True, "Binary is loadable"
