from .postgresql_counter import (
    get_connection,
    close_connection,
    init_user_counter_table,
    get_user_counter,
    increment_user_counter
)

def get_functions():
    return {
        "setup": lambda params: get_connection(),
        "shutdown": lambda params: close_connection(client=params['connection']),
        "reset": lambda params: init_user_counter_table("1", params.get('connection', None), params.get('method', None)),
        "count": lambda params: get_user_counter("1", params.get('connection', None), params.get('method', None)),
        "increment": lambda params: increment_user_counter("1", params.get('connection', None), params.get('method', None), params.get('do_retries', False))
    }