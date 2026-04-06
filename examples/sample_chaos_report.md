# Dock Chaos — Fault Tolerance Report

Generated: 2026-04-06 06:14:10 UTC

## Services Scanned

| Service | Image | Status |
|---------|-------|--------|
| url-shortener-git-app-1 | url-shortener-git-app:latest | running |
| url-shortener-git-db-1 | postgres:16-alpine | running |
| url-shortener-git-cache-1 | redis:7-alpine | running |

## Fault Injection Results

| # | Fault Type | Target | Recovered | Recovery Time | Error |
|---|-----------|--------|-----------|---------------|-------|
| 1 | process_pause | url-shortener-git-app-1 | ✅ Yes | 13ms | — |
| 2 | container_kill | url-shortener-git-db-1 | ✅ Yes | 15ms | — |
| 3 | process_pause | url-shortener-git-db-1 | ✅ Yes | 5234ms | — |
| 4 | memory_stress | url-shortener-git-db-1 | ✅ Yes | 17ms | — |
| 5 | network_partition | url-shortener-git-cache-1 | ✅ Yes | 14ms | — |
| 6 | process_pause | url-shortener-git-app-1 | ✅ Yes | 15ms | — |
| 7 | container_kill | url-shortener-git-cache-1 | ✅ Yes | 14ms | — |
| 8 | container_kill | url-shortener-git-db-1 | ✅ Yes | 14ms | — |
| 9 | process_pause | url-shortener-git-db-1 | ✅ Yes | 5253ms | — |
| 10 | memory_stress | url-shortener-git-db-1 | ✅ Yes | 16ms | — |
| 11 | network_partition | url-shortener-git-app-1 | ✅ Yes | 10ms | — |
| 12 | process_pause | url-shortener-git-app-1 | ✅ Yes | 12ms | — |
| 13 | process_pause | url-shortener-git-cache-1 | ✅ Yes | 5230ms | — |
| 14 | memory_stress | url-shortener-git-db-1 | ✅ Yes | 16ms | — |
| 15 | memory_stress | url-shortener-git-cache-1 | ✅ Yes | 17ms | — |
| 16 | process_pause | url-shortener-git-cache-1 | ✅ Yes | 5247ms | — |

## Summary

- **Total faults injected:** 16
- **Recovered:** 16/16
- **Failed:** 0/16
- **Average recovery time:** 1321ms
- **Fault tolerance score:** B — Good (all recovered, but slowly)

## Recommendations

All services recovered from injected faults. Consider increasing chaos intensity or duration for a more rigorous test.