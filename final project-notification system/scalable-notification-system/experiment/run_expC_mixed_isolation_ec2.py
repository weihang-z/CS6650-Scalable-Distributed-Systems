import csv
import json
import random
import shlex
import signal
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


AWS_REGION = "us-east-1"
CLUSTER_NAME = "scalable-notification-system-dev-cluster"
EMAIL_SERVICE = "scalable-notification-system-dev-email-worker-service"
INAPP_SERVICE = "scalable-notification-system-dev-inapp-worker-service"
INGRESS_SERVICE = "scalable-notification-system-dev-ingress-service"
KAFKA_TAG_NAME = "scalable-notification-system-dev-kafka-ec2"
LOADGEN_TAG_NAME = "scalable-notification-system-dev-loadgen-ec2"
LOCUST_HOST = "http://scalable-notification-system-alb-2044224092.us-east-1.elb.amazonaws.com"
LOCUST_FILE = "locust/locustfile.py"
KEY_PATH = ".keys/sns-dev-20260420.pem"
SSH_USER = "ec2-user"
REMOTE_BASE_DIR = "/home/ec2-user/expC_mixed_isolation"

STEADY_USERS = "60"
STEADY_DURATION_SEC = "300"
SPAWN_RATE = "10"
PAYLOAD_BYTES = "256"
STABILIZE_SEC = 30
LAG_SAMPLE_SEC = 5
ATTEMPT_SETTLE_SEC = 60
SAMPLED_NOTIFICATION_IDS_RATE = "0.02"
SAMPLED_NOTIFICATION_IDS_LIMIT = 200
EMAIL_WORKER_REPLICAS = 1
INAPP_WORKER_REPLICAS = 1

EXPERIMENT_ROUNDS = [
    {"name": "round_1_normal", "email_latency_ms": 100, "inapp_latency_ms": 20},
    {"name": "round_2_slow_email", "email_latency_ms": 1000, "inapp_latency_ms": 20},
    {"name": "round_3_very_slow_email", "email_latency_ms": 3000, "inapp_latency_ms": 20},
]


def utc_now():
    return datetime.now(timezone.utc)


def fmt_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def log(message: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def run(cmd, cwd=None, capture_output=True, check=True):
    result = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=capture_output,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )
    return result


def aws_json(args):
    result = run(["aws", *args, "--region", AWS_REGION, "--output", "json"])
    return json.loads(result.stdout or "null")


def get_instance_public_ip(tag_name: str):
    data = aws_json([
        "ec2",
        "describe-instances",
        "--filters",
        f"Name=tag:Name,Values={tag_name}",
        "Name=instance-state-name,Values=running",
        "--query",
        "Reservations[].Instances[].PublicIpAddress",
    ])
    if not data or not data[0]:
        raise RuntimeError(f"Could not resolve current public IP for {tag_name}")
    return data[0]


def ssh_base(host: str):
    return [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "IdentitiesOnly=yes",
        "-i",
        KEY_PATH,
        f"{SSH_USER}@{host}",
    ]


def scp_base():
    return [
        "scp",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "IdentitiesOnly=yes",
        "-i",
        KEY_PATH,
    ]


def ssh_bash(host: str, script: str, check=True, capture_output=True):
    return run(
        ssh_base(host) + [f"bash -lc {shlex.quote(script)}"],
        check=check,
        capture_output=capture_output,
    )


def wait_for_ssh(host: str, label: str, timeout_sec=300):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        probe = ssh_bash(host, "echo ready", check=False)
        if probe.returncode == 0 and (probe.stdout or "").strip() == "ready":
            log(f"{label} SSH is ready")
            return
        time.sleep(5)
    raise RuntimeError(f"Timed out waiting for SSH on {label} ({host})")


def prepare_loadgen(loadgen_ip: str, remote_root: str):
    log("Waiting for load generator SSH")
    wait_for_ssh(loadgen_ip, "load generator")
    log("Ensuring remote workdir and Locust dependencies")
    ssh_bash(
        loadgen_ip,
        (
            "set -euo pipefail && "
            f"mkdir -p {remote_root} && "
            "if ! python3 -m pip show locust >/dev/null 2>&1; then "
            "sudo dnf install -y gcc gcc-c++ python3-devel libffi-devel make >/dev/null && "
            "python3 -m pip install --user locust; "
            "fi"
        ),
        capture_output=False,
    )
    log("Uploading locustfile to load generator")
    run(
        scp_base()
        + [
            LOCUST_FILE,
            f"{SSH_USER}@{loadgen_ip}:{remote_root}/locustfile.py",
        ]
    )
    log(f"Uploaded locustfile to {loadgen_ip}:{remote_root}/locustfile.py")


def get_service_description(service_name: str):
    data = aws_json([
        "ecs",
        "describe-services",
        "--cluster",
        CLUSTER_NAME,
        "--services",
        service_name,
        "--query",
        "services[0]",
    ])
    if not data:
        raise RuntimeError(f"Could not describe ECS service {service_name}")
    return data


def get_task_definition(task_definition_arn: str):
    data = aws_json([
        "ecs",
        "describe-task-definition",
        "--task-definition",
        task_definition_arn,
        "--query",
        "taskDefinition",
    ])
    if not data:
        raise RuntimeError(f"Could not describe task definition {task_definition_arn}")
    return data


def register_task_definition_with_env(service_name: str, env_updates: dict):
    service = get_service_description(service_name)
    task_definition = get_task_definition(service["taskDefinition"])
    payload = {
        key: task_definition[key]
        for key in [
            "family",
            "taskRoleArn",
            "executionRoleArn",
            "networkMode",
            "containerDefinitions",
            "volumes",
            "placementConstraints",
            "requiresCompatibilities",
            "cpu",
            "memory",
            "runtimePlatform",
            "pidMode",
            "ipcMode",
            "proxyConfiguration",
            "inferenceAccelerators",
            "ephemeralStorage",
        ]
        if key in task_definition
    }

    container = payload["containerDefinitions"][0]
    current_env = {
        entry["name"]: entry["value"]
        for entry in container.get("environment", [])
    }
    current_env.update({key: str(value) for key, value in env_updates.items()})
    container["environment"] = [
        {"name": key, "value": value}
        for key, value in current_env.items()
    ]

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as temp_file:
        json.dump(payload, temp_file)
        temp_path = temp_file.name

    try:
        result = aws_json([
            "ecs",
            "register-task-definition",
            "--cli-input-json",
            f"file://{temp_path}",
            "--query",
            "taskDefinition.taskDefinitionArn",
        ])
    finally:
        Path(temp_path).unlink(missing_ok=True)

    return result


def update_service_task_definition(service_name: str, task_definition_arn: str, desired_count: int | None = None):
    cmd = [
        "aws",
        "ecs",
        "update-service",
        "--region",
        AWS_REGION,
        "--cluster",
        CLUSTER_NAME,
        "--service",
        service_name,
        "--task-definition",
        task_definition_arn,
        "--force-new-deployment",
    ]
    if desired_count is not None:
        cmd += ["--desired-count", str(desired_count)]
    run(cmd)


def wait_for_services_stable(service_names: list[str]):
    run(
        [
            "aws",
            "ecs",
            "wait",
            "services-stable",
            "--region",
            AWS_REGION,
            "--cluster",
            CLUSTER_NAME,
            "--services",
            *service_names,
        ],
        capture_output=False,
    )
    log(f"Services are stable, waiting {STABILIZE_SEC}s extra")
    time.sleep(STABILIZE_SEC)


def configure_worker_latencies(email_latency_ms: int, inapp_latency_ms: int):
    log(
        "Updating worker task definitions with latencies "
        f"email={email_latency_ms}ms inapp={inapp_latency_ms}ms"
    )
    email_td = register_task_definition_with_env(
        EMAIL_SERVICE,
        {
            "APP_PROVIDERS_EMAIL_SIMULATED_LATENCY_MS": email_latency_ms,
        },
    )
    inapp_td = register_task_definition_with_env(
        INAPP_SERVICE,
        {
            "APP_PROVIDERS_INAPP_SIMULATED_LATENCY_MS": inapp_latency_ms,
        },
    )
    update_service_task_definition(EMAIL_SERVICE, email_td, EMAIL_WORKER_REPLICAS)
    update_service_task_definition(INAPP_SERVICE, inapp_td, INAPP_WORKER_REPLICAS)
    wait_for_services_stable([EMAIL_SERVICE, INAPP_SERVICE])


def parse_total_lag(raw: str) -> int:
    total = 0
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 6:
            continue
        if parts[0].startswith("notification.") and parts[-1].isdigit():
            total += int(parts[-1])
    return total


def lag_sampler(kafka_ip: str, group_id: str, output_csv: Path, stop_event: threading.Event):
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(["timestamp_utc", "total_lag"])
        while not stop_event.is_set():
            raw = ssh_bash(
                kafka_ip,
                (
                    "sudo docker exec kafka "
                    "kafka-consumer-groups "
                    "--bootstrap-server localhost:9092 "
                    "--describe "
                    f"--group {group_id}"
                ),
                check=False,
            )
            writer.writerow([
                fmt_ts(utc_now()),
                parse_total_lag((raw.stdout or "") + "\n" + (raw.stderr or "")),
            ])
            output_file.flush()
            stop_event.wait(LAG_SAMPLE_SEC)


def run_remote_locust(loadgen_ip: str, remote_root: str, run_dir: Path):
    remote_run_dir = f"{remote_root}/{run_dir.name}"
    csv_prefix = run_dir / "locust"
    sampled_ids_path = run_dir / "sampled_notification_ids.csv"
    log_path = run_dir / "locust.log"

    ssh_bash(loadgen_ip, f"mkdir -p {remote_run_dir}", capture_output=False)

    remote_cmd = (
        "set -euo pipefail && "
        f"cd {remote_root} && "
        f"mkdir -p {remote_run_dir} && "
        f"TEST_MODE=steady CHANNEL_MODE=MIXED STEADY_USERS={STEADY_USERS} "
        f"STEADY_DURATION_SEC={STEADY_DURATION_SEC} SPAWN_RATE={SPAWN_RATE} "
        f"PAYLOAD_BYTES={PAYLOAD_BYTES} "
        f"SAMPLED_NOTIFICATION_IDS_FILE={remote_run_dir}/sampled_notification_ids.csv "
        f"SAMPLED_NOTIFICATION_IDS_RATE={SAMPLED_NOTIFICATION_IDS_RATE} "
        "python3 -m locust "
        "-f locustfile.py "
        f"--host {LOCUST_HOST} "
        "--headless "
        f"--csv {remote_run_dir}/locust"
    )

    log(f"Starting remote Locust on {loadgen_ip}")
    with log_path.open("w") as log_file:
        proc = subprocess.Popen(
            ssh_base(loadgen_ip) + [f"bash -lc {shlex.quote(remote_cmd)}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                log_file.write(line)
                log_file.flush()
                if line.strip():
                    print(line.rstrip(), flush=True)
        finally:
            proc.wait()

    run(
        scp_base()
        + [
            f"{SSH_USER}@{loadgen_ip}:{remote_run_dir}/locust_*",
            f"{SSH_USER}@{loadgen_ip}:{remote_run_dir}/sampled_notification_ids.csv",
            str(run_dir),
        ]
    )

    if proc.returncode not in (0, 1):
        raise RuntimeError(f"Remote Locust run failed with exit code {proc.returncode}")

    return csv_prefix, sampled_ids_path


def get_metric_stats(service_name: str, metric_name: str, start: datetime, end: datetime):
    data = aws_json([
        "cloudwatch",
        "get-metric-statistics",
        "--namespace",
        "AWS/ECS",
        "--metric-name",
        metric_name,
        "--dimensions",
        f"Name=ClusterName,Value={CLUSTER_NAME}",
        f"Name=ServiceName,Value={service_name}",
        "--statistics",
        "Average",
        "Maximum",
        "--period",
        "60",
        "--start-time",
        fmt_ts(start),
        "--end-time",
        fmt_ts(end),
    ])
    datapoints = data.get("Datapoints", [])
    if not datapoints:
        return {"avg_average": None, "max_maximum": None, "points": 0}
    avg_average = sum(point["Average"] for point in datapoints) / len(datapoints)
    max_maximum = max(point["Maximum"] for point in datapoints)
    return {"avg_average": avg_average, "max_maximum": max_maximum, "points": len(datapoints)}


def parse_locust_summary(stats_csv: Path):
    with stats_csv.open() as input_file:
        rows = list(csv.DictReader(input_file))
    aggregated = next(row for row in rows if row["Name"] == "Aggregated")
    request_count = int(float(aggregated["Request Count"]))
    failure_count = int(float(aggregated["Failure Count"]))
    return {
        "request_count": request_count,
        "failure_count": failure_count,
        "success_rate": (
            (request_count - failure_count) / request_count if request_count else None
        ),
        "requests_per_sec": float(aggregated["Requests/s"]),
        "failures_per_sec": float(aggregated["Failures/s"]),
        "avg_response_ms": float(aggregated["Average Response Time"]),
        "p95_response_ms": float(aggregated["95%"]),
        "p99_response_ms": float(aggregated["99%"]),
        "max_response_ms": float(aggregated["Max Response Time"]),
    }


def parse_lag_summary(lag_csv: Path):
    with lag_csv.open() as input_file:
        rows = list(csv.DictReader(input_file))
    if not rows:
        return {"avg_total_lag": None, "max_total_lag": None, "samples": 0}
    values = [int(row["total_lag"]) for row in rows]
    return {
        "avg_total_lag": sum(values) / len(values),
        "max_total_lag": max(values),
        "samples": len(values),
    }


def percentile(values: list[float], percentile_value: float):
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = round((len(ordered) - 1) * percentile_value)
    return ordered[index]


def load_sample_notification_ids(sampled_ids_path: Path):
    if not sampled_ids_path.exists():
        return []
    rows = []
    seen = set()
    with sampled_ids_path.open() as input_file:
        reader = csv.reader(input_file)
        for row in reader:
            if not row:
                continue
            notification_id = row[0].strip()
            if not notification_id or notification_id in seen:
                continue
            channels = row[1].split("|") if len(row) > 1 and row[1] else []
            rows.append({"notification_id": notification_id, "channels": channels})
            seen.add(notification_id)
    if len(rows) > SAMPLED_NOTIFICATION_IDS_LIMIT:
        random.seed(42)
        rows = random.sample(rows, SAMPLED_NOTIFICATION_IDS_LIMIT)
    return rows


def fetch_attempts(notification_id: str):
    url = f"{LOCUST_HOST}/notifications/{notification_id}/attempts"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def collect_attempts_for_samples(samples: list[dict]):
    attempts_by_notification = {}
    for sample in samples:
        notification_id = sample["notification_id"]
        try:
            attempts_by_notification[notification_id] = fetch_attempts(notification_id)
        except urllib.error.HTTPError as exc:
            attempts_by_notification[notification_id] = {"http_error": exc.code}
        except Exception as exc:
            attempts_by_notification[notification_id] = {"error": str(exc)}
    return attempts_by_notification


def summarize_channel_attempts(samples: list[dict], attempts_by_notification: dict, channel: str):
    expected = 0
    observed = 0
    missing = 0
    queue_wait_values = []
    processing_values = []
    end_to_end_values = []
    success_count = 0

    for sample in samples:
        if channel not in sample["channels"]:
            continue
        expected += 1
        attempts = attempts_by_notification.get(sample["notification_id"], [])
        if not isinstance(attempts, list):
            missing += 1
            continue
        matching = [attempt for attempt in attempts if attempt.get("channel") == channel]
        if not matching:
            missing += 1
            continue
        observed += 1
        latest = max(matching, key=lambda attempt: attempt.get("attemptNo", 0))
        queue_wait_values.append(float(latest["queueWaitLatencyMs"]))
        processing_values.append(float(latest["consumerProcessingLatencyMs"]))
        end_to_end_values.append(float(latest["endToEndLatencyMs"]))
        if latest.get("result") == "SUCCESS":
            success_count += 1

    return {
        "expected_samples": expected,
        "observed_samples": observed,
        "missing_samples": missing,
        "success_rate": (success_count / observed) if observed else None,
        "avg_queue_wait_ms": (sum(queue_wait_values) / len(queue_wait_values)) if queue_wait_values else None,
        "p95_queue_wait_ms": percentile(queue_wait_values, 0.95),
        "avg_processing_ms": (sum(processing_values) / len(processing_values)) if processing_values else None,
        "p95_processing_ms": percentile(processing_values, 0.95),
        "avg_end_to_end_ms": (sum(end_to_end_values) / len(end_to_end_values)) if end_to_end_values else None,
        "p95_end_to_end_ms": percentile(end_to_end_values, 0.95),
    }


def write_summary(run_dir: Path, summary: dict):
    with (run_dir / "summary.json").open("w") as output_file:
        json.dump(summary, output_file, indent=2)


def write_markdown_summary(results_root: Path, summary_rows: list[dict]):
    lines = [
        "# Experiment C Summary",
        "",
        "| Round | Email latency (ms) | In-app latency (ms) | Success rate | Req/s | Email lag max | In-app lag max | In-app CPU max | In-app queue wait p95 (ms) | In-app end-to-end p95 (ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        inapp_attempts = row["inapp_attempts"]
        lines.append(
            "| "
            + " | ".join(
                [
                    row["round_name"],
                    str(row["email_latency_ms"]),
                    str(row["inapp_latency_ms"]),
                    f"{row['locust']['success_rate']:.4f}" if row["locust"]["success_rate"] is not None else "n/a",
                    f"{row['locust']['requests_per_sec']:.2f}",
                    str(row["email_worker_group_lag"]["max_total_lag"]),
                    str(row["inapp_worker_group_lag"]["max_total_lag"]),
                    f"{row['inapp_worker_cpu']['max_maximum']:.2f}" if row["inapp_worker_cpu"]["max_maximum"] is not None else "n/a",
                    f"{inapp_attempts['p95_queue_wait_ms']:.1f}" if inapp_attempts["p95_queue_wait_ms"] is not None else "n/a",
                    f"{inapp_attempts['p95_end_to_end_ms']:.1f}" if inapp_attempts["p95_end_to_end_ms"] is not None else "n/a",
                ]
            )
            + " |"
        )

    with (results_root / "summary.md").open("w") as output_file:
        output_file.write("\n".join(lines) + "\n")


def write_aggregate_csv(results_root: Path, summary_rows: list[dict]):
    with (results_root / "summary.csv").open("w", newline="") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(
            [
                "round_name",
                "email_latency_ms",
                "inapp_latency_ms",
                "success_rate",
                "requests_per_sec",
                "failures_per_sec",
                "email_lag_avg",
                "email_lag_max",
                "inapp_lag_avg",
                "inapp_lag_max",
                "email_cpu_max",
                "inapp_cpu_max",
                "ingress_cpu_max",
                "inapp_attempt_expected",
                "inapp_attempt_observed",
                "inapp_queue_wait_p95_ms",
                "inapp_processing_p95_ms",
                "inapp_end_to_end_p95_ms",
            ]
        )
        for row in summary_rows:
            inapp_attempts = row["inapp_attempts"]
            writer.writerow(
                [
                    row["round_name"],
                    row["email_latency_ms"],
                    row["inapp_latency_ms"],
                    row["locust"]["success_rate"],
                    row["locust"]["requests_per_sec"],
                    row["locust"]["failures_per_sec"],
                    row["email_worker_group_lag"]["avg_total_lag"],
                    row["email_worker_group_lag"]["max_total_lag"],
                    row["inapp_worker_group_lag"]["avg_total_lag"],
                    row["inapp_worker_group_lag"]["max_total_lag"],
                    row["email_worker_cpu"]["max_maximum"],
                    row["inapp_worker_cpu"]["max_maximum"],
                    row["ingress_cpu"]["max_maximum"],
                    inapp_attempts["expected_samples"],
                    inapp_attempts["observed_samples"],
                    inapp_attempts["p95_queue_wait_ms"],
                    inapp_attempts["p95_processing_ms"],
                    inapp_attempts["p95_end_to_end_ms"],
                ]
            )


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_root = Path("results") / f"expC_mixed_isolation_ec2_{timestamp}"
    results_root.mkdir(parents=True, exist_ok=True)
    remote_root = f"{REMOTE_BASE_DIR}/{results_root.name}"
    summary_rows = []

    interrupted = False

    def handle_interrupt(signum, frame):
        nonlocal interrupted
        interrupted = True
        raise KeyboardInterrupt()

    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)

    kafka_ip = get_instance_public_ip(KAFKA_TAG_NAME)
    loadgen_ip = get_instance_public_ip(LOADGEN_TAG_NAME)
    log(f"Using Kafka EC2 public IP: {kafka_ip}")
    log(f"Using load generator EC2 public IP: {loadgen_ip}")
    prepare_loadgen(loadgen_ip, remote_root)

    try:
        for round_config in EXPERIMENT_ROUNDS:
            round_name = round_config["name"]
            run_dir = results_root / round_name
            run_dir.mkdir(parents=True, exist_ok=True)
            log(
                f"=== Experiment C start: {round_name} "
                f"(email={round_config['email_latency_ms']}ms, inapp={round_config['inapp_latency_ms']}ms) ==="
            )

            configure_worker_latencies(
                round_config["email_latency_ms"],
                round_config["inapp_latency_ms"],
            )

            email_lag_stop = threading.Event()
            inapp_lag_stop = threading.Event()
            email_lag_thread = threading.Thread(
                target=lag_sampler,
                args=(kafka_ip, "email-worker-group", run_dir / "email_worker_group_lag.csv", email_lag_stop),
                daemon=True,
            )
            inapp_lag_thread = threading.Thread(
                target=lag_sampler,
                args=(kafka_ip, "inapp-worker-group", run_dir / "inapp_worker_group_lag.csv", inapp_lag_stop),
                daemon=True,
            )

            start_time = utc_now()
            email_lag_thread.start()
            inapp_lag_thread.start()
            try:
                csv_prefix, sampled_ids_path = run_remote_locust(loadgen_ip, remote_root, run_dir)
            finally:
                email_lag_stop.set()
                inapp_lag_stop.set()
                email_lag_thread.join(timeout=20)
                inapp_lag_thread.join(timeout=20)
            end_time = utc_now()

            log(f"Waiting {ATTEMPT_SETTLE_SEC}s for sampled notification attempts to settle")
            time.sleep(ATTEMPT_SETTLE_SEC)

            sampled_notifications = load_sample_notification_ids(sampled_ids_path)
            attempts_by_notification = collect_attempts_for_samples(sampled_notifications)

            summary = {
                "round_name": round_name,
                "start_time_utc": fmt_ts(start_time),
                "end_time_utc": fmt_ts(end_time),
                "kafka_public_ip": kafka_ip,
                "loadgen_public_ip": loadgen_ip,
                "email_latency_ms": round_config["email_latency_ms"],
                "inapp_latency_ms": round_config["inapp_latency_ms"],
                "locust": parse_locust_summary(Path(f"{csv_prefix}_stats.csv")),
                "email_worker_group_lag": parse_lag_summary(run_dir / "email_worker_group_lag.csv"),
                "inapp_worker_group_lag": parse_lag_summary(run_dir / "inapp_worker_group_lag.csv"),
                "email_worker_cpu": get_metric_stats(EMAIL_SERVICE, "CPUUtilization", start_time, end_time),
                "email_worker_memory": get_metric_stats(EMAIL_SERVICE, "MemoryUtilization", start_time, end_time),
                "inapp_worker_cpu": get_metric_stats(INAPP_SERVICE, "CPUUtilization", start_time, end_time),
                "inapp_worker_memory": get_metric_stats(INAPP_SERVICE, "MemoryUtilization", start_time, end_time),
                "ingress_cpu": get_metric_stats(INGRESS_SERVICE, "CPUUtilization", start_time, end_time),
                "ingress_memory": get_metric_stats(INGRESS_SERVICE, "MemoryUtilization", start_time, end_time),
                "sampled_notifications": {
                    "count": len(sampled_notifications),
                    "sample_rate": float(SAMPLED_NOTIFICATION_IDS_RATE),
                },
                "email_attempts": summarize_channel_attempts(sampled_notifications, attempts_by_notification, "EMAIL"),
                "inapp_attempts": summarize_channel_attempts(sampled_notifications, attempts_by_notification, "INAPP"),
            }
            write_summary(run_dir, summary)
            summary_rows.append(summary)
            log(f"=== Experiment C complete: {round_name} ===")
    finally:
        try:
            configure_worker_latencies(100, 20)
        except Exception as exc:
            log(f"Failed to restore worker latencies to defaults: {exc}")

    write_aggregate_csv(results_root, summary_rows)
    write_markdown_summary(results_root, summary_rows)
    log(f"Experiment C complete. Results written to {results_root}")


if __name__ == "__main__":
    main()
