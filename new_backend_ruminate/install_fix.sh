#!/bin/bash

echo "Installing dependencies with PyYAML fix..."

# First, try to install PyYAML separately with no build isolation
pip install --no-build-isolation pyyaml==6.0.1

# Then install the rest
pip install -r requirements.txt

echo "Installation complete!"