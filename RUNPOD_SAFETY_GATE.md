# RunPod $2 safety gate — implementation checklist

Status: **NOT SAFE TO START GPU**. Read-only actions work; billable actions remain HTTP 423 locked.

## Verified on 2026-10-08
- Cloudflare Worker authenticates GPT Actions and can read RunPod Pods and GPU types.
- Pods returned empty.
- GPU type metadata has VRAM but **no verified live pricing or inventory**.
- `budgetUsd=2`, `reserveUsd=0.5`, and `gpuHourlyLimitUsd=0.8` are configuration targets, **not** a RunPod account balance or billing cap.

## Required before unlocking any billable operation
1. Obtain verified RunPod GPU hourly rate for the selected deployment type (Community vs Secure), region and instance; confirm actual availability and minimum billing terms.
2. Obtain verified storage charges (container disk, persistent volume, stopped Pod charges) and account's actual available balance. Avoid claiming the budget is safe without this.
3. Use a separate watchdog outside the GPU Pod (e.g. Cloudflare Cron Trigger), configured with an exact immutable Pod ID, hard absolute UTC deadline and separate RunPod credentials with least privileges possible. It must terminate the Pod, not merely stop it, and check residual storage.
4. A watchdog must run even if the TRELLIS process hangs or GPT loses connectivity. On errors, it must retry and raise an alert; verify termination by reading the Pods API. Cron frequency is not a hard real-time guarantee, so leave an adequate safety buffer and don't claim a guaranteed $2 ceiling.
5. Deploy and **test the watchdog with a mock RunPod API** and fake Pod IDs. Test missing secrets, invalid price, repeated requests, watchdog retry, timeout, API failure and idempotent termination. Never perform a live billable test without separate user approval.
6. Enforce a server-side, one-time signed authorization for create/start/submit with a short expiry; default deny. Never let GPT 'Always Allow' bypass this gate. Protect concurrent requests.
7. Account for cold start, model download, TRELLIS inference time, disk cleanup and shutdown delays. If $2 cannot cover a conservative bound, do not start.
8. Keep game Vercel deployments untouched.

## Candidate GPUs (metadata only)
RTX 3090 (24GB), RTX 4090 (24GB), RTX A5000 (24GB), RTX A6000 (48GB). Prices, inventory and actual TRELLIS compatibility remain unverified.

## Current Worker contract
- GET /health: paidOperations=locked
- GET /api/runpod?action=pods|gpu_types|budget_preview: read only, bearer auth required
- POST create_pod|start_pod|submit_job: 423 locked
- POST terminate_pod: explicit pod_id required

Do not interpret this document as an active watchdog or an implemented spending limit.
