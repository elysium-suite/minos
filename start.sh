#!/bin/bash

# Script to run the scripts with the development Flask server
# or... not recommended, but works for systems without systemd

cd engine
python3 ./engine.py &
python3 ./wsgi.py
echo "Press enter or <C-c> to stop scoring."
read
pkill python3
