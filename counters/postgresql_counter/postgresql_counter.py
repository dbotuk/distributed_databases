import os
import time
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_SERIALIZABLE
from psycopg2 import errorcodes

def get_db_connection():
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


def init_user_counter_table(user_id, isolation_level=None):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if isolation_level and isolation_level == "serializable":
            conn.set_isolation_level(ISOLATION_LEVEL_SERIALIZABLE)
        cursor = conn.cursor()
        
        drop_table_query = "DROP TABLE IF EXISTS user_counter;"
        cursor.execute(drop_table_query)
        conn.commit()

        create_table_query = """
        CREATE TABLE user_counter (
            USER_ID VARCHAR(255) PRIMARY KEY,
            Counter INTEGER NOT NULL DEFAULT 0,
            Version INTEGER NOT NULL DEFAULT 0
        );
        """
        
        cursor.execute(create_table_query)

        cursor.execute("INSERT INTO user_counter (user_id, counter) VALUES (%s, %s)", (user_id, 0))

        conn.commit()
        cursor.close()
        return True
        
    except psycopg2.Error as e:
        if cursor:
            cursor.close()
        if conn:
            conn.rollback()
        return False
        
    finally:
        if conn:
            conn.close()


def get_user_counter(user_id: str, isolation_level=None) -> int:
    conn = None
    try:
        conn = get_db_connection()
        if isolation_level and isolation_level == "serializable":
            conn.set_isolation_level(ISOLATION_LEVEL_SERIALIZABLE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT counter FROM user_counter WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()

        conn.commit()
        cursor.close()
        
        if result is None:
            return 0
        return result[0]
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        
        serialization_error = (e.pgcode == '40001' or 
                             (hasattr(errorcodes, 'SERIALIZATION_FAILURE') and 
                              e.pgcode == errorcodes.SERIALIZATION_FAILURE))
        if serialization_error:
            raise
        return 0
    finally:
        if conn:
            conn.close()

def increment_user_counter(user_id: str, method=None, do_retries=False) -> int:
    MAX_RETRIES = 20 if do_retries else 1
    BASE_DELAY = 0.01 if do_retries else 0
    MAX_DELAY = 5.0 if do_retries else 0
    
    def _attempt_increment():
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            if method and method == "serializable_update":
                conn.set_isolation_level(ISOLATION_LEVEL_SERIALIZABLE)
            cursor = conn.cursor()

            if method and (method == "lost_update" or method == "serializable_update"):
                cursor.execute("SELECT counter FROM user_counter WHERE user_id = %s", (user_id,))
                counter = cursor.fetchone()
                counter = counter[0] + 1
                
                cursor.execute("UPDATE user_counter SET counter = %s WHERE user_id = %s", (counter, user_id))
                conn.commit()
            
            elif method and method == "inplace_update":
                cursor.execute("UPDATE user_counter SET counter = counter + 1 WHERE user_id = %s", (user_id,))
                conn.commit()
            
            elif method and method == "row_level_locking":
                cursor.execute("SELECT counter FROM user_counter WHERE user_id = %s FOR UPDATE", (user_id,))
                counter = cursor.fetchone()
                counter = counter[0] + 1
                
                cursor.execute("UPDATE user_counter SET counter = %s WHERE user_id = %s", (counter, user_id))
                conn.commit()
            
            elif method and method == "optimistic_concurrency_control":
                while (True):
                    cursor.execute("SELECT counter, version FROM user_counter WHERE user_id = %s", (user_id,))
                    (counter, version) = cursor.fetchone()
                    counter = counter + 1
                    cursor.execute("UPDATE user_counter SET counter = %s, version = %s WHERE user_id = %s and version = %s", (counter, version + 1, user_id, version))
                    conn.commit()
                    count = cursor.rowcount
                    if (count > 0):
                        break
            
            cursor.close()
            conn.close()
            return 1
                
        except psycopg2.Error as e:
            if cursor:
                cursor.close()
            if conn:
                conn.rollback()
                conn.close()
            
            serialization_error = (e.pgcode == '40001' or 
                                 (hasattr(errorcodes, 'SERIALIZATION_FAILURE') and 
                                  e.pgcode == errorcodes.SERIALIZATION_FAILURE))
            
            if serialization_error:
                raise
            else:
                return 0
        except Exception as e:
            if cursor:
                cursor.close()
            if conn:
                conn.rollback()
                conn.close()
            return 0
    
    for attempt in range(MAX_RETRIES):
        try:
            result = _attempt_increment()
            if result is not None:
                return result
        except psycopg2.Error as e:
            serialization_error = (e.pgcode == '40001' or 
                                 (hasattr(errorcodes, 'SERIALIZATION_FAILURE') and 
                                  e.pgcode == errorcodes.SERIALIZATION_FAILURE))
            if not do_retries:
                print(f"Serialization error occurred for user_id={user_id}: {str(e)}")
                return 0

            if serialization_error and attempt < MAX_RETRIES - 1:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                jitter = delay * 0.1 * (0.5 + (hash(f"{user_id}{attempt}") % 100) / 200.0)
                total_delay = delay + jitter
                
                time.sleep(total_delay)
            else:
                print(f"Serialization error occurred for user_id={user_id} after {MAX_RETRIES} attempts: {str(e)}")
                return 0
        except Exception as e:
            return 0
    
    return 0
