import logging
import os
from cassandra.cluster import Cluster
from cassandra import ConsistencyLevel
from cassandra.policies import WhiteListRoundRobinPolicy, AddressTranslator

logger = logging.getLogger(__name__)
KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "keyspace_rf3")
TABLE_NAME = os.getenv("CASSANDRA_COUNTER_TABLE", "likes_counter")
DEFAULT_USER_ID = "1"


class ContactPointTranslator(AddressTranslator):
    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port

    def translate(self, addr):
        return (self._host, self._port)


def get_connection():
    host = os.getenv("CASSANDRA_HOST", "localhost")
    port = int(os.getenv("CASSANDRA_PORT", "9042"))
    consistency_name = os.getenv("CASSANDRA_CONSISTENCY", "ONE").upper()
    consistency = getattr(ConsistencyLevel, consistency_name, ConsistencyLevel.ONE)
    contact_points = [host]
    cluster = Cluster(
        contact_points=contact_points,
        port=port,
        load_balancing_policy=WhiteListRoundRobinPolicy(contact_points),
        protocol_version=5,
        address_translator=ContactPointTranslator(host, port),
    )
    bootstrap = cluster.connect()
    try:
        cluster.refresh_schema_metadata()
        bootstrap.execute(
            f"CREATE TABLE IF NOT EXISTS {KEYSPACE}.{TABLE_NAME} ("
            "user_id text PRIMARY KEY, "
            "counter counter"
            ")"
        )
        cluster.refresh_schema_metadata()
    finally:
        bootstrap.shutdown()
    session = cluster.connect(KEYSPACE)
    return cluster, session, consistency


def close_connection(conn):
    if conn is None:
        return
    cluster = conn[0]
    if cluster:
        cluster.shutdown()


def init_user_counter_table(conn) -> bool:
    if conn is None:
        return False
    try:
        _, session, _ = conn
        session.execute(f"TRUNCATE {TABLE_NAME}")
        return True
    except Exception:
        return False


def get_user_counter(user_id: str, conn) -> int:
    if conn is None:
        return 0
    try:
        _, session, consistency = conn
        statement = session.prepare(
            f"SELECT counter FROM {KEYSPACE}.{TABLE_NAME} WHERE user_id = ?"
        )
        statement.consistency_level = consistency
        row = session.execute(statement, (user_id,)).one()
        return int(row.counter) if row and row.counter is not None else 0
    except Exception as e:
        logger.debug("get_user_counter failed: %s", e)
        return 0


def increment(user_id: str, conn) -> int:
    if conn is None:
        return 0
    try:
        _, session, consistency = conn
        statement = session.prepare(
            f"UPDATE {KEYSPACE}.{TABLE_NAME} SET counter = counter + 1 WHERE user_id = ?"
        )
        statement.consistency_level = consistency
        session.execute(statement, (user_id,))
        return 1
    except Exception as e:
        logger.warning("increment failed: %s", e)
        return 0
