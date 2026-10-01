# Light-Router run visualizer

Thin static visualizer for passage runs in `runs/`: one animated page per
experiment showing every budget's boat on the evolving truth wind field.

## What it shows

- Boats (one per bandwidth budget) moving 6 h frame by 6 h frame, with the
  trace each one has sailed so far, colored by budget.
- Hover a boat (or watch the side table) for heading, speed over ground,
  true wind speed and true wind angle at the current time.
- The truth wind field (from the run's data pack), evolving with the
  timeline, drawn as arrows colored by speed.

## Build the site

    .venv/bin/python visualizer/build.py

Writes `visualizer/dist/`: an `index.html` experiment list plus one page per
run. Wind frames are subsampled to 6 h / every 2nd grid point; runs whose
data pack is missing simply render without the wind layer.

## Serve it

Any static file server works (the pages are self-contained apart from the
map tiles). On pascal there is a docker wrapper:

    docker compose -f visualizer/docker-compose.yml up -d --build

which serves `dist/` on the shared `ingress` network as `lightrouter-viz`,
proxied by the gateway at `light-router.pascal-internet.duckdns.org` behind
authentik (gateway conf: `light-router.conf` in the gateway's nginx conf.d).

## Keeping it fresh

The site is static, so new runs under `runs/` only appear after a rebuild.
On pascal a systemd timer (`lightrouter-viz-build.timer`, every 15 min,
niced with idle I/O per the server rules) re-runs `build.py` as `hke`;
the container bind-mounts `dist/`, so no restart is needed. Manually:
`make viz-build`.
