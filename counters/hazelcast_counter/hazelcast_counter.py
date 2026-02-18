import os
import logging
import hazelcast

logging.getLogger("hazelcast").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

MAP_NAME_ENV = "HZ_MAP_NAME"
COUNTER_KEY_ENV = "HZ_COUNTER_KEY"
ATOMIC_LONG_NAME_ENV = "HZ_ATOMIC_LONG_NAME"
DEFAULT_MAP_NAME = "counter-map"
DEFAULT_COUNTER_KEY = "count"
DEFAULT_ATOMIC_LONG_NAME = "counter"


def get_connection():
    members_env = os.getenv("HZ_CLUSTER_MEMBERS", "127.0.0.1:5701,127.0.0.1:5702,127.0.0.1:5703")
    cluster_members = [m.strip() for m in members_env.split(",") if m.strip()]

    cluster_name = os.getenv("HZ_CLUSTER_NAME", "dev")

    logger.info("Connecting Hazelcast client to members %s, cluster_name=%s", cluster_members, cluster_name)

    client = hazelcast.HazelcastClient(
        cluster_members=cluster_members,
        cluster_name=cluster_name,
        smart_routing=False,
        connection_timeout=10.0,
        invocation_timeout=30.0,
        redo_operation=True,
    )

    return client


def close_connection(client):
    client.shutdown()


def _get_map(client):
    map_name = os.getenv(MAP_NAME_ENV, DEFAULT_MAP_NAME)
    return client.get_map(map_name).blocking()


def _get_counter_key():
    return os.getenv(COUNTER_KEY_ENV, DEFAULT_COUNTER_KEY)


def _get_atomic_long(client):
    name = os.getenv(ATOMIC_LONG_NAME_ENV, DEFAULT_ATOMIC_LONG_NAME)
    return client.cp_subsystem.get_atomic_long(name).blocking()


def get_atomic_long(client):
    return _get_atomic_long(client)


def reset_counter(client=None, method=None):
    if method == "atomic":
        _get_atomic_long(client).set(0)
        return True
    else:
        m = _get_map(client)
        key = _get_counter_key()
        m.put(key, 0)
        return True


def get_count(client=None, method=None):
    if method == "atomic":
        return _get_atomic_long(client).get()
    else:
        m = _get_map(client)
        key = _get_counter_key()
        value = m.get(key)
        if value is None:
            value = 0
        return value


def increment_no_lock(client=None, method=None):
    m = _get_map(client)
    key = _get_counter_key()
    value = m.get(key)
    if value is None:
        value = 0
    new_value = value + 1
    m.put(key, new_value)
    return new_value


def increment_pessimistic(client=None, method=None):
    m = _get_map(client)
    key = _get_counter_key()
    m.lock(key)
    try:
        value = m.get(key)
        if value is None:
            value = 0
        new_value = value + 1
        m.put(key, new_value)
        return new_value
    finally:
        m.force_unlock(key)


def increment_optimistic(client=None, method=None):
    m = _get_map(client)
    key = _get_counter_key()
    max_attempts = 1000
    for _ in range(max_attempts):
        old_value = m.get(key)
        if old_value is None:
            old_value = 0
        new_value = old_value + 1
        if m.replace_if_same(key, old_value, new_value):
            return new_value
    raise RuntimeError(f"Optimistic increment failed after {max_attempts} attempts (contention)")


def increment_atomic_long(client=None, method=None):
    return _get_atomic_long(client).increment_and_get()


def increment(client=None, method=None):
    if method == "no_lock":
        return increment_no_lock(client=client, method=method)
    if method == "pessimistic":
        return increment_pessimistic(client=client, method=method)
    if method == "optimistic":
        return increment_optimistic(client=client, method=method)
    if method == "atomic":
        return increment_atomic_long(client=client, method=method)
    raise ValueError(f"Invalid method: {method}")

