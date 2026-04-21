# Experiment B Summary

- Email worker replicas: `4`
- Topic partitions: `{'notification.requested': 4, 'notification.email.send': 8, 'notification.inapp.send': 8}`
- Locust shape: `20 users -> 120 users -> 20 users`

## Topline

- Success rate: `1.0000`
- p95: `4900.0` ms
- p99: `5700.0` ms
- Peak lag: `0`
- Time-to-recover: `0.0` sec

## Phase Rates

- baseline avg req/s: `24.615015589285715`
- spike avg req/s: `26.065`
- recovery avg req/s: `24.965921787709494`

## Worker Health

- Task set changed during run: `False`
- Interesting service events during run: `0`
