# Web Counter - Documentation and Testing Instructions

## Project Description

Web Counter is a FastAPI web server that provides an API for incrementing and retrieving a counter value. The counter supports two storage modes: shared memory (for in-memory storage with multi-worker support) or disk-based file storage. The implementation uses file locking (`fcntl`) for thread-safe operations and supports multiple worker processes.

### Architecture

- **Framework**: FastAPI with async/await support
- **Server**: Uvicorn with configurable worker processes
- **Synchronization**: File locking (`fcntl.flock`) for thread-safe operations
- **Storage Backends**:
  - **Shared Memory**: Uses `multiprocessing.shared_memory` for in-memory storage across multiple workers
  - **Disk Storage**: File-based storage with atomic read-modify-write operations

### API Endpoints

- `POST /reset` - Resets the counter to 0
- `POST /inc` - Increments the counter by 1 (thread-safe)
- `GET /count` - Returns the current counter value

### Storage Modes

#### Shared Memory Storage (Default)
- **Activation**: When `STORAGE_PATH` is not set or set as an empty string
- **Implementation**: Uses `multiprocessing.shared_memory` to share counter state across multiple worker processes
- **Locking**: File-based locking (`/tmp/web_counter_shared_memory.lock`) ensures atomic increments
- **Use Case**: Best for high-performance scenarios with multiple workers

#### Disk Storage
- **Activation**: When `STORAGE_PATH` points to a file path
- **Implementation**: Stores counter value in a text file with file locking for synchronization
- **Locking**: Uses `fcntl.flock` for exclusive locks during read-modify-write operations
- **Use Case**: Persistence across server restarts, single-worker deployments

### Environment Variables

- `HOST` - Server host (default: `0.0.0.0`)
- `PORT` - Server port (default: `8080`)
- `STORAGE_PATH` - Path to counter file (empty string for shared memory, or file path for disk storage)
- `WORKERS` - Number of uvicorn worker processes (default: `1`)

## Installation and Setup

### Option 1: Running with Docker Compose (Recommended)

1. Navigate to the `web_counter` directory:
```bash
cd web_counter
```

2. Start the server:
```bash
docker-compose up --build
```

The default configuration uses:
- **4 workers** for multi-processing support
- **Disk storage** at `/app/counter.txt`
- **Port 8080**

The server will be available at `http://localhost:8080`

#### Customizing Docker Compose Configuration

Edit `docker-compose.yml` to change settings:

```yaml
environment:
  - HOST=0.0.0.0
  - PORT=8080
  - STORAGE_PATH=/app/counter.txt  # Empty string for shared memory
  - WORKERS=4                       # Number of worker processes
```

To use shared memory instead of disk storage:
```yaml
environment:
  - STORAGE_PATH=  # Empty string enables shared memory
  - WORKERS=4
```

### Option 2: Running with Docker (Standalone)

Build the image:
```bash
cd web_counter
docker build -t web-counter -f api/Dockerfile ..
```

Run with disk storage:
```bash
docker run -p 8080:8080 -e STORAGE_PATH=/app/counter.txt -e WORKERS=4 web-counter
```

Run with shared memory:
```bash
docker run -p 8080:8080 -e STORAGE_PATH= -e WORKERS=4 web-counter
```

### Option 3: Running without Docker

1. Install dependencies:
```bash
cd counters
pip install -r requirements.txt
```

2. Start the server:
```bash
cd web_counter/api
python web_counter.py
```

Or with environment variables:
```bash
# Shared memory mode (default)
WORKERS=4 python web_counter.py

# Disk storage mode
STORAGE_PATH=counter.txt WORKERS=1 python web_counter.py
```

## Testing

The testing script `productivity_tester.py` is located in the `counters` directory. It uses concurrent threads to simulate multiple clients making requests to the counter API.

### General Testing Command

```bash
python productivity_tester.py --counter-type web --n-clients <number_of_clients> --n-calls-per-client <calls_per_client> [--counter-host <host>] [--counter-port <port>]
```

### Parameters

- `--counter-type` - Type of counter (required, use `web` for web counter)
- `--n-clients` - Number of concurrent clients (required)
- `--n-calls-per-client` - Number of calls each client makes (required)
- `--counter-host` - Server host (default: `localhost` or `COUNTER_HOST` env var)
- `--counter-port` - Server port (default: `8080` or `COUNTER_PORT` env var)

### How Testing Works

1. The script automatically resets the counter to 0 before starting
2. Spawns `n_clients` concurrent threads, each making `n_calls_per_client` requests
3. Each client calls the `/inc` endpoint sequentially
4. After all clients complete, the script retrieves the final count
5. Reports performance metrics including RPS (requests per second)

## Test Scenarios

### Test 1: One Client, 10,000 Calls

**Expected Result**: `count = 10,000`

**Command**:
```bash
python productivity_tester.py --counter-type web --n-clients 1 --n-calls-per-client 10000
```

**Description**: One client sequentially makes 10,000 calls to `/inc`. The final counter value should equal 10,000.

**Metric**: Requests per second (RPS) for sequential calls.

---

### Test 2: Two Clients, 10,000 Calls Each

**Expected Result**: `count = 20,000`

**Command**:
```bash
python productivity_tester.py --counter-type web --n-clients 2 --n-calls-per-client 10000
```

**Description**: Two clients simultaneously make 10,000 calls each. The final counter value should equal 20,000.

**Metric**: Requests per second (RPS) for parallel calls from two clients.

---

### Test 3: Five Clients, 10,000 Calls Each

**Expected Result**: `count = 50,000`

**Command**:
```bash
python productivity_tester.py --counter-type web --n-clients 5 --n-calls-per-client 10000
```

**Description**: Five clients simultaneously make 10,000 calls each. The final counter value should equal 50,000.

**Metric**: Requests per second (RPS) for parallel calls from five clients.

---

### Test 4: Ten Clients, 10,000 Calls Each

**Expected Result**: `count = 100,000`

**Command**:
```bash
python productivity_tester.py --counter-type web --n-clients 10 --n-calls-per-client 10000
```

**Description**: Ten clients simultaneously make 10,000 calls each. The final counter value should equal 100,000.

**Metric**: Requests per second (RPS) for parallel calls from ten clients.

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

- **Final count** should equal `n_clients * n_calls_per_client`
- If the value doesn't match, it may indicate:
  - Synchronization issues (race conditions)
  - Lost requests due to network errors
  - Server errors during processing

## Storage Mode Comparison

It is recommended to run all tests in both modes to compare performance:

1. **Shared Memory Storage** (`STORAGE_PATH` not set or empty string)
   - Faster for high-throughput scenarios
   - Better for multi-worker deployments
   - Counter is lost on server restart

2. **Disk Storage** (`STORAGE_PATH=/app/counter.txt` or any file path)
   - Persists across server restarts
   - Slightly slower due to disk I/O
   - Better for single-worker deployments or when persistence is required

### Performance Considerations

- **Multiple Workers**: Use `WORKERS=4` or higher for better throughput with shared memory
- **Single Worker**: Use `WORKERS=1` for disk storage to avoid file locking contention
- **Shared Memory**: Generally 2-5x faster than disk storage for high-concurrency scenarios

## Complete Testing Workflow Example

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

## Project Structure

```
counters/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── productivity_tester.py      # Performance testing script
└── web_counter/
    ├── docker-compose.yml       # Docker Compose configuration
    └── api/
        ├── Dockerfile           # Docker image definition
        └── web_counter.py       # Main FastAPI application
    └── utils.py                 # HTTP client utilities
```

## Technical Details

### Synchronization Mechanism

The implementation uses file locking (`fcntl.flock`) to ensure thread-safe operations:

- **Shared Memory Mode**: Uses a lock file at `/tmp/web_counter_shared_memory.lock` to synchronize access to shared memory
- **Disk Storage Mode**: Uses exclusive file locks on the counter file during read-modify-write operations
- **Retry Logic**: Both modes include retry mechanisms with exponential backoff for lock acquisition

### Error Handling

- Automatic retry on lock acquisition failures
- Graceful degradation if locks cannot be acquired
- Comprehensive logging for debugging
- Error recovery for file I/O operations

## Notes

- Make sure the server is running before executing tests
- Tests with a large number of clients may take more time
- Results may vary depending on system load and hardware
- It is recommended to run each test multiple times to get average values
- For best performance with multiple workers, use shared memory storage
- Disk storage is recommended for single-worker deployments or when persistence is required

## Troubleshooting

### Connection Error

If you get a connection error, make sure:
- The server is running (`docker-compose ps` or check server logs)
- Port 8080 is available and not blocked by firewall
- You're using the correct `--counter-host` and `--counter-port` parameters
- Docker container is running if using Docker Compose

### Incorrect Count Value

If `final_count` doesn't match the expected value:
- Check server logs for errors or warnings
- Make sure `/reset` was called before the test (the script does this automatically)
- Check if there are no other clients simultaneously using the server
- Verify that file locking is working correctly (check for lock file permissions)
- For shared memory mode, ensure all workers can access the shared memory segment

### Performance Issues

If RPS is lower than expected:
- Increase the number of workers (`WORKERS` environment variable)
- Use shared memory storage instead of disk storage
- Check system resources (CPU, memory, disk I/O)
- Monitor server logs for errors or warnings
- Consider network latency if testing against a remote server

### Shared Memory Issues

If you encounter shared memory errors:
- Ensure the system supports shared memory (most Unix-like systems do)
- Check `/dev/shm` is available and has sufficient space
- Verify file permissions for `/tmp/web_counter_shared_memory.lock`
- Try using disk storage as an alternative