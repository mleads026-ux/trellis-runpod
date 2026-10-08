# RunPod safety and persistence plan

Current Pod: `outdoor_silver_sparrow` (owner confirmed Stopped, October 2026).

## Current limitations
- This Pod has **no persistent volume**. RunPod warned that stopping it loses **all data** stored on the Pod's ephemeral filesystem. Never assume installed TRELLIS code, downloaded weights, generated models or uploaded images will survive a stop.
- Cloudflare watchdog discovery runs once per minute. Its automatic queue guard is **DISABLED** until `WATCHDOG_AUTO_ARM=yes` is deliberately configured. It is not a billing cap.
- Never enable automatic Stop while important files exist only on the Pod.
- Never automatically Terminate the Pod. The separate API bridge rejects `terminate_pod` in source, but that API change requires its own deployment.
- `podStop` is not `podTerminate`; Stop does not delete the Pod record, but without a volume it may lose ephemeral data.
- RunPod GPU billing and possible storage charges must be verified from the RunPod console, not estimated from this repository.

## Before any paid restart
1. Choose and verify a persistent storage destination (RunPod network volume, compatible object storage, or external backup) and its pricing against the user's $2 maximum budget. A network volume may incur ongoing charges even with GPU stopped.
2. Confirm the Pod can actually access that destination. Do not assume a volume can be attached to the existing stopped Pod.
3. Prepare a reproducible TRELLIS container/setup and an export routine for generated GLB and other output artifacts. Do not store API keys in GitHub.
4. Test restoration from backup using a non-GPU test where possible.
5. Only then ask for explicit approval to start paid GPU compute and separately enable the stop-only queue guard after verifying immutable Pod ID and stop mutation.

## Safe deployment
- Watchdog: `.github/workflows/deploy-watchdog.yml` (disarmed).
- API: `.github/workflows/deploy-api-stop-only.yml` (checks termination mutation absent before deployment).
- A successful workflow only verifies deployment, **not** that RunPod stop has been exercised in production.
