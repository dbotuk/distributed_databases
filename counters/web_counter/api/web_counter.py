import os
import asyncio
import fcntl
import time
import struct
from pathlib import Path
from pydantic import BaseModel
from multiprocessing import shared_memory
import psycopg2
import psycopg2.errors
from fastapi import FastAPI
import uvicorn

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebCounterResponse(BaseModel):
    count: int

_counter_instance = None

def get_counter_instance():
    global _counter_instance
    if _counter_instance is None:
        host = os.getenv('HOST', '0.0.0.0')
        port = int(os.getenv('PORT', 8080))
        storage_method = os.getenv('STORAGE_METHOD', 'shared_memory')
        storage_path = os.getenv('STORAGE_PATH', '')
        storage_path = storage_path.strip() if storage_path else ''
        workers = int(os.getenv('WORKERS', '1'))
        _counter_instance = WebCounter(workers=workers, host=host, port=port, storage_method=storage_method, storage_path=storage_path)
    return _counter_instance

class WebCounter:
    def __init__(self, workers=1, host='0.0.0.0', port=8080, storage_method='shared_memory', storage_path=''):
        self.host = host
        self.port = port

        self.storage_method = storage_method
        self.workers = workers
        
        if self.storage_method == "disk":
            logger.info(f"Using disk storage: {storage_path}")
        elif self.storage_method == "shared_memory":
            logger.info(f"Using in-memory storage with shared memory")
        elif self.storage_method == "postgresql":
            logger.info(f"Using PostgreSQL storage")
        elif self.storage_method == "hazelcast":
            logger.info("Using Hazelcast IAtomicLong storage (CP Subsystem / Raft)")

        if self.storage_method == "disk":
            self.storage_path = Path(storage_path)
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize_from_disk()
            self.shared_mem = None
            self.shared_mem_name = None
        elif self.storage_method == "shared_memory":
            self.shared_mem_name = "web_counter_shared"
            self._initialize_shared_memory()
            self.storage_path = None
        elif self.storage_method == "postgresql":
            self.user_id = "1"
            self._initialize_postgresql(self.user_id)
            self.storage_path = None
        elif self.storage_method == "hazelcast":
            self._atomic_long = None
            self.hz_client = None
            self._initialize_hazelcast()
            self.storage_path = None
            self.shared_mem = None
            self.shared_mem_name = None

        self.app = FastAPI(
            title="Web Counter FastAPI Server",
            description="A Web Counter FastAPI server for counting web requests",
            version="1.0.0"
        )
        self.setup_routes()

    async def _read_value(self) -> int:
        if self.storage_method == "disk":
            return await asyncio.to_thread(self._read_from_disk)
        elif self.storage_method == "shared_memory":
            return await asyncio.to_thread(self._read_from_shared_memory)
        elif self.storage_method == "postgresql":
            return await asyncio.to_thread(self._read_from_postgresql, self.user_id)
        elif self.storage_method == "hazelcast":
            return await asyncio.to_thread(self._read_from_hazelcast)
        return 0

    async def _write_value(self, value: int):
        if self.storage_method == "disk":
            logger.info(f"Writing value to disk: {value}")
            await asyncio.to_thread(self._write_to_disk, value)
        elif self.storage_method == "shared_memory":
            logger.info(f"Writing value to shared memory: {value}")
            await asyncio.to_thread(self._write_to_shared_memory, value)
        elif self.storage_method == "postgresql":
            logger.info(f"Writing value to PostgreSQL: {value}")
            await asyncio.to_thread(self._write_to_postgresql, self.user_id, value)
        elif self.storage_method == "hazelcast":
            logger.info(f"Writing value to Hazelcast IAtomicLong: {value}")
            await asyncio.to_thread(self._write_to_hazelcast, value)

    def _read_from_shared_memory(self):
        return struct.unpack_from('q', self.shared_mem.buf, 0)[0]
    
    def _write_to_shared_memory(self, value: int):
        struct.pack_into('q', self.shared_mem.buf, 0, value)
    
    def _read_from_hazelcast(self) -> int:
        return self._atomic_long.get()

    def _write_to_hazelcast(self, value: int):
        self._atomic_long.set(value)
    
    def _increment_shared_memory(self) -> int:
        lock_file_path = Path('/tmp/web_counter_shared_memory.lock')
        max_retries = 10
        retry_delay = 0.001
        
        for attempt in range(max_retries):
            try:
                lock_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(lock_file_path, 'w') as lock_file:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                    try:
                        current = struct.unpack_from('q', self.shared_mem.buf, 0)[0]
                        new_value = current + 1
                        struct.pack_into('q', self.shared_mem.buf, 0, new_value)
                        return new_value
                    finally:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except (IOError, OSError) as e:
                logger.warning(f"Error acquiring file lock (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    logger.error("Failed to acquire lock after all retries, proceeding without lock")
                    current = struct.unpack_from('q', self.shared_mem.buf, 0)[0]
                    new_value = current + 1
                    struct.pack_into('q', self.shared_mem.buf, 0, new_value)
                    return new_value
            except Exception as e:
                logger.error(f"Unexpected error in shared memory increment: {e}")
                current = struct.unpack_from('q', self.shared_mem.buf, 0)[0]
                new_value = current + 1
                struct.pack_into('q', self.shared_mem.buf, 0, new_value)
                return new_value
        
        current = struct.unpack_from('q', self.shared_mem.buf, 0)[0]
        new_value = current + 1
        struct.pack_into('q', self.shared_mem.buf, 0, new_value)
        return new_value

    def _read_from_disk(self) -> int:
        if self.storage_path is None:
            return 0
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    try:
                        content = f.read().strip()
                        if content:
                            return int(content)
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return 0
        except (ValueError, IOError, OSError) as e:
            logger.error(f"Error reading from disk: {e}")
            return 0

    def _write_to_disk(self, value: int):
        if self.storage_path is None:
            return
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(str(value))
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except IOError as e:
            logger.error(f"Error writing to disk: {e}")

    def _increment_disk(self) -> int:
        if self.storage_path is None:
            return 0
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.storage_path.exists():
                    file_mode = 'r+'
                else:
                    file_mode = 'w+'
                
                with open(self.storage_path, file_mode) as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    try:
                        f.seek(0)
                        content = f.read().strip()
                        current_count = int(content) if content else 0
                        
                        new_count = current_count + 1
                        
                        f.seek(0)
                        f.truncate(0)
                        f.write(str(new_count))
                        f.flush()
                        os.fsync(f.fileno())
                        
                        return new_count
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except FileNotFoundError:
                if attempt < max_retries - 1:
                    continue
                else:
                    logger.error("File not found after multiple attempts")
                    return 0
            except (ValueError, IOError, OSError) as e:
                logger.error(f"Error in increment (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.001 * (attempt + 1))
                    continue
                else:
                    try:
                        with open(self.storage_path, 'w') as f:
                            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                            try:
                                f.write('1')
                                f.flush()
                                os.fsync(f.fileno())
                                return 1
                            finally:
                                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except IOError as e2:
                        logger.error(f"Failed to create counter file: {e2}")
                        return 0
        
        return 0
    
    def _get_db_connection(self):
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('POSTGRES_DB', 'counter_db')
        db_user = os.getenv('POSTGRES_USER', 'postgres')
        db_password = os.getenv('POSTGRES_PASSWORD', 'postgres')
        
        return psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )

    def _read_from_postgresql(self, user_id: str) -> int:
        conn = None
        cursor = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT counter FROM user_counter WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            conn.commit()
            
            if result is None:
                return 0
            return result[0]
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Error reading from PostgreSQL: {e}")
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _write_to_postgresql(self, user_id: str, value: int):
        conn = None
        cursor = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE user_counter SET counter = %s WHERE user_id = %s", (value, user_id))
            conn.commit()
            logger.info(f"Updated counter value to: {value}")
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Error writing to PostgreSQL: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _increment_postgresql(self, user_id: str) -> int:
        conn = None
        cursor = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("UPDATE user_counter SET counter = counter + 1 WHERE user_id = %s RETURNING counter", (user_id,))
            result = cursor.fetchone()
            conn.commit()
            
            if result:
                new_value = result[0]
                logger.info(f"Incremented counter to: {new_value}")
                return new_value
            else:
                logger.error(f"UPDATE did not affect any rows for user_id={user_id}. Row may not exist.")
                raise ValueError(f"Counter row not found for user_id={user_id}")
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Error incrementing in PostgreSQL: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _increment_hazelcast(self) -> int:
        return self._atomic_long.increment_and_get()

    def _initialize_from_disk(self):
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    content = f.read().strip()
                    if content:
                        pass
        except (ValueError, IOError, OSError) as e:
            logger.warning(f"Could not read initial value from disk: {e}")
    
    def _initialize_shared_memory(self):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.shared_mem = shared_memory.SharedMemory(name=self.shared_mem_name, create=False)
                logger.info(f"Attached to existing shared memory: {self.shared_mem_name}")
                break
            except FileNotFoundError:
                try:
                    self.shared_mem = shared_memory.SharedMemory(name=self.shared_mem_name, create=True, size=8)
                    struct.pack_into('q', self.shared_mem.buf, 0, 0)
                    logger.info(f"Created new shared memory: {self.shared_mem_name}")
                    break
                except FileExistsError:
                    if attempt < max_retries - 1:
                        time.sleep(0.01 * (attempt + 1))
                        continue
                    else:
                        try:
                            self.shared_mem = shared_memory.SharedMemory(name=self.shared_mem_name, create=False)
                            logger.info(f"Attached to existing shared memory after retry: {self.shared_mem_name}")
                            break
                        except Exception as e:
                            logger.error(f"Failed to attach to shared memory after {max_retries} attempts: {e}")
                            raise
    
    def _initialize_postgresql(self, user_id: str):
        conn = None
        cursor = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            drop_table_query = "DROP TABLE IF EXISTS user_counter;"
            cursor.execute(drop_table_query)
            
            # Create table if it doesn't exist
            create_table_query = """
            CREATE TABLE IF NOT EXISTS user_counter (
                user_id VARCHAR(255) PRIMARY KEY,
                counter INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 0
            );
            """
            cursor.execute(create_table_query)

            cursor.execute("""
                INSERT INTO user_counter (user_id, counter, version) 
                VALUES (%s, %s, %s) 
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id, 0, 0))
            
            conn.commit()
            logger.info("PostgreSQL table initialized")
        except psycopg2.errors.UniqueViolation as e:
            if conn:
                conn.rollback()
            logger.warning(f"Table or type already exists: {e}. Continuing...")
            try:
                cursor.execute("""
                    INSERT INTO user_counter (user_id, counter, version) 
                    VALUES (%s, %s, %s) 
                    ON CONFLICT (user_id) DO NOTHING
                """, (user_id, 0, 0))
                conn.commit()
            except Exception:
                pass
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to initialize PostgreSQL table: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _initialize_hazelcast(self):
        import hazelcast
        members_str = os.getenv("HZ_CLUSTER_MEMBERS", "127.0.0.1:5701,127.0.0.1:5702,127.0.0.1:5703")
        cluster_members = [m.strip() for m in members_str.split(",") if m.strip()]
        cluster_name = os.getenv("HZ_CLUSTER_NAME", "dev")
        logging.getLogger("hazelcast").setLevel(logging.ERROR)
        self.hz_client = hazelcast.HazelcastClient(
            cluster_members=cluster_members,
            cluster_name=cluster_name,
            smart_routing=False,
            connection_timeout=10.0,
            invocation_timeout=30.0,
            redo_operation=True,
        )
        atomic_long_name = os.getenv("HZ_ATOMIC_LONG_NAME", "counter")
        self._atomic_long = self.hz_client.cp_subsystem.get_atomic_long(atomic_long_name).blocking()
        logger.info("Hazelcast IAtomicLong initialized: name=%s", atomic_long_name)

    def setup_routes(self):

        @self.app.post("/reset")
        async def reset():
            if self.storage_method == "postgresql":
                await asyncio.to_thread(self._write_to_postgresql, self.user_id, 0)
            elif self.storage_method == "hazelcast":
                await asyncio.to_thread(self._write_to_hazelcast, 0)
            else:
                await self._write_value(0)
            return {"status": "ok"}

        @self.app.post("/inc")
        async def increment():
            if self.storage_method == "disk":
                new_count = await asyncio.to_thread(self._increment_disk)
                logger.info(f"Writing value to disk: {new_count}")
            elif self.storage_method == "shared_memory":
                new_count = await asyncio.to_thread(self._increment_shared_memory)
                logger.info(f"Incremented shared memory: {new_count}")
            elif self.storage_method == "postgresql":
                new_count = await asyncio.to_thread(self._increment_postgresql, self.user_id)
                logger.info(f"Incremented PostgreSQL: {new_count}")
            elif self.storage_method == "hazelcast":
                new_count = await asyncio.to_thread(self._increment_hazelcast)
                logger.info(f"Incremented Hazelcast IAtomicLong: {new_count}")

            return {"status": "ok"}

        @self.app.get("/count")
        async def get_count():
            count = await self._read_value()
            return WebCounterResponse(count=count)
    
    def run(self):
        workers = int(os.getenv('WORKERS', '1'))
        
        if workers > 1:
            logger.info(f"Starting uvicorn with {workers} workers for multithreading support")
            uvicorn.run(
                "web_counter:app",
                host=self.host, 
                port=self.port,
                workers=workers,
                loop="asyncio"
            )
        else:
            logger.info("Starting uvicorn with single worker (async support enabled)")
            uvicorn.run(
                "web_counter:app",
                host=self.host, 
                port=self.port,
                loop="asyncio"
            )


counter = get_counter_instance()
app = counter.app

if __name__ == "__main__":
    counter.run()