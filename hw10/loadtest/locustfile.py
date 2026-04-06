import csv
import os
import random
import time
from collections import deque
from threading import Lock

from locust import HttpUser, task, between, events


TARGET_MODE = os.getenv("TARGET_MODE", "leader-follower")
LEADER_URL = os.getenv("LEADER_URL", "http://localhost:8081")
NODE_URLS = os.getenv(
    "NODE_URLS",
    "http://localhost:8081,http://localhost:8082,http://localhost:8083,http://localhost:8084,http://localhost:8085",
).split(",")

WRITE_RATIO = float(os.getenv("WRITE_RATIO", "0.10"))
KEYSPACE_SIZE = int(os.getenv("KEYSPACE_SIZE", "50"))
HOT_KEY_WINDOW = int(os.getenv("HOT_KEY_WINDOW", "20"))
RESULT_PREFIX = os.getenv("RESULT_PREFIX", "results/run")

STALE_LOG_PATH = f"{RESULT_PREFIX}_stale_reads.csv"
INTERVAL_LOG_PATH = f"{RESULT_PREFIX}_read_write_intervals.csv"

expected_versions = {}
expected_lock = Lock()

recent_keys = deque(maxlen=HOT_KEY_WINDOW)
recent_keys_lock = Lock()

stale_log_lock = Lock()
interval_log_lock = Lock()


def choose_random_node():
    return random.choice(NODE_URLS)


def choose_write_target():
    if TARGET_MODE == "leader-follower":
        return LEADER_URL
    return choose_random_node()


def choose_key_for_write():
    return f"key-{random.randint(1, KEYSPACE_SIZE)}"


def choose_key_for_read():
    with recent_keys_lock:
        if recent_keys and random.random() < 0.7:
            return random.choice(list(recent_keys))
    return f"key-{random.randint(1, KEYSPACE_SIZE)}"


def remember_recent_key(key: str):
    with recent_keys_lock:
        recent_keys.append(key)


def update_expected_version(key: str, value: str, version: int):
    with expected_lock:
        expected_versions[key] = {
            "value": value,
            "version": version,
            "write_ts_ms": int(time.time() * 1000),
        }


def get_expected(key: str):
    with expected_lock:
        return expected_versions.get(key)


def append_csv_row(path: str, lock: Lock, row: list[str]):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with lock:
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)


def log_stale_read(key: str, node_url: str, observed_version, expected_version):
    append_csv_row(
        STALE_LOG_PATH,
        stale_log_lock,
        [str(int(time.time() * 1000)), key, node_url, str(observed_version), str(expected_version)],
    )


def log_read_write_interval(key: str, delta_ms: int):
    append_csv_row(
        INTERVAL_LOG_PATH,
        interval_log_lock,
        [str(int(time.time() * 1000)), key, str(delta_ms)],
    )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    os.makedirs(os.path.dirname(STALE_LOG_PATH) or ".", exist_ok=True)

    with open(STALE_LOG_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_ms", "key", "node_url", "observed_version", "expected_version"])

    with open(INTERVAL_LOG_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_ms", "key", "delta_ms"])


class KVUser(HttpUser):
    wait_time = between(0.01, 0.05)
    host = "http://localhost"

    @task
    def mixed_workload(self):
        if random.random() < WRITE_RATIO:
            self.do_write()
        else:
            self.do_read()

    def do_write(self):
        key = choose_key_for_write()
        value = f"value-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"
        target = choose_write_target()

        with self.client.put(
            f"{target}/kv/{key}",
            json={"value": value},
            name="PUT /kv/{key}",
            catch_response=True,
        ) as resp:
            if resp.status_code != 201:
                resp.failure(f"unexpected status={resp.status_code} body={resp.text}")
                return

            try:
                body = resp.json()
            except Exception as e:
                resp.failure(f"invalid json: {e}")
                return

            version = body.get("version")
            if version is None:
                resp.failure("missing version in write response")
                return

            update_expected_version(key, value, int(version))
            remember_recent_key(key)
            resp.success()

    def do_read(self):
        key = choose_key_for_read()
        target = choose_random_node()
        expected = get_expected(key)

        with self.client.get(
            f"{target}/kv/{key}",
            name="GET /kv/{key}",
            catch_response=True,
        ) as resp:
            if resp.status_code == 404:
                if expected is not None:
                    log_stale_read(key, target, "missing", expected["version"])
                resp.success()
                return

            if resp.status_code != 200:
                resp.failure(f"unexpected status={resp.status_code} body={resp.text}")
                return

            try:
                body = resp.json()
            except Exception as e:
                resp.failure(f"invalid json: {e}")
                return

            observed_version = int(body.get("version", -1))

            if expected is not None:
                expected_version = int(expected["version"])
                delta_ms = int(time.time() * 1000) - int(expected["write_ts_ms"])
                log_read_write_interval(key, delta_ms)

                if observed_version < expected_version:
                    log_stale_read(key, target, observed_version, expected_version)

            remember_recent_key(key)
            resp.success()