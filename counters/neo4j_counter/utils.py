from .neo4j_counter import (
    get_connection,
    close_connection,
    init_counter,
    get_counter,
    increment,
)


def get_functions():
    return {
        "setup": lambda params: get_connection(),
        "shutdown": lambda params: close_connection(params.get("connection")),
        "reset": lambda params: init_counter(params.get("connection")),
        "count": lambda params: get_counter(params.get("connection")),
        "increment": lambda params: increment(params.get("connection")),
    }
