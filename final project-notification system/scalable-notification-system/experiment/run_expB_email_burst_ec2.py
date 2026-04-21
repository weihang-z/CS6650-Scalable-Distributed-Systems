import csv
import json
import math
import os
import re
import shlex
import signal
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


AWS_REGION = "us-east-1"
CLUSTER_NAME = "scalable-notification-system-dev-cluster"
EMAIL_SERVICE = "scalable-notification-system-dev-email-worker-service"
INGRESS_SERVICE = "scalable-notification-system-dev-ingress-service"
KAFKA_TAG_NAME = "scalable-notification-system-dev-kafka-ec2"
LOADGEN_TAG_NAME = "scalable-notification-system-dev-loadgen-ec2"
LOCUST_HOST = "http://scalable-notification-system-alb-2044224092.us-east-1.elb.amazonaws.com"
LOCUST_FILE = "locust/locustfile.py"
KEY_PATH = ".keys/sns-dev-20260420.pem"
SSH_USER = "ec2-user"
REMOTE_BASE_DIR = "/home/ec2-user/expB_email_burst"

EMAIL_WORKER_REPLICAS = int(os.getenv("EMAIL_WORKER_REPLICAS", "4"))
RESTORE_EMAIL_WORKER_REPLICAS = int(os.getenv("RESTORE_EMAIL_WORKER_REPLICAS", "1"))

BASELINE_USERS = os.getenv("BASELINE_USERS", "20")
BASELINE_DURATION_SEC = int(os.getenv("BASELINE_DURATION_SEC", "120"))
SPIKE_USERS = os.getenv("SPIKE_USERS", "120")
SPIKE_DURATION_SEC = int(os.getenv("SPIKE_DURATION_SEC", "120"))
RECOVERY_DURATION_SEC = int(os.getenv("RECOVERY_DURATION_SEC", "180"))
SPAWN_RATE = os.getenv("SPAWN_RATE", "20")
PAYLOAD_BYTES = os.getenv("PAYLOAD_BYTES", "256")

STABILIZE_SEC = int(os.getenv("STABILIZE_SEC", "60"))
LAG_SAMPLE_SEC = int(os.getenv("LAG_SAMPLE_SEC", "5"))
BASELINE_STEADY_WINDOW_SEC = int(os.getenv("BASELINE_STEADY_WINDOW_SEC", "60"))
RECOVERY_CONSECUTIVE_SAMPLES = int(os.getenv("RECOVERY_CONSECUTIVE_SAMPLES", "2"))

TOPICS_TO_TRACK = [
    "notification.requested",
    "notification.email.send",
    "notification.inapp.send",
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


def scale_email_workers(replica_count: int):
    log(f"Scaling {EMAIL_SERVICE} to {replica_count} replicas")
    run(
        [
            "aws",
            "ecs",
            "update-service",
            "--region",
            AWS_REGION,
            "--cluster",
            CLUSTER_NAME,
            "--service",
            EMAIL_SERVICE,
            "--desired-count",
            str(replica_count),
        ]
    )
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
            EMAIL_SERVICE,
        ],
        capture_output=False,
    )
    log(f"{EMAIL_SERVICE} is stable, waiting {STABILIZE_SEC}s extra")
    time.sleep(STABILIZE_SEC)


def parse_total_lag(raw: str) -> int:
    total = 0
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 6:
            continue
        if parts[0].startswith("notification.") and parts[-1].isdigit():
            total += int(parts[-1])
    return total


def lag_sampler(kafka_ip: str, output_csv: Path, stop_event: threading.Event):
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_utc", "total_lag"])
        while not stop_event.is_set():
            raw = ssh_bash(
                kafka_ip,
                (
                    "sudo docker exec kafka "
                    "kafka-consumer-groups "
                    "--bootstrap-server localhost:9092 "
                    "--describe "
                    "--group email-worker-group"
                ),
                check=False,
            )
            total_lag = parse_total_lag((raw.stdout or "") + "\n" + (raw.stderr or ""))
            writer.writerow([fmt_ts(utc_now()), total_lag])
            f.flush()
            stop_event.wait(LAG_SAMPLE_SEC)


def run_remote_locust(loadgen_ip: str, remote_root: str, run_dir: Path):
    remote_run_dir = f"{remote_root}/{run_dir.name}"
    csv_prefix = run_dir / "locust"
    log_path = run_dir / "locust.log"

    ssh_bash(loadgen_ip, f"mkdir -p {remote_run_dir}", capture_output=False)

    remote_cmd = (
        "set -euo pipefail && "
        f"cd {remote_root} && "
        f"mkdir -p {remote_run_dir} && "
        "TEST_MODE=burst "
        "CHANNEL_MODE=EMAIL "
        f"BASELINE_USERS={BASELINE_USERS} "
        f"BASELINE_DURATION_SEC={BASELINE_DURATION_SEC} "
        f"SPIKE_USERS={SPIKE_USERS} "
        f"SPIKE_DURATION_SEC={SPIKE_DURATION_SEC} "
        f"RECOVERY_DURATION_SEC={RECOVERY_DURATION_SEC} "
        f"SPAWN_RATE={SPAWN_RATE} "
        f"PAYLOAD_BYTES={PAYLOAD_BYTES} "
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
            str(run_dir),
        ]
    )

    if proc.returncode not in (0, 1):
        raise RuntimeError(f"Remote Locust run failed with exit code {proc.returncode}")

    return csv_prefix


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
    dps = data.get("Datapoints", [])
    if not dps:
        return {"avg_average": None, "max_maximum": None, "points": 0}
    avg_average = sum(dp["Average"] for dp in dps) / len(dps)
    max_maximum = max(dp["Maximum"] for dp in dps)
    return {"avg_average": avg_average, "max_maximum": max_maximum, "points": len(dps)}


def parse_locust_summary(stats_csv: Path):
    with stats_csv.open() as f:
        rows = list(csv.DictReader(f))
    aggregated = next(row for row in rows if row["Name"] == "Aggregated")
    request_count = int(float(aggregated["Request Count"]))
    failure_count = int(float(aggregated["Failure Count"]))
    success_rate = 1.0 if request_count == 0 else (request_count - failure_count) / request_count
    return {
        "request_count": request_count,
        "failure_count": failure_count,
        "success_rate": success_rate,
        "requests_per_sec": float(aggregated["Requests/s"]),
        "failures_per_sec": float(aggregated["Failures/s"]),
        "avg_response_ms": float(aggregated["Average Response Time"]),
        "p95_response_ms": float(aggregated["95%"]),
        "p99_response_ms": float(aggregated["99%"]),
        "max_response_ms": float(aggregated["Max Response Time"]),
    }


def parse_iso8601(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_lag_samples(lag_csv: Path):
    with lag_csv.open() as f:
        rows = list(csv.DictReader(f))
    return [(parse_iso8601(r["timestamp_utc"]), int(r["total_lag"])) for r in rows]


def summarize_lag_recovery(lag_csv: Path, start_time: datetime):
    samples = load_lag_samples(lag_csv)
    if not samples:
        return {
            "samples": 0,
            "baseline_avg_lag": None,
            "baseline_max_lag": None,
            "recovery_threshold_lag": None,
            "lag_rise_time_utc": None,
            "lag_rise_after_spike_start_sec": None,
            "peak_lag": None,
            "peak_lag_time_utc": None,
            "recovered_time_utc": None,
            "time_to_recover_sec": None,
        }

    baseline_end = start_time + timedelta(seconds=BASELINE_DURATION_SEC)
    spike_end = baseline_end + timedelta(seconds=SPIKE_DURATION_SEC)
    baseline_start = baseline_end - timedelta(seconds=BASELINE_STEADY_WINDOW_SEC)

    baseline_values = [lag for ts, lag in samples if baseline_start <= ts < baseline_end]
    if not baseline_values:
        baseline_values = [lag for ts, lag in samples if start_time <= ts < baseline_end]

    baseline_avg = sum(baseline_values) / len(baseline_values) if baseline_values else 0.0
    baseline_max = max(baseline_values) if baseline_values else 0
    recovery_threshold = max(5, int(math.ceil(baseline_max + 5)))

    rise_sample = next(
        (
            (ts, lag)
            for ts, lag in samples
            if ts >= baseline_end and lag > recovery_threshold
        ),
        None,
    )
    peak_time, peak_lag = max(samples, key=lambda sample: sample[1])

    post_spike_samples = [(ts, lag) for ts, lag in samples if ts >= spike_end]
    recovered_time = None
    if rise_sample is None:
        recovered_time = spike_end
    else:
        consecutive = 0
        for ts, lag in post_spike_samples:
            if lag <= recovery_threshold:
                consecutive += 1
                if consecutive >= RECOVERY_CONSECUTIVE_SAMPLES:
                    recovered_time = ts
                    break
            else:
                consecutive = 0

    return {
        "samples": len(samples),
        "baseline_avg_lag": baseline_avg,
        "baseline_max_lag": baseline_max,
        "recovery_threshold_lag": recovery_threshold,
        "lag_rise_time_utc": fmt_ts(rise_sample[0]) if rise_sample else None,
        "lag_rise_after_spike_start_sec": (
            (rise_sample[0] - baseline_end).total_seconds() if rise_sample else None
        ),
        "peak_lag": peak_lag,
        "peak_lag_time_utc": fmt_ts(peak_time),
        "recovered_time_utc": fmt_ts(recovered_time) if recovered_time else None,
        "time_to_recover_sec": (
            (recovered_time - spike_end).total_seconds() if recovered_time else None
        ),
    }


def summarize_locust_history(history_csv: Path, start_time: datetime):
    phases = {
        "baseline": (0, BASELINE_DURATION_SEC),
        "spike": (BASELINE_DURATION_SEC, BASELINE_DURATION_SEC + SPIKE_DURATION_SEC),
        "recovery": (
            BASELINE_DURATION_SEC + SPIKE_DURATION_SEC,
            BASELINE_DURATION_SEC + SPIKE_DURATION_SEC + RECOVERY_DURATION_SEC,
        ),
    }
    buckets = {phase: [] for phase in phases}

    with history_csv.open() as f:
        for row in csv.DictReader(f):
            if row["Name"] != "Aggregated":
                continue
            if row["Type"]:
                continue
            ts = datetime.fromtimestamp(int(row["Timestamp"]), tz=timezone.utc)
            offset_sec = (ts - start_time).total_seconds()
            for phase, (start_sec, end_sec) in phases.items():
                if start_sec <= offset_sec < end_sec:
                    buckets[phase].append(row)
                    break

    summary = {}
    for phase, rows in buckets.items():
        if not rows:
            summary[phase] = {
                "samples": 0,
                "avg_requests_per_sec": None,
                "max_requests_per_sec": None,
                "avg_failures_per_sec": None,
                "max_user_count": None,
            }
            continue

        request_rates = [float(row["Requests/s"]) for row in rows]
        failure_rates = [float(row["Failures/s"]) for row in rows]
        user_counts = [int(float(row["User Count"])) for row in rows]
        summary[phase] = {
            "samples": len(rows),
            "avg_requests_per_sec": sum(request_rates) / len(request_rates),
            "max_requests_per_sec": max(request_rates),
            "avg_failures_per_sec": sum(failure_rates) / len(failure_rates),
            "max_user_count": max(user_counts),
        }
    return summary


def get_service_events(service_name: str):
    data = aws_json([
        "ecs",
        "describe-services",
        "--cluster",
        CLUSTER_NAME,
        "--services",
        service_name,
        "--query",
        "services[0].events",
    ])
    return data or []


def get_task_state(service_name: str):
    task_arns = aws_json([
        "ecs",
        "list-tasks",
        "--cluster",
        CLUSTER_NAME,
        "--service-name",
        service_name,
        "--query",
        "taskArns",
    ]) or []
    if not task_arns:
        return []
    data = aws_json([
        "ecs",
        "describe-tasks",
        "--cluster",
        CLUSTER_NAME,
        "--tasks",
        *task_arns,
        "--query",
        "tasks[].{taskArn:taskArn,lastStatus:lastStatus,desiredStatus:desiredStatus,healthStatus:healthStatus,containers:containers[].{name:name,lastStatus:lastStatus,healthStatus:healthStatus,exitCode:exitCode,reason:reason}}",
    ])
    return data or []


def summarize_service_health_events(events, start_time: datetime, end_time: datetime):
    interesting = []
    pattern = re.compile(r"unhealthy|stopped|unable|failed|restart", re.IGNORECASE)
    for event in events:
        created_at = datetime.fromisoformat(event["createdAt"])
        created_at_utc = created_at.astimezone(timezone.utc)
        if not (start_time <= created_at_utc <= end_time):
            continue
        message = event["message"]
        if pattern.search(message):
            interesting.append(
                {
                    "created_at_utc": fmt_ts(created_at_utc),
                    "message": message,
                }
            )
    return interesting


def get_topic_partition_counts(kafka_ip: str):
    counts = {}
    for topic in TOPICS_TO_TRACK:
        raw = ssh_bash(
            kafka_ip,
            f"sudo docker exec kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic {shlex.quote(topic)}",
        )
        match = re.search(r"PartitionCount:\s*(\d+)", raw.stdout or "")
        counts[topic] = int(match.group(1)) if match else None
    return counts


def write_summary(run_dir: Path, summary: dict):
    with (run_dir / "summary.json").open("w") as f:
        json.dump(summary, f, indent=2)


def write_markdown_summary(run_dir: Path, summary: dict):
    locust = summary["locust"]
    lag = summary["lag_recovery"]
    phase = summary["locust_phase_rates"]
    health = summary["email_worker_health"]
    workload = summary["workload"]
    lines = [
        "# Experiment B Summary",
        "",
        f"- Email worker replicas: `{summary['email_worker_replicas']}`",
        f"- Topic partitions: `{summary['topic_partitions']}`",
        (
            f"- Locust shape: `{workload['baseline_users']} users -> "
            f"{workload['spike_users']} users -> {workload['baseline_users']} users`"
        ),
        "",
        "## Topline",
        "",
        f"- Success rate: `{locust['success_rate']:.4f}`",
        f"- p95: `{locust['p95_response_ms']}` ms",
        f"- p99: `{locust['p99_response_ms']}` ms",
        f"- Peak lag: `{lag['peak_lag']}`",
        f"- Time-to-recover: `{lag['time_to_recover_sec']}` sec",
        "",
        "## Phase Rates",
        "",
        f"- baseline avg req/s: `{phase['baseline']['avg_requests_per_sec']}`",
        f"- spike avg req/s: `{phase['spike']['avg_requests_per_sec']}`",
        f"- recovery avg req/s: `{phase['recovery']['avg_requests_per_sec']}`",
        "",
        "## Worker Health",
        "",
        f"- Task set changed during run: `{health['task_set_changed']}`",
        f"- Interesting service events during run: `{len(health['interesting_events'])}`",
    ]
    with (run_dir / "summary.md").open("w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_root = Path("results") / f"expB_email_burst_ec2_{timestamp}"
    results_root.mkdir(parents=True, exist_ok=True)
    run_dir = results_root / "run_1"
    run_dir.mkdir(parents=True, exist_ok=True)
    remote_root = f"{REMOTE_BASE_DIR}/{results_root.name}"

    def handle_interrupt(signum, frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)

    kafka_ip = get_instance_public_ip(KAFKA_TAG_NAME)
    loadgen_ip = get_instance_public_ip(LOADGEN_TAG_NAME)
    log(f"Using Kafka EC2 public IP: {kafka_ip}")
    log(f"Using load generator EC2 public IP: {loadgen_ip}")
    prepare_loadgen(loadgen_ip, remote_root)
    try:
        scale_email_workers(EMAIL_WORKER_REPLICAS)
        topic_partitions = get_topic_partition_counts(kafka_ip)

        log("Capturing pre-run task state")
        pre_run_tasks = get_task_state(EMAIL_SERVICE)
        pre_run_events = get_service_events(EMAIL_SERVICE)
        log(f"Captured {len(pre_run_tasks)} pre-run email-worker tasks")

        lag_stop = threading.Event()
        lag_thread = threading.Thread(
            target=lag_sampler,
            args=(kafka_ip, run_dir / "email_worker_group_lag.csv", lag_stop),
            daemon=True,
        )

        start_time = utc_now()
        lag_thread.start()
        try:
            csv_prefix = run_remote_locust(loadgen_ip, remote_root, run_dir)
        finally:
            lag_stop.set()
            lag_thread.join(timeout=20)
        end_time = utc_now()

        locust_summary = parse_locust_summary(Path(f"{csv_prefix}_stats.csv"))
        locust_phase_rates = summarize_locust_history(Path(f"{csv_prefix}_stats_history.csv"), start_time)
        lag_recovery = summarize_lag_recovery(run_dir / "email_worker_group_lag.csv", start_time)
        email_cpu = get_metric_stats(EMAIL_SERVICE, "CPUUtilization", start_time, end_time)
        email_mem = get_metric_stats(EMAIL_SERVICE, "MemoryUtilization", start_time, end_time)
        ingress_cpu = get_metric_stats(INGRESS_SERVICE, "CPUUtilization", start_time, end_time)
        ingress_mem = get_metric_stats(INGRESS_SERVICE, "MemoryUtilization", start_time, end_time)

        post_run_tasks = get_task_state(EMAIL_SERVICE)
        post_run_events = get_service_events(EMAIL_SERVICE)
        interesting_events = summarize_service_health_events(post_run_events, start_time, end_time)
        task_set_changed = sorted(task["taskArn"] for task in pre_run_tasks) != sorted(
            task["taskArn"] for task in post_run_tasks
        )

        summary = {
            "start_time_utc": fmt_ts(start_time),
            "end_time_utc": fmt_ts(end_time),
            "kafka_public_ip": kafka_ip,
            "loadgen_public_ip": loadgen_ip,
            "email_worker_replicas": EMAIL_WORKER_REPLICAS,
            "topic_partitions": topic_partitions,
            "workload": {
                "test_mode": "burst",
                "channel_mode": "EMAIL",
                "baseline_users": int(BASELINE_USERS),
                "baseline_duration_sec": BASELINE_DURATION_SEC,
                "spike_users": int(SPIKE_USERS),
                "spike_duration_sec": SPIKE_DURATION_SEC,
                "recovery_duration_sec": RECOVERY_DURATION_SEC,
                "spawn_rate": float(SPAWN_RATE),
                "payload_bytes": int(PAYLOAD_BYTES),
            },
            "locust": locust_summary,
            "locust_phase_rates": locust_phase_rates,
            "lag_recovery": lag_recovery,
            "email_worker_cpu": email_cpu,
            "email_worker_memory": email_mem,
            "ingress_cpu": ingress_cpu,
            "ingress_memory": ingress_mem,
            "email_worker_health": {
                "task_set_changed": task_set_changed,
                "pre_run_task_arns": [task["taskArn"] for task in pre_run_tasks],
                "post_run_task_arns": [task["taskArn"] for task in post_run_tasks],
                "interesting_events": interesting_events,
                "event_count_before_run": len(pre_run_events),
                "event_count_after_run": len(post_run_events),
            },
        }
        write_summary(run_dir, summary)
        write_markdown_summary(run_dir, summary)

        aggregate_csv = results_root / "summary.csv"
        with aggregate_csv.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "email_worker_replicas",
                    "success_rate",
                    "requests_per_sec",
                    "failures_per_sec",
                    "p95_response_ms",
                    "p99_response_ms",
                    "peak_lag",
                    "time_to_recover_sec",
                    "email_worker_cpu_max",
                    "email_worker_mem_max",
                    "ingress_cpu_max",
                    "ingress_mem_max",
                    "task_set_changed",
                    "interesting_event_count",
                ]
            )
            writer.writerow(
                [
                    summary["email_worker_replicas"],
                    summary["locust"]["success_rate"],
                    summary["locust"]["requests_per_sec"],
                    summary["locust"]["failures_per_sec"],
                    summary["locust"]["p95_response_ms"],
                    summary["locust"]["p99_response_ms"],
                    summary["lag_recovery"]["peak_lag"],
                    summary["lag_recovery"]["time_to_recover_sec"],
                    summary["email_worker_cpu"]["max_maximum"],
                    summary["email_worker_memory"]["max_maximum"],
                    summary["ingress_cpu"]["max_maximum"],
                    summary["ingress_memory"]["max_maximum"],
                    summary["email_worker_health"]["task_set_changed"],
                    len(summary["email_worker_health"]["interesting_events"]),
                ]
            )

        log(f"Experiment B complete. Results written to {results_root}")
    finally:
        try:
            scale_email_workers(RESTORE_EMAIL_WORKER_REPLICAS)
        except Exception as exc:
            log(f"Failed to restore email worker replicas to {RESTORE_EMAIL_WORKER_REPLICAS}: {exc}")


if __name__ == "__main__":
    main()
