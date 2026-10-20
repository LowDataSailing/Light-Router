#!/bin/sh
# Oracle runner: drive the pinned OpenCPN headless build in its docker
# image, forwarding the WR_HEADLESS_* contract (issue #22).
#
# The adapter executes this script as the "binary"; the scenario, wind
# (GRIB2) and result files live in the caller's workdir, which is mounted
# into the container at the same path so the scenario's absolute paths
# stay valid. Point the harness at it with --opencpn-binary or
# $LR_ORACLE_OPENCPN_BINARY.
#
# OpenCPN runs against a bare in-container Xvfb (no xauth cookie:
# xvfb-run's cookie setup makes the app exit silently before init) and
# exits by itself once the headless scenario completes.
#
#   LR_ORACLE_IMAGE=lightrouter-opencpn-oracle:ae09f41  (default)

set -eu

IMAGE="${LR_ORACLE_IMAGE:-lightrouter-opencpn-oracle:ae09f41}"

scenario="${WR_HEADLESS_SCENARIO:?WR_HEADLESS_SCENARIO not set}"
output="${WR_HEADLESS_OUTPUT:?WR_HEADLESS_OUTPUT not set}"
wind="${WR_HEADLESS_GRIB_FILE:?WR_HEADLESS_GRIB_FILE not set}"

workdir=$(dirname "$scenario")

exec docker run --rm \
    -v "$workdir:$workdir" \
    -e HOME=/home/ubuntu \
    -e DISPLAY=:99 \
    -e WR_HEADLESS_SCENARIO="$scenario" \
    -e WR_HEADLESS_GRIB_FILE="$wind" \
    -e WR_HEADLESS_OUTPUT="$output" \
    -e OPENCPN_PLUGIN_DIRS="/opt/OpenCPN/build/plugins/weather_routing_pi:/opt/OpenCPN/build/plugins/grib_pi:/usr/lib/opencpn" \
    ${WR_HEADLESS_TIMEOUT_MS:+-e WR_HEADLESS_TIMEOUT_MS="$WR_HEADLESS_TIMEOUT_MS"} \
    --entrypoint /bin/bash \
    "$IMAGE" \
    -c 'Xvfb :99 -screen 0 1280x1024x24 -nolisten tcp &
        sleep 1
        cd /opt/OpenCPN
        exec /opt/OpenCPN/build/opencpn'
