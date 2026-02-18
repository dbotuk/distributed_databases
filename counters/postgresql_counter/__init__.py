# Make postgresql_counter a package
from .postgresql_counter import (
    init_user_counter_table,
    get_user_counter,
    increment_user_counter,
    get_connection,
    close_connection
)

__all__ = [
    'init_user_counter_table',
    'get_user_counter',
    'increment_user_counter',
    'get_connection',
    'close_connection',
]
