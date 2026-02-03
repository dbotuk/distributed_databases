import requests

def get_functions():
    return {
        "reset": lambda counter_host, counter_port: requests.post(f"http://{counter_host}:{counter_port}/reset", timeout=30),
        "count": lambda counter_host, counter_port: requests.get(f"http://{counter_host}:{counter_port}/count", timeout=10).json()["count"],
        "increment": lambda counter_host, counter_port: requests.post(f"http://{counter_host}:{counter_port}/inc", timeout=30).status_code == 200
    }
