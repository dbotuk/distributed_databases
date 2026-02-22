# Distributed Databases — Counter Performance Tester

A homework project for comparing performance and correctness of distributed counters implemented with different backends: **Web API**, **PostgreSQL**, **Hazelcast**, and **MongoDB**. A single productivity tester runs concurrent clients against any backend and reports throughput (requests per second) and final count.

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
│   └── mongodb_counter/          # Direct MongoDB counter client (atomic $inc)
│       ├── utils.py
│       ├── mongodb_counter.py
│       └── __init__.py
├── mongo/
│   ├── docker-compose.yml        # MongoDB service for counter
│   └── e_shop.mongodb.js         # (optional) other MongoDB scripts
└── README.md
```

## Requirements

- Python 3.11+
- For **web** counter: running Web Counter service (e.g. via Docker).
- For **postgresql**: running PostgreSQL (connection via env or code defaults).
- For **hazelcast**: running Hazelcast cluster (e.g. `counters/hazelcast_counter/docker-compose.yml`).
- For **mongodb**: running MongoDB (e.g. `mongo/docker-compose.yml`).

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
cd mongo
docker compose up -d
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
| `--counter-type` | Yes | One of: `web`, `postgresql`, `hazelcast`, `mongodb` |
| `--n-clients` | Yes | Number of concurrent client threads |
| `--n-calls-per-client` | Yes | Number of increment calls per client |
| `--counter-host` | No | Web counter host (default: `localhost` or `COUNTER_HOST`) |
| `--counter-port` | No | Web counter port (default: `8080` or `COUNTER_PORT`) |
| `--method` | No | Backend-specific method (see below) |
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

- No extra CLI flags. Uses atomic `$inc` on a single document.
- Connection: env `MONGO_HOST`, `MONGO_PORT`, `MONGO_DB`, or `MONGO_URI` (see `mongodb_counter/mongodb_counter.py`).

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

# MongoDB (atomic $inc)
python productivity_tester.py --counter-type mongodb --n-clients 10 --n-calls-per-client 1000

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

## Environment variables (overview)

| Backend | Variables |
|---------|-----------|
| Web | `COUNTER_HOST`, `COUNTER_PORT` (tester); `HOST`, `PORT`, `STORAGE_METHOD`, `STORAGE_PATH`, `WORKERS`, `DB_*`, `HZ_*` (service) |
| PostgreSQL | DB connection (host, port, db, user, password) as in `postgresql_counter` / web counter |
| Hazelcast | `HZ_CLUSTER_MEMBERS`, `HZ_CLUSTER_NAME`, `HZ_MAP_NAME`, `HZ_COUNTER_KEY`, `HZ_ATOMIC_LONG_NAME` |
| MongoDB | `MONGO_HOST`, `MONGO_PORT`, `MONGO_DB`, `MONGO_URI` |

## License / course

Part of the **Distributed Databases** course (UCU). Use for learning and homework only.
