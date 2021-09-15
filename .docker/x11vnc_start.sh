#!/bin/bash

echo "Starting X virtual framebuffer using: Xvfb $DISPLAY -ac -screen 0 $XVFB_WHD -nolisten tcp"
Xvfb $DISPLAY -ac -screen 0 $XVFB_WHD -nolisten tcp &
sleep 2

x11vnc -display $DISPLAY -listen 0.0.0.0 -shared \
    -forever -passwd ${X11VNC_PASSWORD:-password} &

fluxbox &
sleep 1

exec "$@"
