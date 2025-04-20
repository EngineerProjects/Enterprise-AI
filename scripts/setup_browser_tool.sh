#!/bin/bash
# setup_browser_tools.sh
# Script to set up browser automation dependencies for Enterprise AI

set -e  # Exit on error
echo "=== Enterprise AI - Browser Tools Setup ==="

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    echo "Detected OS: $OS"
else
    OS="Unknown"
    echo "Warning: Could not detect OS. Assuming Debian/Ubuntu-based."
fi

# Install system dependencies
echo -e "\n=== Installing system dependencies ==="
if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
    echo "Installing dependencies for Ubuntu/Debian..."
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends \
        libevent-2.1-7 \
        libgstreamer-plugins-base1.0-0 \
        libavif-dev \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libdbus-1-3 \
        libxkbcommon0 \
        libx11-6 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2
elif [[ "$OS" == *"Fedora"* ]] || [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
    echo "Installing dependencies for Fedora/RHEL/CentOS..."
    sudo dnf install -y \
        libevent \
        gstreamer1-plugins-base \
        libavif \
        nss \
        nspr \
        atk \
        at-spi2-atk \
        cups-libs \
        libdrm \
        dbus-libs \
        libxkbcommon \
        libX11 \
        libXcomposite \
        libXdamage \
        libXext \
        libXfixes \
        libXrandr \
        mesa-libgbm \
        pango \
        cairo \
        alsa-lib
else
    echo "Warning: Unsupported OS. Please install browser dependencies manually."
    echo "Required libraries: libevent-2.1-7 libgstreamer-plugins-base1.0-0 libavif-dev"
    echo "And standard browser dependencies for your OS."
fi

# Install Playwright browsers
echo -e "\n=== Installing Playwright browsers ==="
python -m playwright install

# Verify installation
echo -e "\n=== Verifying installation ==="
if python -m playwright --version; then
    echo "Playwright installation verified!"
else
    echo "Warning: Playwright installation verification failed."
fi

echo -e "\n=== Browser tools setup complete! ==="