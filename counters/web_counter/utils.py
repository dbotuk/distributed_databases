import requests

def get_functions():
    return {
        "reset": lambda params: requests.post(f"http://{params.get('counter_host', 'localhost')}:{params.get('counter_port', 8080)}/reset", timeout=30),
        "count": lambda params: requests.get(f"http://{params.get('counter_host', 'localhost')}:{params.get('counter_port', 8080)}/count", timeout=10).json()["count"],
        "increment": lambda params: requests.post(f"http://{params.get('counter_host', 'localhost')}:{params.get('counter_port', 8080)}/inc", timeout=30).status_code == 200
    }
