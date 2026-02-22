import os
from pymongo import MongoClient
from pymongo.errors import PyMongoError

COLLECTION_NAME = "user_counter"
DEFAULT_USER_ID = "1"


def get_connection():
    host = os.getenv("MONGO_HOST", "localhost")
    port = int(os.getenv("MONGO_PORT", "27017"))
    db_name = os.getenv("MONGO_DB", "counter_db")
    uri = os.getenv("MONGO_URI") or f"mongodb://{host}:{port}/"
    client = MongoClient(uri)
    return client, db_name


def close_connection(conn):
    client, _ = conn
    if client:
        client.close()


def _get_coll(client, db_name):
    return client[db_name][COLLECTION_NAME]


def init_user_counter_table(user_id: str, conn):
    client, db_name = conn
    if client is None or db_name is None:
        return False
    try:
        coll = _get_coll(client, db_name)
        coll.drop()
        coll.insert_one({
            "user_id": user_id,
            "counter": 0
        })
        return True
    except PyMongoError:
        return False


def get_user_counter(user_id: str, conn) -> int:
    client, db_name = conn
    if client is None or db_name is None:
        return 0
    try:
        coll = _get_coll(client, db_name)
        doc = coll.find_one({"user_id": user_id})
        return doc["counter"] if doc else 0
    except (PyMongoError, KeyError):
        return 0


def increment(user_id: str, conn) -> int:
    client, db_name = conn
    if client is None or db_name is None:
        return 0
    try:
        coll = _get_coll(client, db_name)
        result = coll.update_one(
            {"user_id": user_id},
            {"$inc": {"counter": 1}},
        )
        return 1 if result.modified_count else 0
    except PyMongoError:
        return 0
