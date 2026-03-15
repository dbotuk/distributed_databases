# Distributed Databases — Counter Performance Tester

A homework project for comparing performance and correctness of distributed counters implemented with different backends: **Web API**, **PostgreSQL**, **Hazelcast**, **MongoDB**, **Cassandra**, and **Neo4j**. A single productivity tester runs concurrent clients against any backend and reports throughput (requests per second) and final count.

## Project structure

```
Homework/
├── counters/
│   ├── productivity_tester.py    # Main script: runs performance tests for any counter type
│   ├── requirements.txt         # Python dependencies
│   ├── web_counter/              # HTTP counter service (FastAPI) + direct client
│   │   ├── api/
│   │   │   ├── web_counter.py    # FastAPI app (disk / shared_memory / postgresql / hazelcast)
│   │   │   └── Dockerfile
│   │   ├── utils.py              # Tester client: setup, reset, count, increment, shutdown
│   │   └── docker-compose.yml
│   ├── postgresql_counter/       # Direct PostgreSQL counter client
│   │   ├── utils.py
│   │   └── postgresql_counter.py
│   ├── hazelcast_counter/        # Direct Hazelcast counter client (IMap + IAtomicLong)
│   │   ├── utils.py
│   │   ├── hazelcast_counter.py
│   │   └── docker-compose.yml    # 3-node Hazelcast cluster
│   ├── mongodb_counter/          # Direct MongoDB counter client (atomic $inc)
│   │   ├── utils.py
│   │   ├── mongodb_counter.py
│   │   └── __init__.py
│   ├── cassandra_counter/       # Direct Cassandra counter client (native counter column)
│   │   ├── utils.py
│   │   ├── cassandra_counter.py
│   │   └── __init__.py
│   └── neo4j_counter/            # Direct Neo4j counter client (Counter node, MERGE/ON MATCH SET)
│       ├── utils.py
│       ├── neo4j_counter.py
│       └── __init__.py
├── mongo/
│   ├── docker-compose.yml        # MongoDB service for counter
│   └── e_shop.mongodb.js         # (optional) other MongoDB scripts
├── cassandra/
│   ├── docker-compose.yml        # Cassandra cluster for counter
│   └── e_shop.cql                # (optional) other Cassandra scripts
├── cassandra-with-replication/
│   ├── docker-compose.yml        # Separate 3-node Cassandra cluster for replication experiments
│   └── replication_guide.md      # Manual step-by-step guide for Task 8
├── neo4j/
│   ├── docker-compose.yml        # Neo4j service for counter
│   └── e_shop.cypher             # (optional) other Neo4j scripts
└── README.md
```

## Requirements

- Python 3.11+
- For **web** counter: running Web Counter service (e.g. via Docker).
- For **postgresql**: running PostgreSQL (connection via env or code defaults).
- For **hazelcast**: running Hazelcast cluster (e.g. `counters/hazelcast_counter/docker-compose.yml`).
- For **mongodb**: running MongoDB (e.g. `mongo/docker-compose.yml`).
- For **cassandra**: running Cassandra (e.g. `cassandra/docker-compose.yml`).
- For **Cassandra replication experiments**: running the 3-node cluster in `cassandra-with-replication/`.
- For **neo4j**: running Neo4j (e.g. `neo4j/docker-compose.yml`).

## Setup

### 1. Python environment

```bash
cd counters
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Backend services (as needed)

**Web counter (optional, for `--counter-type web`):**

- Build and run the web counter (see `counters/web_counter/docker-compose.yml`). It can use storage: `shared_memory`, `disk`, `postgresql`, or `hazelcast`.
- Default endpoint: `http://localhost:8080`.

**Hazelcast (for `--counter-type hazelcast`):**

```bash
# Create network once if not exists
docker network create counter_network

cd counters/hazelcast_counter
docker compose up -d
```

**MongoDB (for `--counter-type mongodb`):**

```bash
docker network create counter_network   # if not exists
cd mongo-with-replication
docker compose up -d

# verify replica set status
docker exec -it mongo1 mongosh --eval "rs.status().members.map(m => ({name: m.name, state: m.stateStr}))"

# if auto-init did not run, initialize manually once
docker exec -it mongo1 mongosh --eval '
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongo1:27017", priority: 2 },
    { _id: 1, host: "mongo2:27017", priority: 1 },
    { _id: 2, host: "mongo3:27017", priority: 1 }
  ]
})
'
```

MongoDB in this repository runs as a 3-member replica set (`P-S-S`): `mongo1` (preferred primary), `mongo2`, `mongo3`.

For local benchmarking from the host machine against the current primary only:

```bash
cd counters
export MONGO_URI="mongodb://localhost:27017/counter_db?directConnection=true&serverSelectionTimeoutMS=5000"
```

For failover experiments, run the client inside Docker network `counter_network` with:

```bash
MONGO_URI="mongodb://mongo1:27017,mongo2:27017,mongo3:27017/counter_db?replicaSet=rs0"
```

**MongoDB failover check (manual):**

```bash
# 1) Check current PRIMARY
docker exec -it mongo1 mongosh --quiet --eval "db.hello().primary"

# 2) Stop current primary (example: mongo1)
docker stop mongo1

# 3) Wait ~10-20 seconds and verify a new PRIMARY is elected
docker exec -it mongo2 mongosh --quiet --eval "db.hello().isWritablePrimary"
docker exec -it mongo3 mongosh --quiet --eval "db.hello().isWritablePrimary"

# 4) Start stopped node back
docker start mongo1
```

**Cassandra replication cluster (Task 8):**

Use the dedicated folder `cassandra-with-replication/` for manual replication and consistency experiments.

```bash
cd cassandra-with-replication
docker compose down -v --remove-orphans

# start nodes sequentially
docker compose up -d cassandra-node1
docker exec cassandra-node1 nodetool status

docker compose up -d cassandra-node2
docker exec cassandra-node2 nodetool status

docker compose up -d cassandra-node3
docker exec cassandra-node1 nodetool status
```

Wait until every node appears as `UN` before starting the next one.

See [cassandra-with-replication/replication_guide.md](/Users/denisbotuk/Documents/UCU%20(DS%20+%20DE)/Distributed%20Databases/Homework/cassandra-with-replication/replication_guide.md) for the full manual workflow:

- creating keyspaces with `SimpleStrategy` and replication factor `1`, `2`, `3`;
- creating tables and testing reads/writes through different nodes;
- checking replica placement with `nodetool getendpoints`;
- testing consistency levels with one stopped node;
- network partition and conflict experiments;
- lightweight transaction (LWT) behaviour in normal and partitioned cluster states.

**Cassandra counter benchmark (for `--counter-type cassandra`):**

```bash
cd counters

# RF=3 counter table in keyspace_rf3, Consistency ONE
CASSANDRA_HOST=localhost \
CASSANDRA_PORT=9042 \
CASSANDRA_KEYSPACE=keyspace_rf3 \
CASSANDRA_COUNTER_TABLE=likes_counter \
CASSANDRA_CONSISTENCY=ONE \
python productivity_tester.py --counter-type cassandra --n-clients 10 --n-calls-per-client 10000

# RF=3 counter table in keyspace_rf3, Consistency QUORUM
CASSANDRA_HOST=localhost \
CASSANDRA_PORT=9042 \
CASSANDRA_KEYSPACE=keyspace_rf3 \
CASSANDRA_COUNTER_TABLE=likes_counter \
CASSANDRA_CONSISTENCY=QUORUM \
python productivity_tester.py --counter-type cassandra --n-clients 10 --n-calls-per-client 10000
```

The Cassandra counter client now supports:

- `CASSANDRA_KEYSPACE` - target keyspace, e.g. `keyspace_rf3`
- `CASSANDRA_COUNTER_TABLE` - counter table name, e.g. `likes_counter`
- `CASSANDRA_CONSISTENCY` - `ONE`, `QUORUM`, etc.

Observed benchmark results for `10` clients x `10000` increments:

- `CONSISTENCY ONE`: `Final count = 100000`, `Total time = 50.19s`, `RPS = 1992.54`
- `CONSISTENCY QUORUM`: `Final count = 100000`, `Total time = 65.53s`, `RPS = 1525.96`

**Neo4j (for `--counter-type neo4j`):**

```bash
cd neo4j
docker compose up -d
# Default: neo4j://localhost:7687, user neo4j, password password
```

**PostgreSQL:** start your PostgreSQL instance and set `DB_HOST`, `DB_PORT`, etc. as required by `postgresql_counter` / web counter.

## Usage

Run the productivity tester from the `counters` directory:

```bash
cd counters
python productivity_tester.py --counter-type <TYPE> --n-clients <N> --n-calls-per-client <M> [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--counter-type` | Yes | One of: `web`, `postgresql`, `hazelcast`, `mongodb`, `cassandra`, `neo4j` |
| `--n-clients` | Yes | Number of concurrent client threads |
| `--n-calls-per-client` | Yes | Number of increment calls per client |
| `--counter-host` | No | Web counter host (default: `localhost` or `COUNTER_HOST`) |
| `--counter-port` | No | Web counter port (default: `8080` or `COUNTER_PORT`) |
| `--method` | No | Backend-specific method (see below) |
| `--write-concern` | No | MongoDB write concern, e.g. `1` or `majority` |
| `--do-retries` | No | Use retries for PostgreSQL (default: `False`) |

### Counter-type–specific options

**Web** (`--counter-type web`)

- Uses HTTP: `POST /reset`, `GET /count`, `POST /inc`.
- Optional: `--counter-host`, `--counter-port` (or env `COUNTER_HOST`, `COUNTER_PORT`).

**PostgreSQL** (`--counter-type postgresql`)

- `--method`: e.g. `row_level_locking`, `optimistic_concurrency_control`, `inplace_update`, `serializable_update`, `lost_update` (see `postgresql_counter/postgresql_counter.py`).
- `--do-retries`: enable retries for increment (e.g. for OCC).

**Hazelcast** (`--counter-type hazelcast`)

- `--method`: **required**, one of:
  - `no_lock` — IMap get/put, no locking (fast, count can be wrong).
  - `pessimistic` — IMap with locking (correct count).
  - `optimistic` — IMap with optimistic concurrency.
  - `atomic` — CP IAtomicLong (linearizable, correct count).

**MongoDB** (`--counter-type mongodb`)

- `--method`: `find_one_and_update` or default update-based increment.
- `--write-concern`: `1` or `majority`.
- Recommended for the homework counter benchmark: `--method find_one_and_update`.
- Connection: env `MONGO_HOST`, `MONGO_PORT`, `MONGO_DB`, or `MONGO_URI` (see `mongodb_counter/mongodb_counter.py`).

**Cassandra** (`--counter-type cassandra`)

- No extra CLI flags. Uses native counter column with atomic `UPDATE ... SET counter = counter + 1`.
- Connection: env `CASSANDRA_HOST`, `CASSANDRA_PORT` (default: `localhost`, `9042`).
- Optional env:
  - `CASSANDRA_KEYSPACE` - default `keyspace_rf3`
  - `CASSANDRA_COUNTER_TABLE` - default `likes_counter`
  - `CASSANDRA_CONSISTENCY` - default `ONE`

**Neo4j** (`--counter-type neo4j`)

- No extra CLI flags. Uses a single Counter node with atomic `MERGE ... ON MATCH SET c.value = c.value + 1`.
- Connection: env `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` (default: `neo4j://localhost:7687`, `neo4j`, `password`).

### Example runs

```bash
# Web counter: 1 client, 10000 calls
python productivity_tester.py --counter-type web --n-clients 1 --n-calls-per-client 10000

# Web counter: 10 clients, custom host/port
python productivity_tester.py --counter-type web --n-clients 10 --n-calls-per-client 10000 --counter-host localhost --counter-port 8080

# Hazelcast with pessimistic locking (correct count)
python productivity_tester.py --counter-type hazelcast --n-clients 10 --n-calls-per-client 1000 --method pessimistic

# Hazelcast without lock (faster, count may be incorrect)
python productivity_tester.py --counter-type hazelcast --n-clients 10 --n-calls-per-client 1000 --method no_lock

# Hazelcast IAtomicLong (CP Subsystem)
python productivity_tester.py --counter-type hazelcast --n-clients 10 --n-calls-per-client 1000 --method atomic

# MongoDB benchmark from host to current primary only (writeConcern=1)
MONGO_URI="mongodb://localhost:27017/counter_db?directConnection=true&serverSelectionTimeoutMS=5000" \
python productivity_tester.py --counter-type mongodb --n-clients 10 --n-calls-per-client 10000 --method find_one_and_update --write-concern 1

# MongoDB benchmark with writeConcern=majority
MONGO_URI="mongodb://localhost:27017/counter_db?directConnection=true&serverSelectionTimeoutMS=5000" \
python productivity_tester.py --counter-type mongodb --n-clients 10 --n-calls-per-client 10000 --method find_one_and_update --write-concern majority

# MongoDB failover-aware benchmark inside Docker network
docker run --rm \
  --network counter_network \
  -v "$PWD:/workspace" \
  -w /workspace/counters \
  -e MONGO_URI="mongodb://mongo1:27017,mongo2:27017,mongo3:27017/counter_db?replicaSet=rs0" \
  python:3.11-slim \
  bash -lc "pip install -r requirements.txt && python productivity_tester.py --counter-type mongodb --n-clients 10 --n-calls-per-client 10000 --method find_one_and_update --write-concern 1"

# Cassandra counter with Consistency ONE
CASSANDRA_KEYSPACE=keyspace_rf3 CASSANDRA_COUNTER_TABLE=likes_counter CASSANDRA_CONSISTENCY=ONE \
python productivity_tester.py --counter-type cassandra --n-clients 10 --n-calls-per-client 10000

# Cassandra counter with Consistency QUORUM
CASSANDRA_KEYSPACE=keyspace_rf3 CASSANDRA_COUNTER_TABLE=likes_counter CASSANDRA_CONSISTENCY=QUORUM \
python productivity_tester.py --counter-type cassandra --n-clients 10 --n-calls-per-client 10000

# Neo4j (Counter node, atomic MERGE/ON MATCH SET)
python productivity_tester.py --counter-type neo4j --n-clients 10 --n-calls-per-client 1000

# PostgreSQL with retries (e.g. for OCC)
python productivity_tester.py --counter-type postgresql --n-clients 10 --n-calls-per-client 1000 --method optimistic_concurrency_control --do-retries True
```

## Output

The script prints logs during the run and a summary like:

```
============================================================
PERFORMANCE TEST RESULTS
============================================================
Number of clients:           N
Calls per client:            M
Total time (seconds):        T
Requests per second (RPS):   RPS
Final count:                 C
============================================================
```

You can compare **RPS** and **final count vs expected** (N×M) across backends and methods to study throughput and correctness under concurrency.

## Dependencies (from `counters/requirements.txt`)

- `fastapi`, `uvicorn`, `pydantic` — Web counter API
- `requests` — HTTP client for web counter tests
- `psycopg2-binary` — PostgreSQL client
- `hazelcast-python-client` — Hazelcast client
- `pymongo` — MongoDB client
- `cassandra-driver` — Cassandra client
- `neo4j` — Neo4j Python driver

## Environment variables (overview)

| Backend | Variables |
|---------|-----------|
| Web | `COUNTER_HOST`, `COUNTER_PORT` (tester); `HOST`, `PORT`, `STORAGE_METHOD`, `STORAGE_PATH`, `WORKERS`, `DB_*`, `HZ_*` (service) |
| PostgreSQL | DB connection (host, port, db, user, password) as in `postgresql_counter` / web counter |
| Hazelcast | `HZ_CLUSTER_MEMBERS`, `HZ_CLUSTER_NAME`, `HZ_MAP_NAME`, `HZ_COUNTER_KEY`, `HZ_ATOMIC_LONG_NAME` |
| MongoDB | `MONGO_HOST`, `MONGO_PORT`, `MONGO_DB`, `MONGO_URI` |
| Cassandra | `CASSANDRA_HOST`, `CASSANDRA_PORT` |
| Neo4j | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` |

## License / course

Part of the **Distributed Databases** course (UCU). Use for learning and homework only.
