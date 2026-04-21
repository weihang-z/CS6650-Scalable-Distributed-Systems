# Experiment B Summary

- Email worker replicas: `1`
- Topic partitions: `{'notification.requested': 4, 'notification.email.send': 8, 'notification.inapp.send': 8}`
- Locust shape: `20 users -> 400 users -> 20 users`

## Topline

- Success rate: `0.9436`
- p95: `28000.0` ms
- p99: `39000.0` ms
- Peak lag: `0`
- Time-to-recover: `0.0` sec

## Phase Rates

- baseline avg req/s: `22.24190546902655`
- spike avg req/s: `20.98739495798319`
- recovery avg req/s: `18.64979079497908`

## Worker Health

- Task set changed during run: `False`
- Interesting service events during run: `0`
