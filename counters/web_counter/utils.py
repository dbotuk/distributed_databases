import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def _session_with_retries(timeout=30, retries=3):
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=0.5,
        status_forcelist=(502, 503, 504),
        allowed_methods=["GET", "POST"],
    )
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session

def get_functions():
    def setup(params):
        params["_web_session"] = _session_with_retries()
        return None

    def shutdown(params):
        s = params.pop("_web_session", None)
        if s is not None:
            s.close()

    def _base_url(params):
        host = params.get("counter_host", "localhost")
        port = params.get("counter_port", 8080)
        return f"http://{host}:{port}"

    def reset(params):
        session = params.get("_web_session") or _session_with_retries()
        r = session.post(f"{_base_url(params)}/reset", timeout=30)
        r.raise_for_status()
        return r

    def count(params):
        session = params.get("_web_session") or _session_with_retries()
        r = session.get(f"{_base_url(params)}/count", timeout=10)
        r.raise_for_status()
        return r.json()["count"]

    def increment(params):
        import time
        session = params.get("_web_session") or _session_with_retries()
        last_error = None
        for attempt in range(4):
            try:
                r = session.post(f"{_base_url(params)}/inc", timeout=60)
                return r.status_code == 200
            except requests.exceptions.ConnectionError as e:
                last_error = e
                if attempt < 3:
                    time.sleep(0.2 * (attempt + 1))
                else:
                    raise
        raise last_error

    return {
        "setup": setup,
        "shutdown": shutdown,
        "reset": reset,
        "count": count,
        "increment": increment,
    }
