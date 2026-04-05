#!/bin/bash
# One-shot: initialises a 2-shard sharded cluster and restores dumps.
#
# Topology:
#   configRs  — single config server (mongo-config:27019)
#   rs1       — shard 1, 2 members (mongo-rs1-0:27018, mongo-rs1-1:27018)
#   rs2       — shard 2, 2 members (mongo-rs2-0:27018, mongo-rs2-1:27018)
#   mongos    — query router (mongos:27017)
#
# Ordering note: this script does NOT depend on mongos being healthy at
# container start. It initialises configRs first, which allows mongos to
# connect, then polls mongos before adding shards.
set -e

# --- helper: wait for a node to become PRIMARY (default port 27017) ---
wait_primary() {
  local host=$1 port=${2:-27017}
  echo "=== waiting for PRIMARY on ${host}:${port} ==="
  mongosh --host "${host}:${port}" --quiet --eval "
    var ok = false;
    for (var i = 0; i < 30 && !ok; i++) {
      sleep(2000);
      try { ok = db.hello().isWritablePrimary; } catch(e) {}
      print('isWritablePrimary=' + ok);
    }
    if (!ok) { print('ERROR: timed out waiting for PRIMARY'); quit(1); }
    print('Node is PRIMARY');
  "
}

# --- 1. Config server replica set ---
echo "=== mongo-shard-init: initialising config server replica set ==="
STATUS=$(mongosh --host mongo-config:27019 --quiet --eval \
  "try{rs.status().ok}catch(e){0}")
if [ "$STATUS" = "1" ]; then
  echo "configRs already initialised, skipping"
else
  mongosh --host mongo-config:27019 --quiet --eval "
    rs.initiate({
      _id: 'configRs',
      configsvr: true,
      members: [{ _id: 0, host: 'mongo-config:27019' }]
    })
  "
fi
wait_primary mongo-config 27019

# --- 2. Shard 1 replica set ---
echo "=== mongo-shard-init: initialising shard 1 replica set ==="
STATUS=$(mongosh --host mongo-rs1-0:27018 --quiet --eval \
  "try{rs.status().ok}catch(e){0}")
if [ "$STATUS" = "1" ]; then
  echo "rs1 already initialised, skipping"
else
  mongosh --host mongo-rs1-0:27018 --quiet --eval "
    rs.initiate({
      _id: 'rs1',
      members: [
        { _id: 0, host: 'mongo-rs1-0:27018' },
        { _id: 1, host: 'mongo-rs1-1:27018' }
      ]
    })
  "
fi
wait_primary mongo-rs1-0 27018

# --- 3. Shard 2 replica set ---
echo "=== mongo-shard-init: initialising shard 2 replica set ==="
STATUS=$(mongosh --host mongo-rs2-0:27018 --quiet --eval \
  "try{rs.status().ok}catch(e){0}")
if [ "$STATUS" = "1" ]; then
  echo "rs2 already initialised, skipping"
else
  mongosh --host mongo-rs2-0:27018 --quiet --eval "
    rs.initiate({
      _id: 'rs2',
      members: [
        { _id: 0, host: 'mongo-rs2-0:27018' },
        { _id: 1, host: 'mongo-rs2-1:27018' }
      ]
    })
  "
fi
wait_primary mongo-rs2-0 27018

# --- 4. Wait for mongos ---
# configRs is now initialised so mongos will connect on its next retry.
echo "=== mongo-shard-init: waiting for mongos ==="
for i in $(seq 1 40); do
  if mongosh --host mongos:27017 --quiet --eval "db.runCommand('ping').ok" 2>/dev/null | grep -q "^1$"; then
    echo "mongos is ready"
    break
  fi
  echo "mongos not ready yet (${i}/40), retrying in 3s..."
  sleep 3
  if [ "$i" -eq 40 ]; then
    echo "ERROR: timed out waiting for mongos"
    exit 1
  fi
done

# --- 5. Add shards (idempotent) ---
echo "=== mongo-shard-init: adding shards ==="
mongosh --host mongos:27017 --quiet --eval "
  var existing = db.adminCommand({ listShards: 1 }).shards.map(function(s){ return s._id; });

  if (existing.indexOf('rs1') < 0) {
    var res = db.adminCommand({ addShard: 'rs1/mongo-rs1-0:27018,mongo-rs1-1:27018' });
    print('addShard rs1: ' + JSON.stringify(res));
  } else {
    print('rs1 already a shard, skipping');
  }

  if (existing.indexOf('rs2') < 0) {
    var res = db.adminCommand({ addShard: 'rs2/mongo-rs2-0:27018,mongo-rs2-1:27018' });
    print('addShard rs2: ' + JSON.stringify(res));
  } else {
    print('rs2 already a shard, skipping');
  }
"

# --- 6. Restore dumps ---
echo "=== mongo-shard-init: restoring dumps ==="
for f in /dumps/*.gz; do
  [ -f "$f" ] && mongorestore --host mongos:27017 --archive="$f" --gzip --drop
done
echo "=== mongo-shard-init: done ==="
