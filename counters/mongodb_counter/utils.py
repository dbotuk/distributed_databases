from .mongodb_counter import (
    get_connection,
    close_connection,
    init_user_counter_table,
    get_user_counter,
    increment,
)

DEFAULT_USER_ID = "1"

def get_functions():
    return {
        "setup": lambda params: get_connection(),
        "shutdown": lambda params: close_connection(params.get("connection")),
        "reset": lambda params: init_user_counter_table(DEFAULT_USER_ID, params.get("connection")),
        "count": lambda params: get_user_counter(DEFAULT_USER_ID, params.get("connection")),
        "increment": lambda params: increment(DEFAULT_USER_ID, params.get("connection")),
    }
