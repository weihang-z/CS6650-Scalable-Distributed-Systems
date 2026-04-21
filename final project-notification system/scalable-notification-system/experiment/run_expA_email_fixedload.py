import csv
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


AWS_REGION = "us-east-1"
CLUSTER_NAME = "scalable-notification-system-dev-cluster"
EMAIL_SERVICE = "scalable-notification-system-dev-email-worker-service"
INGRESS_SERVICE = "scalable-notification-system-dev-ingress-service"
KAFKA_TAG_NAME = "scalable-notification-system-dev-kafka-ec2"
LOCUST_HOST = "http://scalable-notification-system-alb-2044224092.us-east-1.elb.amazonaws.com"
LOCUST_FILE = "locust/locustfile.py"
KEY_PATH = '.keys/sns-dev-20260420.pem'
KAFKA_SSH_USER = "ec2-user"
REPLICAS_TO_TEST = [1, 2, 4, 8]
STABILIZE_SEC = 60
LAG_SAMPLE_SEC = 15


def utc_now():
    return datetime.now(timezone.utc)


def fmt_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def log(message: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def run(cmd, env=None, cwd=None, capture_output=True, check=True):
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
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


def get_kafka_public_ip():
    data = aws_json([
        "ec2", "describe-instances",
        "--filters",
        f"Name=tag:Name,Values={KAFKA_TAG_NAME}",
        "Name=instance-state-name,Values=running",
        "--query",
        "Reservations[].Instances[].PublicIpAddress",
    ])
    if not data or not data[0]:
        raise RuntimeError("Could not resolve current Kafka EC2 public IP")
    return data[0]


def ssh_base(kafka_ip: str):
    return [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "IdentitiesOnly=yes",
        "-i", KEY_PATH,
        f"{KAFKA_SSH_USER}@{kafka_ip}",
    ]


def scale_email_workers(replica_count: int):
    log(f"Scaling {EMAIL_SERVICE} to {replica_count} replicas")
    run([
        "aws", "ecs", "update-service",
        "--region", AWS_REGION,
        "--cluster", CLUSTER_NAME,
        "--service", EMAIL_SERVICE,
        "--desired-count", str(replica_count),
    ])
    run([
        "aws", "ecs", "wait", "services-stable",
        "--region", AWS_REGION,
        "--cluster", CLUSTER_NAME,
        "--services", EMAIL_SERVICE,
    ], capture_output=False)
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
            raw = run(
                ssh_base(kafka_ip) + [
                    "sudo", "docker", "exec", "kafka",
                    "kafka-consumer-groups",
                    "--bootstrap-server", "localhost:9092",
                    "--describe",
                    "--group", "email-worker-group",
                ],
                check=False,
            )
            total_lag = parse_total_lag((raw.stdout or "") + "\n" + (raw.stderr or ""))
            writer.writerow([fmt_ts(utc_now()), total_lag])
            f.flush()
            stop_event.wait(LAG_SAMPLE_SEC)


def run_locust(run_dir: Path):
    csv_prefix = run_dir / "locust"
    log_path = run_dir / "locust.log"
    env = os.environ.copy()
    env.update({
        "TEST_MODE": "steady",
        "CHANNEL_MODE": "EMAIL",
        "STEADY_USERS": "80",
        "STEADY_DURATION_SEC": "300",
        "SPAWN_RATE": "10",
        "PAYLOAD_BYTES": "256",
    })
    cmd = [
        "locust",
        "-f", LOCUST_FILE,
        "--host", LOCUST_HOST,
        "--headless",
        "--csv", str(csv_prefix),
    ]
    log(f"Starting Locust: {' '.join(cmd)}")
    with log_path.open("w") as log_file:
        proc = subprocess.Popen(
            cmd,
            cwd=Path.cwd(),
            env=env,
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
    if proc.returncode != 0:
        raise RuntimeError(f"Locust run failed with exit code {proc.returncode}")
    return csv_prefix


def get_metric_stats(service_name: str, metric_name: str, start: datetime, end: datetime):
    data = aws_json([
        "cloudwatch", "get-metric-statistics",
        "--namespace", "AWS/ECS",
        "--metric-name", metric_name,
        "--dimensions", f"Name=ClusterName,Value={CLUSTER_NAME}", f"Name=ServiceName,Value={service_name}",
        "--statistics", "Average", "Maximum",
        "--period", "60",
        "--start-time", fmt_ts(start),
        "--end-time", fmt_ts(end),
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
    return {
        "request_count": int(float(aggregated["Request Count"])),
        "failure_count": int(float(aggregated["Failure Count"])),
        "requests_per_sec": float(aggregated["Requests/s"]),
        "failures_per_sec": float(aggregated["Failures/s"]),
        "avg_response_ms": float(aggregated["Average Response Time"]),
        "p95_response_ms": float(aggregated["95%"]),
        "p99_response_ms": float(aggregated["99%"]),
        "max_response_ms": float(aggregated["Max Response Time"]),
    }


def parse_lag_summary(lag_csv: Path):
    with lag_csv.open() as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {"avg_total_lag": None, "max_total_lag": None, "samples": 0}
    values = [int(r["total_lag"]) for r in rows]
    return {
        "avg_total_lag": sum(values) / len(values),
        "max_total_lag": max(values),
        "samples": len(values),
    }


def write_summary(run_dir: Path, summary: dict):
    with (run_dir / "summary.json").open("w") as f:
        json.dump(summary, f, indent=2)


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_root = Path("results") / f"expA_email_fixedload_{timestamp}"
    results_root.mkdir(parents=True, exist_ok=True)
    summary_rows = []

    interrupted = False

    def handle_interrupt(signum, frame):
        nonlocal interrupted
        interrupted = True
        raise KeyboardInterrupt()

    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)

    kafka_ip = get_kafka_public_ip()
    log(f"Using Kafka EC2 public IP: {kafka_ip}")

    try:
        for replica_count in REPLICAS_TO_TEST:
            run_dir = results_root / f"replicas_{replica_count}"
            run_dir.mkdir(parents=True, exist_ok=True)
            log(f"=== Experiment run start: replicas={replica_count} ===")
            scale_email_workers(replica_count)

            lag_stop = threading.Event()
            lag_thread = threading.Thread(
                target=lag_sampler,
                args=(kafka_ip, run_dir / "email_worker_group_lag.csv", lag_stop),
                daemon=True,
            )

            start_time = utc_now()
            lag_thread.start()
            try:
                csv_prefix = run_locust(run_dir)
            finally:
                lag_stop.set()
                lag_thread.join(timeout=20)
            end_time = utc_now()

            locust_summary = parse_locust_summary(Path(f"{csv_prefix}_stats.csv"))
            lag_summary = parse_lag_summary(run_dir / "email_worker_group_lag.csv")
            email_cpu = get_metric_stats(EMAIL_SERVICE, "CPUUtilization", start_time, end_time)
            email_mem = get_metric_stats(EMAIL_SERVICE, "MemoryUtilization", start_time, end_time)
            ingress_cpu = get_metric_stats(INGRESS_SERVICE, "CPUUtilization", start_time, end_time)
            ingress_mem = get_metric_stats(INGRESS_SERVICE, "MemoryUtilization", start_time, end_time)

            summary = {
                "replicas": replica_count,
                "start_time_utc": fmt_ts(start_time),
                "end_time_utc": fmt_ts(end_time),
                "locust": locust_summary,
                "email_worker_cpu": email_cpu,
                "email_worker_memory": email_mem,
                "ingress_cpu": ingress_cpu,
                "ingress_memory": ingress_mem,
                "email_worker_group_lag": lag_summary,
            }
            write_summary(run_dir, summary)
            summary_rows.append(summary)
            log(f"=== Experiment run complete: replicas={replica_count} ===")
    finally:
        try:
            scale_email_workers(1)
        except Exception as exc:
            log(f"Failed to restore email worker replicas to 1: {exc}")

    aggregate_csv = results_root / "summary.csv"
    with aggregate_csv.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "replicas",
            "requests_per_sec",
            "failures_per_sec",
            "p95_response_ms",
            "p99_response_ms",
            "email_worker_cpu_avg",
            "email_worker_cpu_max",
            "email_worker_mem_avg",
            "email_worker_mem_max",
            "ingress_cpu_avg",
            "ingress_cpu_max",
            "ingress_mem_avg",
            "ingress_mem_max",
            "email_worker_group_lag_avg",
            "email_worker_group_lag_max",
        ])
        for row in summary_rows:
            writer.writerow([
                row["replicas"],
                row["locust"]["requests_per_sec"],
                row["locust"]["failures_per_sec"],
                row["locust"]["p95_response_ms"],
                row["locust"]["p99_response_ms"],
                row["email_worker_cpu"]["avg_average"],
                row["email_worker_cpu"]["max_maximum"],
                row["email_worker_memory"]["avg_average"],
                row["email_worker_memory"]["max_maximum"],
                row["ingress_cpu"]["avg_average"],
                row["ingress_cpu"]["max_maximum"],
                row["ingress_memory"]["avg_average"],
                row["ingress_memory"]["max_maximum"],
                row["email_worker_group_lag"]["avg_total_lag"],
                row["email_worker_group_lag"]["max_total_lag"],
            ])

    log(f"Experiment A complete. Results written to {results_root}")


if __name__ == "__main__":
    main()
