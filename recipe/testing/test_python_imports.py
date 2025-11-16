#!/usr/bin/env python
"""Test if Python backend dependencies can import without SIGILL."""
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def test_import(module_name):
    """Test importing a module."""
    try:
        logging.info(f"Testing import: {module_name}")
        __import__(module_name)
        logging.info(f"✓ {module_name} imported successfully")
        return True
    except Exception as e:
        logging.error(f"✗ {module_name} failed to import: {e}")
        return False

def main():
    """Test critical pgadmin4-python dependencies that might have native code."""
    critical_modules = [
        "bcrypt",
        "cryptography",
        "psycopg",
        "psycopg_c",
        "psutil",
    ]

    logging.info("Testing Python backend dependencies for CPU compatibility...")
    logging.info(f"Python version: {sys.version}")

    all_passed = True
    for module in critical_modules:
        if not test_import(module):
            all_passed = False

    if all_passed:
        logging.info("All Python dependencies imported successfully")
        sys.exit(0)
    else:
        logging.error("Some Python dependencies failed to import")
        sys.exit(1)

if __name__ == "__main__":
    main()
