# Experiment A Summary

Environment:
- Load generator: temporary EC2 in `us-east-1` (`54.162.14.153`)
- Kafka host: `18.234.178.195`
- Workload: fixed-load EMAIL test, 80 Locust users, 300 seconds, 256-byte payload

## Results

| Email worker replicas | Requests/s | Failures/s | p95 (ms) | p99 (ms) | Avg resp (ms) | Avg Kafka lag |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 293.39 | 0.00 | 480 | 1200 | 237.19 | 0.0 |
| 2 | 321.70 | 0.00 | 470 | 1100 | 214.44 | 0.0 |
| 4 | 434.79 | 0.00 | 260 | 380 | 150.40 | 0.0 |
| 8 | 446.25 | 0.00 | 250 | 350 | 145.44 | 0.0 |

## Observations

1. Scaling from 1 to 2 replicas improved throughput modestly, from about 293 req/s to 322 req/s.
2. Scaling from 2 to 4 replicas produced the largest gain, increasing throughput to about 435 req/s and cutting latency sharply.
3. Scaling from 4 to 8 replicas provided only a small throughput gain, from about 435 req/s to 446 req/s, while latency improved only slightly.
4. All four runs completed with zero request failures and zero sampled Kafka consumer lag, so the system stayed stable under this workload.
5. Ingress CPU stayed relatively high across runs, which suggests the next bottleneck is likely on the ingress/API side rather than in the email workers.

## Recommended takeaway

For this workload, `4` email-worker replicas appears to be the best trade-off. Moving to `8` replicas adds cost with only marginal performance improvement.
