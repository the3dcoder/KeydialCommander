#!/bin/bash
# Installation script for Huion Keydial Mini udev rules

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UDEV_RULES_DIR="/etc/udev/rules.d"
BIN_DIR="/usr/local/bin"

# Permission constants
UDEV_PERMS="644"
SCRIPT_PERMS="755"

echo "Installing Huion Keydial Mini udev rules..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (use sudo)"
    exit 1
fi

# Install udev rules (70- carries uaccess tags and must sort before 73-seat-late.rules)
echo "Installing udev rules..."
install -m "$UDEV_PERMS" "$SCRIPT_DIR/udev/70-huion-keydial-mini.rules" "$UDEV_RULES_DIR/"
echo "Udev rules installed with permissions $UDEV_PERMS"

# Remove any stale unbind artifacts from the old BLE architecture
rm -f "$UDEV_RULES_DIR/99-huion-keydial-mini.rules" "$BIN_DIR/unbind-huion.sh" 2>/dev/null || true

# Reload udev rules
echo "Reloading udev rules..."
udevadm control --reload-rules

# Trigger rules for existing devices
echo "Triggering rules for existing devices..."
udevadm trigger --subsystem-match=misc --subsystem-match=input

echo "Installation complete!"
echo ""
echo "Installed: $UDEV_RULES_DIR/70-huion-keydial-mini.rules ($UDEV_PERMS)"
echo ""
echo "The udev rule grants your logged-in session access to the Keydial event"
echo "nodes and to /dev/uinput, so the user-level service can grab the device"
echo "and emit remapped keys without root or 'input' group membership."
echo ""
echo "You may need to reconnect your device for changes to take effect."
