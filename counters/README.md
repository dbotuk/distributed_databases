# Counter Implementations - Documentation and Testing Instructions

## Project Description

This project contains multiple counter implementations for distributed database testing:

1. **Web Counter**: A FastAPI web server that provides an API for incrementing and retrieving a counter value with multiple storage backends
2. **PostgreSQL Counter**: A direct PostgreSQL-based counter implementation with various concurrency control methods
3. **Hazelcast Counter**: A Hazelcast-based counter using IMap or CP Subsystem IAtomicLong, with multiple concurrency methods

All implementations can be tested using the unified `productivity_tester.py` script.

---

## Web Counter

### Overview

Web Counter is a FastAPI web server that provides an API for incrementing and retrieving a counter value. The counter supports three storage modes: shared memory (for in-memory storage with multi-worker support), disk-based file storage, or PostgreSQL database storage. The implementation uses file locking (`fcntl`) for thread-safe operations and supports multiple worker processes.

### Architecture

- **Framework**: FastAPI with async/await support
- **Server**: Uvicorn with configurable worker processes
- **Synchronization**: File locking (`fcntl.flock`) for thread-safe operations (shared memory and disk modes)
- **Storage Backends**:
  - **Shared Memory**: Uses `multiprocessing.shared_memory` for in-memory storage across multiple workers
  - **Disk Storage**: File-based storage with atomic read-modify-write operations
  - **PostgreSQL**: Database-backed storage with atomic UPDATE operations

### API Endpoints

- `POST /reset` - Resets the counter to 0
- `POST /inc` - Increments the counter by 1 (thread-safe)
- `GET /count` - Returns the current counter value

### Storage Modes

#### Shared Memory Storage
- **Activation**: Set `STORAGE_METHOD=shared_memory` (or leave `STORAGE_METHOD` unset and `STORAGE_PATH` empty)
- **Implementation**: Uses `multiprocessing.shared_memory` to share counter state across multiple worker processes
- **Locking**: File-based locking (`/tmp/web_counter_shared_memory.lock`) ensures atomic increments
- **Use Case**: Best for high-performance scenarios with multiple workers
- **Persistence**: Counter is lost on server restart

#### Disk Storage
- **Activation**: Set `STORAGE_METHOD=disk` and provide `STORAGE_PATH` pointing to a file path
- **Implementation**: Stores counter value in a text file with file locking for synchronization
- **Locking**: Uses `fcntl.flock` for exclusive locks during read-modify-write operations
- **Use Case**: Persistence across server restarts, single-worker deployments
- **Persistence**: Counter persists across server restarts

#### PostgreSQL Storage
- **Activation**: Set `STORAGE_METHOD=postgresql` and configure PostgreSQL connection variables
- **Implementation**: Stores counter value in PostgreSQL database using atomic UPDATE operations
- **Locking**: Database-level locking and transaction isolation
- **Use Case**: Distributed deployments, persistence, and database-backed storage
- **Persistence**: Counter persists in database

### Environment Variables

- `HOST` - Server host (default: `0.0.0.0`)
- `PORT` - Server port (default: `8080`)
- `STORAGE_METHOD` - Storage method: `shared_memory`, `disk`, or `postgresql` (default: `shared_memory`)
- `STORAGE_PATH` - Path to counter file (for disk storage mode, ignored for other modes)
- `WORKERS` - Number of uvicorn worker processes (default: `1`)
- `DB_HOST` - PostgreSQL host (for PostgreSQL storage, default: `localhost`)
- `DB_PORT` - PostgreSQL port (for PostgreSQL storage, default: `5432`)
- `POSTGRES_DB` - PostgreSQL database name (for PostgreSQL storage, default: `counter_db`)
- `POSTGRES_USER` - PostgreSQL user (for PostgreSQL storage, default: `postgres`)
- `POSTGRES_PASSWORD` - PostgreSQL password (for PostgreSQL storage, default: `postgres`)

### Installation and Setup

#### Option 1: Running with Docker Compose (Recommended)

1. Start PostgreSQL database (if using PostgreSQL storage):
```bash
cd postgresql_counter
docker-compose up -d
```

2. Navigate to the `web_counter` directory:
```bash
cd web_counter
```

3. Start the server:
```bash
docker-compose up --build
```

The default configuration uses:
- **4 workers** for multi-processing support
- **PostgreSQL storage** (requires PostgreSQL database to be running)
- **Port 8080**

The server will be available at `http://localhost:8080`

#### Customizing Docker Compose Configuration

Edit `web_counter/docker-compose.yml` to change settings:

**Shared Memory Mode:**
```yaml
environment:
  - HOST=0.0.0.0
  - PORT=8080
  - STORAGE_METHOD=shared_memory
  - WORKERS=4
```

**Disk Storage Mode:**
```yaml
environment:
  - HOST=0.0.0.0
  - PORT=8080
  - STORAGE_METHOD=disk
  - STORAGE_PATH=/app/counter.txt
  - WORKERS=1
```

**PostgreSQL Storage Mode:**
```yaml
environment:
  - HOST=0.0.0.0
  - PORT=8080
  - STORAGE_METHOD=postgresql
  - WORKERS=4
  - DB_HOST=postgresql-counter-db
  - DB_PORT=5432
  - POSTGRES_DB=counter_db
  - POSTGRES_USER=postgres
  - POSTGRES_PASSWORD=postgres
```

#### Option 2: Running with Docker (Standalone)

Build the image:
```bash
cd web_counter
docker build -t web-counter -f api/Dockerfile ..
```

Run with shared memory:
```bash
docker run -p 8080:8080 -e STORAGE_METHOD=shared_memory -e WORKERS=4 web-counter
```

Run with disk storage:
```bash
docker run -p 8080:8080 -e STORAGE_METHOD=disk -e STORAGE_PATH=/app/counter.txt -e WORKERS=1 web-counter
```

Run with PostgreSQL storage:
```bash
docker run -p 8080:8080 -e STORAGE_METHOD=postgresql -e DB_HOST=localhost -e WORKERS=4 web-counter
```

#### Option 3: Running without Docker

1. Install dependencies:
```bash
cd counters
pip install -r requirements.txt
```

2. Start PostgreSQL (if using PostgreSQL storage):
```bash
cd postgresql_counter
docker-compose up -d
```

3. Start the server:
```bash
cd web_counter/api
python web_counter.py
```

Or with environment variables:
```bash
# Shared memory mode
STORAGE_METHOD=shared_memory WORKERS=4 python web_counter.py

# Disk storage mode
STORAGE_METHOD=disk STORAGE_PATH=counter.txt WORKERS=1 python web_counter.py

# PostgreSQL storage mode
STORAGE_METHOD=postgresql DB_HOST=localhost WORKERS=4 python web_counter.py
```

---

## PostgreSQL Counter

### Overview

PostgreSQL Counter is a direct PostgreSQL-based counter implementation that provides various concurrency control methods for testing different transaction isolation and locking strategies. It's designed to be used directly via Python functions rather than through a web API.

### Architecture

- **Database**: PostgreSQL 15+
- **Connection**: Direct psycopg2 connections
- **Concurrency Control**: Multiple methods available for testing different approaches

### Available Methods

The PostgreSQL counter supports the following increment methods:

1. **`lost_update`** - Read-modify-write without locking (demonstrates lost update problem)
   - Reads current value, increments, and writes back
   - No locking or transaction isolation
   - **Use Case**: Demonstrating concurrency issues

2. **`inplace_update`** - Atomic SQL UPDATE (recommended for simple cases)
   - Uses `UPDATE counter = counter + 1` in a single statement
   - Atomic at database level
   - **Use Case**: Simple, efficient increments

3. **`row_level_locking`** - SELECT FOR UPDATE with explicit locking
   - Uses `SELECT ... FOR UPDATE` to acquire row-level lock
   - Prevents concurrent modifications
   - **Use Case**: Explicit locking control

4. **`optimistic_concurrency_control`** - Version-based optimistic locking
   - Uses version column to detect conflicts
   - Retries on version mismatch
   - **Use Case**: Optimistic concurrency control

5. **`serializable_update`** - Serializable transaction isolation
   - Uses PostgreSQL's SERIALIZABLE isolation level
   - Handles serialization failures with retries
   - **Use Case**: Strongest isolation guarantees

### Functions

- `init_user_counter_table(user_id, isolation_level=None)` - Initializes/resets the counter table for a user
- `get_user_counter(user_id, isolation_level=None)` - Gets the current counter value
- `increment_user_counter(user_id, method=None, do_retries=False)` - Increments the counter using specified method

### Environment Variables

- `DB_HOST` - PostgreSQL host (default: `localhost`)
- `DB_PORT` - PostgreSQL port (default: `5432`)
- `POSTGRES_DB` - PostgreSQL database name (default: `counter_db`)
- `POSTGRES_USER` - PostgreSQL user (default: `postgres`)
- `POSTGRES_PASSWORD` - PostgreSQL password (default: `postgres`)

### Installation and Setup

#### Option 1: Running with Docker Compose (Recommended)

1. Navigate to the `postgresql_counter` directory:
```bash
cd postgresql_counter
```

2. Start PostgreSQL:
```bash
docker-compose up -d
```

The default configuration:
- **Port 5432**
- **Database**: `counter_db`
- **User**: `postgres`
- **Password**: `postgres`

#### Option 2: Using Existing PostgreSQL

Ensure PostgreSQL is running and accessible, then set environment variables:
```bash
export DB_HOST=localhost
export DB_PORT=5432
export POSTGRES_DB=counter_db
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres
```

---

## Hazelcast Counter

### Overview

Hazelcast Counter is a direct Hazelcast-based counter implementation that uses either an IMap (distributed map) or the CP Subsystem's IAtomicLong for linearizable increments. It supports multiple concurrency methods: no locking (for demonstrating lost updates), pessimistic locking, optimistic locking with `replaceIfSame`, and atomic increments via IAtomicLong. It is designed to be used directly via Python functions and is driven by the productivity tester.

### Architecture

- **Cluster**: Hazelcast 5.x (default: 3 members on ports 5701–5703)
- **Client**: hazelcast-python-client with optional CP Subsystem usage
- **Storage**: IMap entry (key `count` in map `counter-map`) or IAtomicLong named `counter`
- **Concurrency**: no_lock, pessimistic (map lock), optimistic (replaceIfSame), or atomic (IAtomicLong)

### Available Methods

1. **`no_lock`** – Read-get, increment, put without locking (can show lost updates)
2. **`pessimistic`** – Lock key, get/put, unlock (correct, default for tests)
3. **`optimistic`** – get; put via `replaceIfSame(old, new)` with retries (correct under contention)
4. **`atomic`** – CP Subsystem IAtomicLong `incrementAndGet()` (linearizable, requires CP Subsystem)

For `atomic`, the cluster must be started with the CP Subsystem (see `hazelcast-cp.yaml`). The default docker-compose runs without CP; uncomment the config/volume lines to use IAtomicLong.

### Environment Variables

- `HZ_CLUSTER_MEMBERS` – Comma-separated member list (default: `127.0.0.1:5701,127.0.0.1:5702,127.0.0.1:5703`)
- `HZ_CLUSTER_NAME` – Cluster name (default: `dev`)
- `HZ_MAP_NAME` – IMap name for map-based methods (default: `counter-map`)
- `HZ_COUNTER_KEY` – Key in the map (default: `count`)
- `HZ_ATOMIC_LONG_NAME` – IAtomicLong name for `atomic` method (default: `counter`)

### Installation and Setup

#### Option 1: Running with Docker Compose (Recommended)

1. Create the external network (if not already present):
```bash
docker network create counter_network
```

2. Navigate to the `hazelcast_counter` directory:
```bash
cd hazelcast_counter
```

3. Start the Hazelcast cluster (3 members):
```bash
docker-compose up -d
```

For IAtomicLong (`--method atomic`), enable the CP Subsystem by uncommenting the `HAZELCAST_CONFIG` and `volumes` lines in `docker-compose.yml` so that `hazelcast-cp.yaml` is used (CP member count 3).

#### Option 2: Using an Existing Hazelcast Cluster

Set environment variables to point to your cluster:
```bash
export HZ_CLUSTER_MEMBERS=host1:5701,host2:5701,host3:5701
export HZ_CLUSTER_NAME=dev
```

### Testing (Hazelcast)

**With pessimistic locking (default, correct count):**
```bash
python productivity_tester.py --counter-type hazelcast --n-clients 10 --n-calls-per-client 1000
```

**With no lock (faster, final count may be incorrect):**
```bash
python productivity_tester.py --counter-type hazelcast --n-clients 10 --n-calls-per-client 1000 --method no_lock
```

**With optimistic locking:**
```bash
python productivity_tester.py --counter-type hazelcast --n-clients 10 --n-calls-per-client 1000 --method optimistic
```

**With IAtomicLong (CP Subsystem, linearizable):**
```bash
python productivity_tester.py --counter-type hazelcast --n-clients 10 --n-calls-per-client 1000 --method atomic
```
(Requires cluster started with `hazelcast-cp.yaml`.)

---

## Testing

The testing script `productivity_tester.py` is located in the `counters` directory. It uses concurrent threads to simulate multiple clients making requests to either the web counter API or directly to the PostgreSQL counter functions.

### General Testing Command

**For Web Counter:**
```bash
python productivity_tester.py --counter-type web --n-clients <number_of_clients> --n-calls-per-client <calls_per_client> [--counter-host <host>] [--counter-port <port>]
```

**For PostgreSQL Counter:**
```bash
python productivity_tester.py --counter-type postgresql --n-clients <number_of_clients> --n-calls-per-client <calls_per_client> [--method <method>] [--do-retries <True/False>]
```

**For Hazelcast Counter:**
```bash
python productivity_tester.py --counter-type hazelcast --n-clients <number_of_clients> --n-calls-per-client <calls_per_client> [--method no_lock|pessimistic|optimistic|atomic]
```

### Parameters

- `--counter-type` - Type of counter (required): `web`, `postgresql`, or `hazelcast`
- `--n-clients` - Number of concurrent clients (required)
- `--n-calls-per-client` - Number of calls each client makes (required)
- `--counter-host` - Server host for web counter (default: `localhost` or `COUNTER_HOST` env var)
- `--counter-port` - Server port for web counter (default: `8080` or `COUNTER_PORT` env var)
- `--method` - Method for PostgreSQL counter: `lost_update`, `inplace_update`, `row_level_locking`, `optimistic_concurrency_control`, or `serializable_update`. For Hazelcast counter: `no_lock`, `pessimistic`, `optimistic`, or `atomic`
- `--do-retries` - Enable retries for PostgreSQL counter serialization errors (default: `False`)

### How Testing Works

1. The script automatically resets the counter to 0 before starting
2. Spawns `n_clients` concurrent threads, each making `n_calls_per_client` requests
3. Each client calls the increment function/endpoint sequentially
4. After all clients complete, the script retrieves the final count
5. Reports performance metrics including RPS (requests per second)

## Test Scenarios

### Web Counter Tests

#### Test 1: One Client, 10,000 Calls

**Expected Result**: `count = 10,000`

**Command**:
```bash
python productivity_tester.py --counter-type web --n-clients 1 --n-calls-per-client 10000
```

**Description**: One client sequentially makes 10,000 calls to `/inc`. The final counter value should equal 10,000.

**Metric**: Requests per second (RPS) for sequential calls.

---

#### Test 2: Two Clients, 10,000 Calls Each

**Expected Result**: `count = 20,000`

**Command**:
```bash
python productivity_tester.py --counter-type web --n-clients 2 --n-calls-per-client 10000
```

**Description**: Two clients simultaneously make 10,000 calls each. The final counter value should equal 20,000.

**Metric**: Requests per second (RPS) for parallel calls from two clients.

---

#### Test 3: Five Clients, 10,000 Calls Each

**Expected Result**: `count = 50,000`

**Command**:
```bash
python productivity_tester.py --counter-type web --n-clients 5 --n-calls-per-client 10000
```

**Description**: Five clients simultaneously make 10,000 calls each. The final counter value should equal 50,000.

**Metric**: Requests per second (RPS) for parallel calls from five clients.

---

#### Test 4: Ten Clients, 10,000 Calls Each

**Expected Result**: `count = 100,000`

**Command**:
```bash
python productivity_tester.py --counter-type web --n-clients 10 --n-calls-per-client 10000
```

**Description**: Ten clients simultaneously make 10,000 calls each. The final counter value should equal 100,000.

**Metric**: Requests per second (RPS) for parallel calls from ten clients.

---

### PostgreSQL Counter Tests

#### Test with Inplace Update (Recommended)

**Expected Result**: `count = n_clients * n_calls_per_client`

**Command**:
```bash
python productivity_tester.py --counter-type postgresql --n-clients 10 --n-calls-per-client 10000 --method inplace_update
```

**Description**: Tests atomic SQL UPDATE method with 10 concurrent clients.

---

#### Test with Row-Level Locking

**Command**:
```bash
python productivity_tester.py --counter-type postgresql --n-clients 10 --n-calls-per-client 10000 --method row_level_locking
```

**Description**: Tests explicit row-level locking with `SELECT FOR UPDATE`.

---

#### Test with Optimistic Concurrency Control

**Command**:
```bash
python productivity_tester.py --counter-type postgresql --n-clients 10 --n-calls-per-client 10000 --method optimistic_concurrency_control
```

**Description**: Tests version-based optimistic locking with automatic retries.

---

#### Test with Serializable Isolation

**Command**:
```bash
python productivity_tester.py --counter-type postgresql --n-clients 10 --n-calls-per-client 10000 --method serializable_update --do-retries True
```

**Description**: Tests SERIALIZABLE isolation level with retry logic for serialization failures.

---

#### Test Lost Update Problem

**Command**:
```bash
python productivity_tester.py --counter-type postgresql --n-clients 10 --n-calls-per-client 10000 --method lost_update
```

**Description**: Demonstrates the lost update problem (final count will be less than expected).

---

### Hazelcast Counter Tests

#### Test with Pessimistic Locking (Default)

**Expected Result**: `count = n_clients * n_calls_per_client`

**Command**:
```bash
python productivity_tester.py --counter-type hazelcast --n-clients 10 --n-calls-per-client 1000
```

**Description**: Tests map-based counter with key lock (correct count).

---

#### Test with No Lock

**Command**:
```bash
python productivity_tester.py --counter-type hazelcast --n-clients 10 --n-calls-per-client 1000 --method no_lock
```

**Description**: Demonstrates lost updates on IMap without locking (final count may be less than expected).

---

#### Test with Optimistic Locking

**Command**:
```bash
python productivity_tester.py --counter-type hazelcast --n-clients 10 --n-calls-per-client 1000 --method optimistic
```

**Description**: Tests replaceIfSame-based optimistic concurrency (correct count).

---

#### Test with IAtomicLong (CP Subsystem)

**Command**:
```bash
python productivity_tester.py --counter-type hazelcast --n-clients 10 --n-calls-per-client 1000 --method atomic
```

**Description**: Tests CP Subsystem IAtomicLong (linearizable). Requires cluster started with `hazelcast-cp.yaml`.

---

## Interpreting Results

After running each test, the script outputs the following information:

```
============================================================
PERFORMANCE TEST RESULTS
============================================================
Number of clients:           <N>
Calls per client:            <M>
Total calls made:            <actual_count>
Total time (seconds):        <time>
Requests per second (RPS):   <rps>
Final count:                 <final_count>
============================================================
```

### Key Metrics:

1. **Total calls made** - Actual number of successful increment operations
2. **Total time (seconds)** - Total test execution time (wall clock time)
3. **Requests per second (RPS)** - Number of requests per second (main performance metric)
4. **Final count** - Final counter value (should match expected value)

### Correctness Check:

- **Final count** should equal `n_clients * n_calls_per_client` for correct implementations
- If the value doesn't match, it may indicate:
  - Synchronization issues (race conditions)
  - Lost updates (for `lost_update` method, this is expected)
  - Lost requests due to network errors (web counter)
  - Server errors during processing
  - Serialization failures without retries (PostgreSQL counter)

---

## Storage Mode Comparison (Web Counter)

It is recommended to run all tests in all three modes to compare performance:

1. **Shared Memory Storage** (`STORAGE_METHOD=shared_memory`)
   - Faster for high-throughput scenarios
   - Better for multi-worker deployments
   - Counter is lost on server restart

2. **Disk Storage** (`STORAGE_METHOD=disk` with `STORAGE_PATH` set)
   - Persists across server restarts
   - Slightly slower due to disk I/O
   - Better for single-worker deployments or when persistence is required

3. **PostgreSQL Storage** (`STORAGE_METHOD=postgresql`)
   - Persists in database
   - Supports distributed deployments
   - Database-level concurrency control
   - Slightly slower than shared memory but more robust

### Performance Considerations

- **Multiple Workers**: Use `WORKERS=4` or higher for better throughput with shared memory or PostgreSQL
- **Single Worker**: Use `WORKERS=1` for disk storage to avoid file locking contention
- **Shared Memory**: Generally 2-5x faster than disk storage for high-concurrency scenarios
- **PostgreSQL**: Performance depends on database configuration and method used

---

## PostgreSQL Counter Method Comparison

### Method Performance and Correctness

1. **`inplace_update`** ⭐ Recommended
   - ✅ Always correct (atomic SQL operation)
   - ✅ Fastest performance
   - ✅ No retries needed

2. **`row_level_locking`**
   - ✅ Always correct (explicit locking)
   - ✅ Good performance
   - ✅ No retries needed

3. **`optimistic_concurrency_control`**
   - ✅ Always correct (with retries)
   - ⚠️ Moderate performance (may need retries)
   - ✅ Handles conflicts automatically

4. **`serializable_update`**
   - ✅ Always correct (with retries enabled)
   - ⚠️ Lower performance (serialization failures)
   - ⚠️ Requires `--do-retries True` for correctness

5. **`lost_update`**
   - ❌ Incorrect (demonstrates problem)
   - ⚠️ Final count will be less than expected
   - ⚠️ Use only for educational purposes

---

## Hazelcast Counter Method Comparison

1. **`atomic`** ⭐ Recommended when CP Subsystem is available
   - ✅ Linearizable (CP Subsystem IAtomicLong)
   - ✅ Best performance for correct increments
   - ⚠️ Requires cluster started with CP config (`hazelcast-cp.yaml`)

2. **`pessimistic`** (default)
   - ✅ Always correct (key-level lock on IMap)
   - ✅ Good performance, no retries

3. **`optimistic`**
   - ✅ Always correct (replaceIfSame with retries)
   - ⚠️ May need many retries under high contention

4. **`no_lock`**
   - ❌ Incorrect (demonstrates lost updates)
   - ⚠️ Final count may be less than expected
   - ⚠️ Use only for educational purposes

---

## Complete Testing Workflow Example

### Web Counter Testing

```bash
# 1. Start the server (in a separate terminal)
cd web_counter
docker-compose up

# 2. Run tests (in another terminal, from counters directory)
cd counters

# Test 1: 1 client
python productivity_tester.py --counter-type web --n-clients 1 --n-calls-per-client 10000

# Test 2: 2 clients
python productivity_tester.py --counter-type web --n-clients 2 --n-calls-per-client 10000

# Test 3: 5 clients
python productivity_tester.py --counter-type web --n-clients 5 --n-calls-per-client 10000

# Test 4: 10 clients
python productivity_tester.py --counter-type web --n-clients 10 --n-calls-per-client 10000
```

### PostgreSQL Counter Testing

```bash
# 1. Start PostgreSQL (in a separate terminal)
cd postgresql_counter
docker-compose up -d

# 2. Run tests (in another terminal, from counters directory)
cd counters

# Test with inplace_update (recommended)
python productivity_tester.py --counter-type postgresql --n-clients 10 --n-calls-per-client 10000 --method inplace_update

# Test with row-level locking
python productivity_tester.py --counter-type postgresql --n-clients 10 --n-calls-per-client 10000 --method row_level_locking

# Test with optimistic concurrency control
python productivity_tester.py --counter-type postgresql --n-clients 10 --n-calls-per-client 10000 --method optimistic_concurrency_control

# Test with serializable isolation (with retries)
python productivity_tester.py --counter-type postgresql --n-clients 10 --n-calls-per-client 10000 --method serializable_update --do-retries True

# Demonstrate lost update problem
python productivity_tester.py --counter-type postgresql --n-clients 10 --n-calls-per-client 10000 --method lost_update
```

### Hazelcast Counter Testing

```bash
# 1. Create network and start Hazelcast (in a separate terminal)
docker network create counter_network  # if needed
cd hazelcast_counter
docker-compose up -d

# 2. Run tests (in another terminal, from counters directory)
cd counters

# Test with pessimistic locking (default)
python productivity_tester.py --counter-type hazelcast --n-clients 10 --n-calls-per-client 1000

# Test with no lock (demonstrates lost updates)
python productivity_tester.py --counter-type hazelcast --n-clients 10 --n-calls-per-client 1000 --method no_lock

# Test with optimistic locking
python productivity_tester.py --counter-type hazelcast --n-clients 10 --n-calls-per-client 1000 --method optimistic

# Test with IAtomicLong (requires CP Subsystem in cluster)
python productivity_tester.py --counter-type hazelcast --n-clients 10 --n-calls-per-client 1000 --method atomic
```

---

## Project Structure

```
counters/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── productivity_tester.py       # Performance testing script
├── web_counter/
│   ├── docker-compose.yml       # Docker Compose configuration
│   ├── utils.py                 # HTTP client utilities
│   └── api/
│       ├── Dockerfile           # Docker image definition
│       └── web_counter.py       # Main FastAPI application
├── postgresql_counter/
│   ├── docker-compose.yml       # PostgreSQL database configuration
│   ├── utils.py                 # Tester interface (get_functions)
│   ├── postgresql_counter.py    # PostgreSQL counter implementation
│   └── __init__.py
└── hazelcast_counter/
    ├── docker-compose.yml       # Hazelcast cluster (3 members)
    ├── hazelcast-cp.yaml        # Optional CP Subsystem config for IAtomicLong
    ├── hazelcast_counter.py     # Hazelcast counter implementation
    ├── utils.py                 # Tester interface (get_functions)
    └── __init__.py
```

---

## Technical Details

### Web Counter Synchronization Mechanism

The implementation uses different synchronization mechanisms depending on storage mode:

- **Shared Memory Mode**: Uses a lock file at `/tmp/web_counter_shared_memory.lock` to synchronize access to shared memory
- **Disk Storage Mode**: Uses exclusive file locks on the counter file during read-modify-write operations
- **PostgreSQL Mode**: Uses database-level atomic operations and transaction isolation

**Retry Logic**: Shared memory and disk modes include retry mechanisms with exponential backoff for lock acquisition.

### PostgreSQL Counter Concurrency Control

- **Lost Update**: No concurrency control (demonstrates the problem)
- **Inplace Update**: Atomic SQL UPDATE statement
- **Row-Level Locking**: `SELECT ... FOR UPDATE` with explicit locks
- **Optimistic Concurrency Control**: Version-based conflict detection with automatic retries
- **Serializable**: SERIALIZABLE isolation level with retry logic for serialization failures

### Error Handling

- Automatic retry on lock acquisition failures (web counter)
- Retry logic for serialization failures (PostgreSQL counter with `do_retries=True`)
- Graceful degradation if locks cannot be acquired
- Comprehensive logging for debugging
- Error recovery for file I/O operations

---

## Notes

- Make sure the server/database is running before executing tests
- Tests with a large number of clients may take more time
- Results may vary depending on system load and hardware
- It is recommended to run each test multiple times to get average values
- For best performance with multiple workers, use shared memory or PostgreSQL storage
- Disk storage is recommended for single-worker deployments or when persistence is required
- For PostgreSQL counter, always use `--do-retries True` with `serializable_update` method for correctness
- The `lost_update` method (PostgreSQL) and `no_lock` method (Hazelcast) are intentionally incorrect and should only be used to demonstrate concurrency problems
- For Hazelcast `atomic` method, start the cluster with `hazelcast-cp.yaml` (uncomment config in docker-compose)

---

## Troubleshooting

### Connection Error (Web Counter)

If you get a connection error, make sure:
- The server is running (`docker-compose ps` or check server logs)
- Port 8080 is available and not blocked by firewall
- You're using the correct `--counter-host` and `--counter-port` parameters
- Docker container is running if using Docker Compose

### Connection Error (PostgreSQL Counter)

If you get a PostgreSQL connection error, make sure:
- PostgreSQL is running (`docker-compose ps` in `postgresql_counter` directory)
- Database credentials are correct (check environment variables)
- Port 5432 is available and not blocked by firewall
- Database `counter_db` exists (created automatically on first run)

### Connection Error (Hazelcast Counter)

If you get a Hazelcast connection error, make sure:
- The Hazelcast cluster is running (`docker-compose ps` in `hazelcast_counter` directory)
- `counter_network` exists: `docker network create counter_network`
- `HZ_CLUSTER_MEMBERS` matches your members (default: `127.0.0.1:5701,127.0.0.1:5702,127.0.0.1:5703`)
- Ports 5701–5703 are not blocked by firewall
- For `--method atomic`, the cluster is started with CP Subsystem (`hazelcast-cp.yaml` mounted and enabled in docker-compose)

### Incorrect Count Value

If `final_count` doesn't match the expected value:

**For Web Counter:**
- Check server logs for errors or warnings
- Make sure `/reset` was called before the test (the script does this automatically)
- Check if there are no other clients simultaneously using the server
- Verify that file locking is working correctly (check for lock file permissions)
- For shared memory mode, ensure all workers can access the shared memory segment
- For PostgreSQL mode, check database connection and table initialization

**For PostgreSQL Counter:**
- If using `lost_update` method, incorrect count is expected (this demonstrates the problem)
- If using `serializable_update`, ensure `--do-retries True` is set
- Check PostgreSQL logs for errors or serialization failures
- Verify database connection and table initialization
- Ensure sufficient database resources (connections, memory)

**For Hazelcast Counter:**
- If using `no_lock` method, incorrect count is expected (demonstrates lost updates)
- For `atomic` method, ensure the cluster is started with CP Subsystem (`hazelcast-cp.yaml`)
- Check that all cluster members are reachable and the client can connect
- For `optimistic`, high contention may cause many retries; consider `pessimistic` or `atomic`

### Performance Issues

If RPS is lower than expected:

**For Web Counter:**
- Increase the number of workers (`WORKERS` environment variable)
- Use shared memory or PostgreSQL storage instead of disk storage
- Check system resources (CPU, memory, disk I/O)
- Monitor server logs for errors or warnings
- Consider network latency if testing against a remote server

**For PostgreSQL Counter:**
- Use `inplace_update` method for best performance
- Ensure PostgreSQL is properly configured (connections, memory)
- Check for serialization failures in logs (may indicate need for retries)
- Consider database connection pooling if applicable

**For Hazelcast Counter:**
- Use `atomic` method (with CP Subsystem) for best performance and correctness
- Use `pessimistic` as default when CP is not enabled
- Ensure the cluster has enough resources and low network latency

### Shared Memory Issues

If you encounter shared memory errors:
- Ensure the system supports shared memory (most Unix-like systems do)
- Check `/dev/shm` is available and has sufficient space
- Verify file permissions for `/tmp/web_counter_shared_memory.lock`
- Try using disk storage or PostgreSQL as an alternative

### PostgreSQL Issues

If you encounter PostgreSQL errors:
- Check PostgreSQL logs: `docker-compose logs postgresql` (in `postgresql_counter` directory)
- Verify database is accessible: `psql -h localhost -U postgres -d counter_db`
- Check table exists: `SELECT * FROM user_counter;`
- Ensure sufficient database connections (check `max_connections` setting)
- For serialization errors, use `--do-retries True` flag

### Hazelcast Issues

If you encounter Hazelcast errors:
- Check member logs: `docker-compose logs` (in `hazelcast_counter` directory)
- Ensure `counter_network` exists and containers are on it
- For CP Subsystem (`atomic` method): use `hazelcast-cp.yaml` and set `cp-member-count: 3`; uncomment the config/volume in docker-compose
- For connection timeouts, increase `connection_timeout` in code or check firewall/ports
- Optimistic method can raise after max retries under heavy contention; use `pessimistic` or `atomic` for stability
