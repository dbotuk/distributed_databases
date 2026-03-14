import os
from pymongo import MongoClient, ReturnDocument, WriteConcern
from pymongo.errors import PyMongoError

COLLECTION_NAME = "user_counter"
DEFAULT_USER_ID = "1"
DEFAULT_METHOD = "find_one_and_update"
DEFAULT_WRITE_CONCERN = 1


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


def _get_coll(client, db_name, write_concern=None):
    if write_concern is None:
        return client[db_name][COLLECTION_NAME]
    return client[db_name].get_collection(
        COLLECTION_NAME,
        write_concern=WriteConcern(w=write_concern),
    )


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


def increment(user_id: str, conn, method: str = DEFAULT_METHOD, write_concern=DEFAULT_WRITE_CONCERN) -> int:
    client, db_name = conn
    if client is None or db_name is None:
        return 0
    try:
        coll = _get_coll(client, db_name, write_concern=write_concern)
        if method == "find_one_and_update":
            doc = coll.find_one_and_update(
                {"user_id": user_id},
                {"$inc": {"counter": 1}},
                return_document=ReturnDocument.AFTER,
            )
            return 1 if doc else 0

        result = coll.update_one(
            {"user_id": user_id},
            {"$inc": {"counter": 1}},
        )
        return 1 if result.modified_count else 0
    except PyMongoError:
        return 0
