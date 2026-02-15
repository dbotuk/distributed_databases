from .postgresql_counter import (
    init_user_counter_table,
    get_user_counter,
    increment_user_counter
)

def get_functions():
    return {
        "reset": lambda params: init_user_counter_table("1", params.get('method', None)),
        "count": lambda params: get_user_counter("1", params.get('method', None)),
        "increment": lambda params: increment_user_counter("1", params.get('method', None), params.get('do_retries', False))
    }