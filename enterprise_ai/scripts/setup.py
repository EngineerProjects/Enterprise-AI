#!/usr/bin/env python
"""
Enterprise AI Setup Script

Handles post-installation setup, including browser automation dependencies.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("enterprise-ai-setup")


def main() -> None:
    """Main entry point for setup script."""
    logger.info("=== Enterprise AI Setup ===")

    # Check if running with sufficient privileges for Linux
    if platform.system() == "Linux" and os.geteuid() == 0:
        logger.info("Running with root privileges - can install system dependencies")
        install_system_dependencies()
    elif platform.system() == "Linux":
        logger.warning("Not running with root privileges - skipping system dependency installation")
        logger.info("To install system dependencies, run:")
        logger.info(
            "  sudo apt-get install -y libevent-2.1-7 libgstreamer-plugins-base1.0-0 libavif-dev"
        )

    # Install Playwright browsers
    install_browsers()

    logger.info("=== Enterprise AI Setup Complete ===")


def install_system_dependencies() -> None:
    """Install system dependencies for browser automation."""
    logger.info("Installing system dependencies for browser automation...")

    try:
        if platform.system() == "Linux":
            # Detect distribution
            if os.path.exists("/etc/debian_version"):
                # Debian/Ubuntu
                logger.info("Detected Debian/Ubuntu system")
                subprocess.run(["apt-get", "update"], check=True)
                subprocess.run(
                    [
                        "apt-get",
                        "install",
                        "-y",
                        "libevent-2.1-7",
                        "libgstreamer-plugins-base1.0-0",
                        "libavif-dev",
                        "libnss3",
                        "libnspr4",
                        "libatk1.0-0",
                        "libatk-bridge2.0-0",
                        "libcups2",
                        "libdrm2",
                        "libdbus-1-3",
                        "libxkbcommon0",
                        "libx11-6",
                        "libxcomposite1",
                        "libxdamage1",
                        "libxext6",
                        "libxfixes3",
                        "libxrandr2",
                        "libgbm1",
                        "libpango-1.0-0",
                        "libcairo2",
                        "libasound2",
                    ],
                    check=True,
                )
            elif os.path.exists("/etc/redhat-release"):
                # RHEL/CentOS/Fedora
                logger.info("Detected Red Hat/CentOS/Fedora system")
                subprocess.run(
                    ["dnf", "install", "-y", "libevent", "gstreamer1-plugins-base", "libavif"],
                    check=True,
                )
            else:
                logger.warning("Unsupported Linux distribution")
                logger.info("Please install browser dependencies manually")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error installing system dependencies: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during system dependency installation: {e}")


def install_browsers() -> None:
    """Install browser binaries for automation."""
    logger.info("Installing browser automation binaries...")
    try:
        # Run the playwright install command
        subprocess.run([sys.executable, "-m", "playwright", "install"], check=True)
        logger.info("Browser installation successful!")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during browser installation: {e}")
        logger.info("You may need to run manually:")
        logger.info("  python -m playwright install")
    except Exception as e:
        logger.error(f"Unexpected error during browser installation: {e}")
        logger.info("You may need to run manually:")
        logger.info("  python -m playwright install")


if __name__ == "__main__":
    main()
