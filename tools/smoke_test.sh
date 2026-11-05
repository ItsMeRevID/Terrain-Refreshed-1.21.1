#!/usr/bin/env bash
# End-to-end smoke test for the Terrain Refreshed mod.
#
# Boots the dev dedicated server, waits for the world to finish generating, then
# drives it over RCON: force-loads the spawn area, locates every new biome, checks
# which biome the multi-noise source picks at a few positions, places the custom
# fancy tree and the stream feature, verifies the blocks they produced, and measures
# the silhouette of every tree species against the shape its form is named after.
#
# Usage: tools/smoke_test.sh <log-name> [level-name] [locate-limit] [density-sample]
#
# locate-limit caps how many biomes the sweep looks for; 0 (the default) sweeps
# all of them. Each `locate biome` is a fresh half-million point spiral search, so
# a full sweep of the 100 new biomes takes tens of minutes.
#
# density-sample, when given, additionally spreads that many biomes over the set
# and searches for each of them from six origins, which shows how common a biome
# really is instead of only whether one search from spawn happens to reach it.

set -u

cd "$(dirname "$0")/.."

LOG_NAME="${1:-smoke}"
LEVEL_NAME="${2:-terrainrefreshed-1211-smoke}"

LOG="run/${LOG_NAME}.log"
RCON_HOST="127.0.0.1"
RCON_PORT=25576
RCON_PASSWORD="terrainrefreshed"
LOCATE_LIMIT="${3:-0}"
DENSITY_SAMPLE="${4:-0}"
SWEEP=0

rm -f "$LOG"

python - "$LEVEL_NAME" <<'PY'
import re
import sys

level = sys.argv[1]
path = "run/server.properties"
text = open(path, encoding="utf-8").read()
text = re.sub(r"(?m)^level-name=.*$", "level-name=%s" % level, text)
# `/locate biome` samples up to half a million climate points before it gives up,
# which is a long single tick; the watchdog would kill the server mid-sweep.
text = re.sub(r"(?m)^max-tick-time=.*$", "max-tick-time=-1", text)
open(path, "w", encoding="utf-8", newline="\n").write(text)
PY

JAVA_HOME="C:/Program Files/Eclipse Adoptium/jdk-21.0.12.101-hotspot" \
	./gradlew runServer --console=plain > "$LOG" 2>&1 &
SERVER_PID=$!

READY=0
for _ in $(seq 1 120); do
	if grep -q 'Done (' "$LOG" 2>/dev/null; then
		READY=1
		break
	fi
	if ! kill -0 "$SERVER_PID" 2>/dev/null; then
		break
	fi
	sleep 5
done

if [ "$READY" -ne 1 ]; then
	echo "server never became ready; see $LOG"
else
	echo "== locate sweep =="
	python tools/smoke_locate.py "$RCON_HOST" "$RCON_PORT" "$RCON_PASSWORD" "$LOCATE_LIMIT" || SWEEP=$?

	if [ "$DENSITY_SAMPLE" -gt 0 ]; then
		echo "== density probe =="
		python tools/smoke_density.py "$RCON_HOST" "$RCON_PORT" "$RCON_PASSWORD" "$DENSITY_SAMPLE" || SWEEP=$?
	fi

	# The chunks have to be fully loaded before `place feature` will accept them,
	# so the forceload cannot share a batch with the placements that depend on it.
	echo "== force load =="
	python tools/rcon.py "$RCON_HOST" "$RCON_PORT" "$RCON_PASSWORD" \
		"forceload add -64 -64 64 64" || true
	sleep 20

	echo "== feature placement =="
	python tools/rcon.py "$RCON_HOST" "$RCON_PORT" "$RCON_PASSWORD" \
		"place feature terrainrefreshed:fancy_oak 0 80 0" \
		"place feature terrainrefreshed:fancy_willow 16 80 16" \
		"place feature terrainrefreshed:stream 32 80 32" || true
	sleep 15

	echo "== tree silhouettes =="
	python tools/smoke_trees.py "$RCON_HOST" "$RCON_PORT" "$RCON_PASSWORD" || SWEEP=1

	echo "== biome and block probes =="
	python tools/smoke_probe.py "$RCON_HOST" "$RCON_PORT" "$RCON_PASSWORD" || true

	python tools/rcon.py "$RCON_HOST" "$RCON_PORT" "$RCON_PASSWORD" "stop" || true
fi

wait "$SERVER_PID" 2>/dev/null
echo "server exited, log: $LOG"
exit "$SWEEP"
