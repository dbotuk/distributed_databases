import logging
import os
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)
COUNTER_LABEL = "Counter"
COUNTER_ID = "default"


def get_connection():
    uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    _ensure_counter_constraint(driver)
    return driver


def _ensure_counter_constraint(driver):
    with driver.session() as session:
        session.run(
            "CREATE CONSTRAINT counter_id_unique IF NOT EXISTS "
            "FOR (c:Counter) REQUIRE c.id IS UNIQUE"
        )


def close_connection(conn):
    if conn is not None:
        try:
            conn.close()
        except Exception as e:
            logger.debug("close_connection: %s", e)


def init_counter(conn) -> bool:
    if conn is None:
        return False
    try:
        with conn.session() as session:
            session.run(
                "MERGE (c:Counter {id: $id}) SET c.value = 0",
                id=COUNTER_ID,
            )
        return True
    except Exception as e:
        logger.warning("init_counter failed: %s", e)
        return False


def get_counter(conn) -> int:
    if conn is None:
        return 0
    try:
        with conn.session() as session:
            result = session.run(
                "MATCH (c:Counter {id: $id}) RETURN c.value AS value",
                id=COUNTER_ID,
            )
            record = result.single()
            return int(record["value"]) if record and record["value"] is not None else 0
    except Exception as e:
        logger.debug("get_counter failed: %s", e)
        return 0


def increment(conn) -> int:
    if conn is None:
        return 0
    try:
        with conn.session() as session:
            session.run(
                "MERGE (c:Counter {id: $id}) "
                "ON CREATE SET c.value = 1 "
                "ON MATCH SET c.value = c.value + 1",
                id=COUNTER_ID,
            )
        return 1
    except Exception as e:
        logger.warning("increment failed: %s", e)
        return 0
