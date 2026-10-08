# RTX A5000: Deploy when available — safety gate

**CURRENT DECISION: DO NOT CLICK YET.**

## Confirmed from user's RunPod checkout screenshot
- 1x RTX A5000, On-Demand, **$0.27/GPU-hour**.
- Container disk: **30 GB**, displayed **$0.004/hour**.
- No persistent volume attached.
- GPU is **out of capacity**; 'Deploy when available' would create a billable Pod automatically at an unknown future time.
- Illustrative hourly sum: $0.274/hour; verify any other charges at actual provisioning.

## Why the current watchdog cannot protect this queue
- The deployed watchdog has no RunPod API key or arming variables.
- The code requires an **existing, exact** `WATCHDOG_POD_ID` and an **absolute UTC deadline**.
- A queued Pod does not yet have a verified Pod ID or known start time.
- Arming the current code before the queue is filled would either fail closed or use the wrong deadline; arming after requires someone to notice activation, which is not unattended protection.
- The one-minute cron does not enforce a hard USD $2 ceiling.
- 'Deploy when available' is NOT equivalent to a safe, timed launch.

## Minimum acceptable unattended-queue design (not yet implemented)
1. Confirm provider-supported Pod creation / auto-deploy event metadata and a **unique immutable identifier** for the exact queued request.
2. Build a separate watchdog which reads Pods and associates only the matching queued request, using validated owner, GPU type, creation timestamp and a unique request marker. Never terminate unrelated Pods.
3. Start a per-Pod timer from verified **actual billing/creation time**, not the time the queue was entered.
4. Enforce a short upper time limit and terminate, not stop. Verify disappearance and retry failures; emit actionable alerts.
5. Independently verify a RunPod-native maximum lifetime or terminate-after setting works for **queued** Pod deployment; use as a backup.
6. Verify with non-billable mocks plus a real controlled termination test (requires separate approval and may incur charges).
7. Confirm storage requirements for upstream TRELLIS image-large and its dependencies; 30 GB and PyTorch 2.8.0 are not validated for official TRELLIS default PyTorch 2.4.0/CUDA 11.8.
8. Recheck final live total hourly quote and remaining balance, obtain explicit authorization for automatic future start, then allow queueing.

## Recommended immediate alternative
- Keep this exact A5000 choice and current settings, **do not press 'Deploy when available'** until the unattended queue watchdog and provider-native auto-termination are verified.
- The offline scripts and GitHub CI do not create Pods and are not substitutes for a live cost guard.
