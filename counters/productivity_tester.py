import os
import sys
import time
import logging
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from web_counter.utils import get_functions as get_web_counter_functions
from postgresql_counter.utils import get_functions as get_postgresql_counter_functions

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def get_counter_functions(counter_type: str, params = None):
    if counter_type == "web":
        return get_web_counter_functions()
    elif counter_type == "postgresql":
        return get_postgresql_counter_functions()
    else:
        raise ValueError(f"Invalid counter type: {counter_type}")

def run_performance_test(counter_type: str, n_clients: int, n_calls_per_client: int, params: dict = None):
    functions = get_counter_functions(counter_type)
    logger.info(f"Starting performance test {counter_type}: {n_clients} clients, {n_calls_per_client} calls per client")

    try:
        logger.info(f"Resetting counter")
        functions["reset"](params)
        logger.info(f"Counter reset successfully")
    except Exception as e:
        logger.error(f"Failed to reset counter: {e}")
        return 0, 0, 0, 0
    
    try:
        initial_count = functions["count"](params)
        logger.info(f"Initial count: {initial_count}")
    except Exception as e:
        logger.error(f"Failed to get initial count: {e}")
        initial_count = 0
    
    def client_worker(client_id: int):
        success_count = 0
        logger.info(f"Client {client_id} started making {n_calls_per_client} requests")
        
        for i in range(n_calls_per_client):
            try:
                successful = functions["increment"](params)
                if successful:
                    success_count += 1

                if (i + 1) % max(1, n_calls_per_client // 10) == 0:
                    logger.info(f"Client {client_id} progress: {i+1}/{n_calls_per_client} requests completed")
            except Exception as e:
                logger.warning(f"Client {client_id}, call {i+1} failed: {e}")
        
        logger.info(f"Client {client_id} completed {success_count}/{n_calls_per_client} calls")
        sys.stdout.flush()
        return success_count
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=n_clients) as executor:
        futures = [
            executor.submit(client_worker, client_id)
            for client_id in range(n_clients)
        ]
        
        total_successful_calls = 0
        for future in as_completed(futures):
            try:
                success_count = future.result()
                total_successful_calls += success_count
            except Exception as e:
                logger.error(f"Client task failed: {e}")
    
    end_time = time.time()
    total_time = end_time - start_time
    
    try:
        final_count = functions["count"](params)
        logger.info(f"Final count: {final_count}")
    except Exception as e:
        logger.error(f"Failed to get final count: {e}")
        final_count = initial_count
    
    count_increase = final_count - initial_count
    expected_count = n_clients * n_calls_per_client
    
    requests_per_second = expected_count / total_time if total_time > 0 else 0
    
    logger.info(f"Performance test completed {counter_type}:")
    logger.info(f"  Clients: {n_clients}")
    logger.info(f"  Calls per client: {n_calls_per_client}")
    logger.info(f"  Expected count increase: {expected_count}")
    logger.info(f"  Actual count increase: {count_increase}")
    logger.info(f"  Total time: {total_time:.2f}s")
    logger.info(f"  Requests per second: {requests_per_second:.2f}")
    sys.stdout.flush()
    
    return count_increase, total_time, requests_per_second, final_count


def main():
    parser = argparse.ArgumentParser(
        description='Performance tester for web counter application',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
  Examples:
  # Test with 1 client making 10000 calls
  python productivity_tester.py --counter-type web --n-clients 1 --n-calls-per-client 10000
  
  # Test with 10 clients making 10000 calls each
  python productivity_tester.py --counter-type web --n-clients 10 --n-calls-per-client 10000
  
  # Test with custom counter host and port
  python productivity_tester.py --counter-type web --n-clients 5 --n-calls-per-client 10000 --counter-host localhost --counter-port 8080
        """
    )
    
    parser.add_argument(
        '--counter-type',
        type=str,
        required=True,
        help='Type of counter to use'
    )
    
    parser.add_argument(
        '--n-clients',
        type=int,
        required=True,
        help='Number of concurrent clients'
    )
    
    parser.add_argument(
        '--n-calls-per-client',
        type=int,
        required=True,
        help='Number of calls each client should make'
    )
    
    parser.add_argument(
        '--counter-host',
        type=str,
        default=os.getenv('COUNTER_HOST', 'localhost'),
        help='Host of the web counter service (default: localhost or COUNTER_HOST env var)'
    )
    
    parser.add_argument(
        '--counter-port',
        type=int,
        default=int(os.getenv('COUNTER_PORT', '8080')),
        help='Port of the web counter service (default: 8080 or COUNTER_PORT env var)'
    )

    parser.add_argument(
        '--method',
        type=str,
        default=None,
        help='Method to use for the postgresql counter'
    )

    parser.add_argument(
        '--do-retries',
        type=bool,
        default=False,
        help='Do retries for the PostgreSQL counter'
    )
    
    args = parser.parse_args()

    params = {}
    if args.counter_type == "web":
        if args.counter_host:
            params['counter_host'] = args.counter_host
        if args.counter_port:
            params['counter_port'] = args.counter_port
    if args.counter_type == "postgresql":
        if args.method:
            params['method'] = args.method
        if args.do_retries:
            params['do_retries'] = args.do_retries

    count_increase, total_time, requests_per_second, final_count = run_performance_test(
        counter_type=args.counter_type,
        n_clients=args.n_clients,
        n_calls_per_client=args.n_calls_per_client,
        params=params
    )
    
    print("\n" + "="*60)
    print("PERFORMANCE TEST RESULTS")
    print("="*60)
    print(f"Number of clients:           {args.n_clients}")
    print(f"Calls per client:            {args.n_calls_per_client}")
    print(f"Total time (seconds):        {total_time:.2f}")
    print(f"Requests per second (RPS):   {requests_per_second:.2f}")
    print(f"Final count:                 {final_count}")
    print("="*60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
