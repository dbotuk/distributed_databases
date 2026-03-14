# MongoDB Replica Set (P-S-S): setup and failover check

## 1. Topology

Replica set name: `rs0`

Members:
- `mongo1:27017` - preferred primary (higher priority)
- `mongo2:27017` - secondary
- `mongo3:27017` - secondary

Host ports:
- `localhost:27017 -> mongo1:27017`
- `localhost:27018 -> mongo2:27017`
- `localhost:27019 -> mongo3:27017`

## 2. Start cluster

```bash
docker network create counter_network   # once
cd mongo-with-replication
docker compose up -d
```

`mongo-setup` service initializes the replica set automatically via inline `mongosh --eval` command in `docker-compose.yml`.

## 3. Validate replica set

```bash
# Show state of all nodes
docker exec -it mongo1 mongosh --eval "rs.status().members.map(m => ({name: m.name, state: m.stateStr}))"

# Show current primary
docker exec -it mongo1 mongosh --quiet --eval "db.hello().primary"
```

Expected: one `PRIMARY`, two `SECONDARY`.

## 4. Connect client with failover support

Use replica set URI (recommended):

```bash
export MONGO_URI="mongodb://localhost:27017,localhost:27018,localhost:27019/counter_db?replicaSet=rs0"
```

Then run tester:

```bash
cd counters
python productivity_tester.py --counter-type mongodb --n-clients 10 --n-calls-per-client 1000
```

## 5. Fault-tolerance check (failover)

```bash
# A) Find current primary
docker exec -it mongo1 mongosh --quiet --eval "db.hello().primary"

# B) Simulate failure: stop primary (example)
docker stop mongo1

# C) Wait ~10-20 sec and confirm new primary
# (at least one should print 'true')
docker exec -it mongo2 mongosh --quiet --eval "db.hello().isWritablePrimary"
docker exec -it mongo3 mongosh --quiet --eval "db.hello().isWritablePrimary"

# D) Start old primary back
docker start mongo1

# E) Confirm node has rejoined
docker exec -it mongo1 mongosh --eval "rs.status().members.map(m => ({name: m.name, state: m.stateStr}))"
```

Result criteria:
- cluster keeps majority (2/3 nodes);
- new primary is elected automatically;
- writes continue when client uses `MONGO_URI` with all members + `replicaSet=rs0`.

## 6. Write concern `w:3` with one stopped node

Manual experiment:

```bash
cd mongo-with-replication
docker exec -it mongo1 mongosh --quiet --eval "db.hello().primary"
```

1. Check the current replica set state:

```bash
docker exec -it mongo1 mongosh --eval "rs.status().members.map(m => ({name: m.name, state: m.stateStr}))"
```

Expected: one `PRIMARY`, two `SECONDARY`.

2. Stop one `SECONDARY` node. Example:

```bash
docker stop mongo3
```

3. In the first terminal, start a write with `writeConcern: { w: 3, wtimeout: 0 }`:

```bash
docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.wc3_manual.drop();
db.wc3_manual.insertOne(
  {
    _id: "manual-test",
    startedAt: new Date(),
    note: "w=3, wtimeout=0"
  },
  {
    writeConcern: { w: 3, wtimeout: 0 }
  }
)
'
```

This command should block, because confirmation from all 3 replica set members is required, while one node is offline.

4. In the second terminal, start the stopped node again:

```bash
docker start mongo3
```

5. Wait until the write in the first terminal completes, then verify the document:

```bash
docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.wc3_manual.find().pretty()
'
```

Expected result:
- while one node is stopped, the write blocks;
- after the node returns, the write completes successfully;
- the inserted document appears in the collection.

## 7. Write concern `w:3` with finite timeout

Manual experiment:

1. Check that replica set is healthy:

```bash
docker exec -it mongo1 mongosh --eval "rs.status().members.map(m => ({name: m.name, state: m.stateStr}))"
```

2. Stop one `SECONDARY` node. Example:

```bash
docker stop mongo3
```

3. In the first terminal, execute a write with `writeConcern: { w: 3, wtimeout: 5000 }`:

```bash
docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.wc3_timeout.drop();
try {
  const result = db.wc3_timeout.insertOne(
    {
      _id: "timeout-test",
      startedAt: new Date(),
      note: "w=3, wtimeout=5000"
    },
    {
      writeConcern: { w: 3, wtimeout: 5000 }
    }
  );
  printjson(result);
} catch (e) {
  print("Write finished with error:");
  printjson(e);
}
'
```

Expected: after about 5 seconds, the shell returns a `writeConcernError` or timeout-related error, because acknowledgement from all 3 members was not received in time.

4. Check whether the document was still written on the available majority:

```bash
docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.wc3_timeout.find({ _id: "timeout-test" }).pretty()
'
```

5. Check whether the same document is readable with `readConcern: "majority"`:

```bash
docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
const result = db.runCommand({
  find: "wc3_timeout",
  filter: { _id: "timeout-test" },
  readConcern: { level: "majority" }
});
printjson(result);
'
```

Interpretation:
- `w:3` requires acknowledgement from all 3 replica set members;
- with one node stopped, this condition cannot be satisfied, so the client gets a timeout after `wtimeout`;
- in a 3-node replica set, `majority` is 2 nodes, so the write may still be replicated to the primary and one secondary;
- if that happened, the document will remain stored and will be visible through `readConcern: "majority"` despite the write concern timeout.

6. Start the stopped node again:

```bash
docker start mongo3
```

## 8. Replica Set Elections and catch-up replication

Manual experiment:

1. Check the current replica set state and identify the current `PRIMARY`:

```bash
docker exec -it mongo1 mongosh --eval "rs.status().members.map(m => ({name: m.name, state: m.stateStr}))"
docker exec -it mongo1 mongosh --quiet --eval "db.hello().primary"
```

2. Stop the current `PRIMARY`.

Example: if the previous command returned `mongo1:27017`:

```bash
docker stop mongo1
```

3. Wait about 10-20 seconds and verify that a new `PRIMARY` was elected:

```bash
docker exec -it mongo2 mongosh --quiet --eval "db.hello().isWritablePrimary"
docker exec -it mongo3 mongosh --quiet --eval "db.hello().isWritablePrimary"
```

At least one of these two commands should return `true`.

4. Determine the new `PRIMARY`:

```bash
docker exec -it mongo2 mongosh --quiet --eval "db.hello().primary"
```

5. Write new data to the new `PRIMARY` while the old `PRIMARY` is offline.

If the new `PRIMARY` is `mongo2`, run:

```bash
docker exec -it mongo2 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.election_demo.insertOne({
  _id: "written-during-old-primary-downtime",
  createdAt: new Date(),
  note: "document written after primary election"
})
'
```

If the new `PRIMARY` is `mongo3`, run the same command in `mongo3`.

6. Verify that the document exists on the current `PRIMARY`:

```bash
docker exec -it mongo2 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.election_demo.find({ _id: "written-during-old-primary-downtime" }).pretty()
'
```

If the new `PRIMARY` is `mongo3`, run the same command in `mongo3`.

7. Start the old `PRIMARY` again.

Example:

```bash
docker start mongo1
```

8. Wait a few seconds and verify that the old `PRIMARY` rejoined as `SECONDARY`:

```bash
docker exec -it mongo1 mongosh --eval "rs.status().members.map(m => ({name: m.name, state: m.stateStr}))"
```

Expected: the restarted node is no longer `PRIMARY`; it should rejoin as `SECONDARY`.

9. Check that the restarted old `PRIMARY` received the document that was created during its downtime:

```bash
docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.election_demo.find({ _id: "written-during-old-primary-downtime" }).pretty()
'
```

Expected result:
- after stopping the old `PRIMARY`, the replica set elects a new `PRIMARY`;
- writes continue on the new `PRIMARY`;
- when the old `PRIMARY` comes back, it does not automatically regain leadership;
- instead, it catches up by replicating the new data that appeared while it was offline.

## 9. Rollback of a `w:1` write after primary isolation

Goal:
- isolate the current `PRIMARY` from both `SECONDARY` nodes;
- write a value to the old `PRIMARY` with `writeConcern: { w: 1 }` during the short period before it notices the loss of quorum;
- verify that the value is visible only with `readConcern: "local"`;
- elect a new `PRIMARY` on the other two nodes;
- reconnect the old `PRIMARY` and verify that the unreplicated value disappears.

Manual experiment:

1. Check the current topology and identify the current `PRIMARY`:

```bash
docker exec -it mongo1 mongosh --eval "rs.status().members.map(m => ({name: m.name, state: m.stateStr}))"
docker exec -it mongo1 mongosh --quiet --eval "db.hello().primary"
```

For the commands below, assume:
- old `PRIMARY` = `mongo1`
- secondaries = `mongo2`, `mongo3`

If your `PRIMARY` is different, substitute container names accordingly.

2. Stop both `SECONDARY` nodes almost simultaneously:

```bash
docker stop mongo2 mongo3
```

3. Immediately, within a few seconds, write a document to the old `PRIMARY` with `w:1`:

```bash
docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.rollback_demo.deleteMany({ _id: "rollback-test" });
db.rollback_demo.insertOne(
  {
    _id: "rollback-test",
    createdAt: new Date(),
    note: "written on isolated old primary with w=1"
  },
  {
    writeConcern: { w: 1 }
  }
)
'
```

Expected: the write succeeds, because the old `PRIMARY` has not yet stepped down.

4. Verify that the document is readable with `readConcern: "local"`:

```bash
docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
printjson(db.runCommand({
  find: "rollback_demo",
  filter: { _id: "rollback-test" },
  readConcern: { level: "local" }
}));
'
```

Expected: the document is returned.

5. Try to read the same document with `readConcern: "majority"`:

```bash
docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
printjson(db.runCommand({
  find: "rollback_demo",
  filter: { _id: "rollback-test" },
  readConcern: { level: "majority" }
}));
'
```

Expected: the document is not returned in the result, because it was not majority-committed.

6. Try to read the same document with `readConcern: "linearizable"`:

```bash
docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
printjson(db.runCommand({
  find: "rollback_demo",
  filter: { _id: "rollback-test" },
  readConcern: { level: "linearizable" }
}));
'
```

Expected: the command should fail or time out, because `linearizable` reads require confirmation from a majority, which is unavailable.

7. Stop the old `PRIMARY` before reconnecting the other two nodes:

```bash
docker stop mongo1
```

8. Start the two former `SECONDARY` nodes:

```bash
docker start mongo2 mongo3
```

9. Wait about 10-20 seconds and verify that these two nodes elected a new `PRIMARY`:

```bash
docker exec -it mongo2 mongosh --quiet --eval "db.hello().primary"
docker exec -it mongo2 mongosh --eval "rs.status().members.map(m => ({name: m.name, state: m.stateStr}))"
```

Expected: either `mongo2` or `mongo3` becomes the new `PRIMARY`.

10. Verify that the rolled-back document does not exist on the new `PRIMARY`:

```bash
docker exec -it mongo2 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.rollback_demo.find({ _id: "rollback-test" }).pretty()
'
```

If `mongo2` is not the new `PRIMARY`, run the same command in `mongo3`.

Expected: no document is returned.

11. Start the old `PRIMARY` again:

```bash
docker start mongo1
```

12. Wait a few seconds and verify that it rejoined the replica set:

```bash
docker exec -it mongo1 mongosh --eval "rs.status().members.map(m => ({name: m.name, state: m.stateStr}))"
```

Expected: `mongo1` rejoins as `SECONDARY` first and synchronizes with the current cluster state.

13. Check the old `PRIMARY` for the document that was written during isolation:

```bash
docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.rollback_demo.find({ _id: "rollback-test" }).pretty()
'
```

Expected result:
- the document is gone;
- MongoDB rolled back the `w:1` write because it existed only on the isolated old `PRIMARY` and was never replicated to a majority.

Interpretation:
- `w:1` only confirms that the old `PRIMARY` wrote the document locally;
- while isolated from the replica set majority, that write is not durable from the cluster perspective;
- after the other two nodes form a new majority and elect a new `PRIMARY`, the isolated write becomes divergent history;
- when the old `PRIMARY` rejoins, MongoDB rolls back that history and syncs it with the current majority state.

## 10. Simulate eventual consistency with a delayed replica member

According to the official MongoDB documentation, to configure a delayed secondary member you should set:
- `priority = 0`
- `hidden = true`
- `secondaryDelaySecs = <delay in seconds>`

Source: [MongoDB Docs - Configure a Delayed Self-Managed Replica Set Member](https://www.mongodb.com/docs/manual/tutorial/configure-a-delayed-replica-set-member/)

Manual experiment:

1. Check the current replica set configuration:

```bash
docker exec -it mongo1 mongosh --eval "rs.conf()"
docker exec -it mongo1 mongosh --eval "rs.status().members.map(m => ({name: m.name, state: m.stateStr}))"
```

2. Choose one `SECONDARY` to become delayed.

Example below uses `mongo3`.

3. Reconfigure the replica set on the current `PRIMARY` to make `mongo3` delayed by 30 seconds:

```bash
docker exec -it mongo1 mongosh --eval '
cfg = rs.conf();
cfg.members[2].priority = 0;
cfg.members[2].hidden = true;
cfg.members[2].secondaryDelaySecs = 30;
rs.reconfig(cfg);
'
```

Important:
- `members[2]` is the array index in `rs.conf()`, not necessarily the same thing as member `_id`;
- `rs.reconfig()` may trigger a primary stepdown and brief reconnection window.

4. Wait 10-20 seconds, then verify the updated configuration:

```bash
docker exec -it mongo1 mongosh --eval '
cfg = rs.conf();
printjson(cfg.members.map(m => ({
  host: m.host,
  priority: m.priority,
  hidden: m.hidden,
  secondaryDelaySecs: m.secondaryDelaySecs
})));
'
```

Expected for the delayed member:
- `priority: 0`
- `hidden: true`
- `secondaryDelaySecs: 30`

5. Insert a test document on the current `PRIMARY`:

```bash
docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.eventual_demo.insertOne({
  _id: "delay-test",
  createdAt: new Date(),
  note: "document for delayed replication demo"
})
'
```

6. Immediately read the document from the current `PRIMARY`:

```bash
docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.eventual_demo.find({ _id: "delay-test" }).pretty()
'
```

Expected: the document is visible immediately on the primary.

7. Immediately try to read the same document from the delayed node:

```bash
docker exec -it mongo3 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.getMongo().setReadPref("secondary");
db.eventual_demo.find({ _id: "delay-test" }).pretty()
'
```

Expected: right after the write, the document is not yet visible on `mongo3`.

8. Wait longer than the configured delay, for example 35 seconds:

```bash
sleep 35
```

9. Read the same document again from the delayed node:

```bash
docker exec -it mongo3 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.getMongo().setReadPref("secondary");
db.eventual_demo.find({ _id: "delay-test" }).pretty()
'
```

Expected: after the delay interval passes, the document becomes visible on `mongo3`.

10. Optional: restore the member to normal replication mode after the experiment:

```bash
docker exec -it mongo1 mongosh --eval '
cfg = rs.conf();
cfg.members[2].priority = 1;
cfg.members[2].hidden = false;
cfg.members[2].secondaryDelaySecs = 0;
rs.reconfig(cfg);
'
```

Interpretation:
- the primary accepts and stores writes immediately;
- the delayed secondary intentionally applies oplog entries later;
- during the delay window, different nodes observe different states;
- this demonstrates eventual consistency: the delayed node converges to the current state after some time.

## 11. Linearizable read with only primary and delayed secondary

Goal:
- leave only the `PRIMARY` and the delayed `SECONDARY` online;
- stop the other secondary;
- write several values;
- perform a read with `readConcern: { level: "linearizable" }`;
- observe that the operation is delayed until the data is majority-committed on the delayed secondary.

Important:
- For a reliable demonstration, use `writeConcern: { w: "majority" }` for the writes.
- According to MongoDB documentation, delayed voting members can acknowledge majority writes, but no earlier than `secondaryDelaySecs`.
- `linearizable` reads can wait for writes to propagate to a majority before returning.

Sources:
- [Read Concern "linearizable" - MongoDB Docs](https://www.mongodb.com/docs/manual/reference/read-concern-linearizable/)
- [Write Concern - delayed secondaries and majority acknowledgement - MongoDB Docs](https://www.mongodb.com/docs/manual/reference/write-concern/)

Manual experiment:

1. Check the current replica set state:

```bash
docker exec -it mongo1 mongosh --eval "rs.status().members.map(m => ({name: m.name, state: m.stateStr}))"
docker exec -it mongo1 mongosh --quiet --eval "db.hello().primary"
```

Assume:
- `mongo1` = `PRIMARY`
- `mongo3` = delayed `SECONDARY`
- `mongo2` = normal `SECONDARY`

If your topology differs, substitute container names accordingly.

2. Stop the normal secondary, leaving only the `PRIMARY` and delayed `SECONDARY` online:

```bash
docker stop mongo2
```

3. Verify that only `PRIMARY` and delayed member remain reachable:

```bash
docker exec -it mongo1 mongosh --eval "rs.status().members.map(m => ({name: m.name, state: m.stateStr}))"
```

Expected:
- `mongo1` is still `PRIMARY`
- `mongo3` is `SECONDARY`
- `mongo2` is not reachable

4. Write several documents with `writeConcern: { w: "majority" }` and measure the time:

```bash
time docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.linearizable_demo.deleteMany({});
for (let i = 1; i <= 3; i++) {
  db.linearizable_demo.insertOne(
    {
      _id: i,
      createdAt: new Date(),
      note: "majority write with delayed secondary"
    },
    {
      writeConcern: { w: "majority" }
    }
  );
}
'
```

Expected:
- the writes succeed;
- the command takes about the configured delay time for each majority-acknowledged write, because the delayed member is needed to form the majority.

5. Immediately perform a `linearizable` read from the primary and measure the time:

```bash
time docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
printjson(db.runCommand({
  find: "linearizable_demo",
  filter: {},
  readConcern: { level: "linearizable" }
}));
'
```

Expected:
- the read returns the inserted documents;
- if there are still writes waiting to become majority-committed, the read can block until the delayed secondary catches up enough for majority visibility.

6. Compare with a `local` read:

```bash
time docker exec -it mongo1 mongosh --eval '
db = db.getSiblingDB("counter_db");
printjson(db.runCommand({
  find: "linearizable_demo",
  filter: {},
  readConcern: { level: "local" }
}));
'
```

Expected:
- `local` returns immediately from the primary's local state;
- `linearizable` can be noticeably slower because it waits for majority semantics.

7. Optional direct verification on the delayed secondary:

```bash
docker exec -it mongo3 mongosh --eval '
db = db.getSiblingDB("counter_db");
db.getMongo().setReadPref("secondary");
db.linearizable_demo.find().pretty()
'
```

8. Restore the normal secondary:

```bash
docker start mongo2
```

Interpretation:
- with one normal secondary offline, the delayed secondary becomes necessary for majority acknowledgement in the 3-node replica set;
- majority writes therefore complete only after the delayed secondary applies them;
- `linearizable` read on the primary respects majority visibility and may wait;
- `local` read does not require that guarantee and therefore returns faster.

## 12. Shutdown

```bash
cd mongo-with-replication
docker compose down
```

To remove volumes too:

```bash
docker compose down -v
```
