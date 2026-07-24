#!/bin/bash

set -e

echo "Installing all required dependencies"

python3 -m pip install -r requirements.txt

echo "Finished run - source .venv/bin/activate"