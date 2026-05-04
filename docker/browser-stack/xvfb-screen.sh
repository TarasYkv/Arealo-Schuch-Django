#!/bin/bash
# Helper: macht einen Screenshot vom Xvfb-Display und gibt PNG auf stdout aus.
set -euo pipefail
export DISPLAY=:99
xwd -root | convert xwd:- png:-
