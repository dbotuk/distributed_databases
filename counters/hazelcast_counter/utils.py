from .hazelcast_counter import get_connection, close_connection, reset_counter, get_count, increment


def get_functions():
    return {
        "setup": lambda params: get_connection(),
        "shutdown": lambda params: close_connection(client=params['connection']),
        "reset": lambda params: reset_counter(client=params.get('connection', None), method=params.get('method', None)),
        "count": lambda params: get_count(client=params.get('connection', None), method=params.get('method', None)),
        "increment": lambda params: increment(client=params.get('connection', None), method=params.get('method', None)),
    }