#!/bin/bash

Xvfb $DISPLAY -ac +iglx -screen 0 $XVFB_WHD &

PWD=$(date +%s | sha256sum | base64 | head -c 12)

x11vnc -display $DISPLAY -listen 0.0.0.0 -shared \
    -forever -passwd $PWD > /dev/null 2>&1 &

echo "Container IP address:"

ip a show eth0|grep 'inet'

echo

echo "Running healthcheck http service"

hcdir=$(mktemp -d)

nohup python3 -m http.server -d "${hcdir}" 8000 &

cat <<EOF
=================================================
=================================================

YOUR VNC PASSWORD IS: $PWD

=================================================
=================================================
EOF

sleep 2

fluxbox > /dev/null 2>&1 &
sleep 1

exec "$@"
