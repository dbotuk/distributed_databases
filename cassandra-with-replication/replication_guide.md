# Cassandra 3-node cluster with replication

## Topology

- `cassandra-node1` - seed node
- `cassandra-node2` - peer node
- `cassandra-node3` - peer node
- Datacenter: `datacenter1`
- Rack: `rack1`
- Network: `cassandra_replication_net`

The cluster uses the official `cassandra:4.1` image. Nodes should be started sequentially so that each new node joins an already stable ring.

## Start cluster

```bash
cd cassandra-with-replication
docker compose down -v --remove-orphans
```

### 1. Start the seed node

```bash
docker compose up -d cassandra-node1
docker exec cassandra-node1 nodetool status
```

Wait until `cassandra-node1` appears as `UN`.

### 2. Start the second node

```bash
docker compose up -d cassandra-node2
docker exec cassandra-node2 nodetool status
```

Wait until `cassandra-node2` appears as `UN`.

### 3. Start the third node

```bash
docker compose up -d cassandra-node3
docker exec cassandra-node3 nodetool status
```

Wait until `cassandra-node3` appears as `UN`.

If `nodetool status` is called too early, Cassandra may still be initializing. In that case, wait 10-20 seconds and run the command again.

## Manual verification

```bash
docker exec cassandra-node1 nodetool status
```

Expected result:

- all 3 nodes are listed in `datacenter1`;
- each node has status `UN`.

Example target shape:

```text
Datacenter: datacenter1
=======================
Status=Up/Down
|/ State=Normal/Leaving/Joining/Moving
--  Address     Load       Tokens  Owns (effective)  Host ID   Rack
UN  <node1-ip>  ...
UN  <node2-ip>  ...
UN  <node3-ip>  ...
```

On my verification run, the final status was:

```text
Datacenter: datacenter1
=======================
Status=Up/Down
|/ State=Normal/Leaving/Joining/Moving
--  Address     Load        Tokens  Owns (effective)  Host ID                               Rack
UN  172.22.0.2  109.39 KiB  16      64.7%             3d4e5edc-f90e-4744-8f64-747176099bf4  rack1
UN  172.22.0.3  75.21 KiB   16      59.3%             087993e7-a5d1-4be1-98b7-7b96ab6b6e9c  rack1
UN  172.22.0.4  104.27 KiB  16      76.0%             4cb46bd8-4764-4a71-bff6-c280aac56e5b  rack1
```

## Stop cluster

```bash
cd cassandra-with-replication
docker compose down -v --remove-orphans
```
