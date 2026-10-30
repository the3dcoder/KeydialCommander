#!/bin/sh
# Optional build prerequisites. Runtime dependencies are resolved by apt install ./file.deb.
set -eu
sudo apt-get update
sudo apt-get install python3-venv dpkg nodejs npm
