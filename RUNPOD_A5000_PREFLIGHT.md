# RTX A5000 / TRELLIS preflight — NO GPU LAUNCH

## Locked decisions
- GPU target: NVIDIA RTX A5000 (24 GB VRAM), **not yet provisioned**.
- Maximum user-approved total spend target: **USD $2**, not a RunPod-enforced cap.
- Paid operations in the API Worker must remain locked until explicit user approval after all checks.
- Keep the Cloudflare watchdog **disarmed** until it is fully configured and validated for the exact Pod.

## Pre-launch checklist (all required)
1. Identify the **exact TRELLIS repository and version** (TRELLIS, TRELLIS.2, etc.), license, model weights, Python/CUDA/PyTorch dependencies, peak VRAM, and whether A5000 24 GB supports the chosen inference mode. Do not assume TRELLIS.2 will fit 24 GB.
2. Confirm A5000 is **actually available** in the user's selected RunPod region/cloud at checkout and record the real quoted GPU $/hr.
3. Confirm separately: container-disk GB and $/GB-month; volume-disk GB and $/GB-month; whether charges continue while stopped; minimum storage sizes; network or other applicable fees. Do not rely on headline GPU prices.
4. Check actual account credits/balance and calculate a conservative maximum session duration with reserve for storage, setup, cold-start, and teardown. `budget_preview` is informational only.
5. Validate RunPod pod termination API against the current provider schema without terminating a real Pod. Verify deadline timezone, retries, failure alerts, and exact-Pod isolation.
6. Independently test the watchdog and verify it has the correct RunPod secret, exact Pod ID, UTC deadline, cron schedule, and `WATCHDOG_ARMED=yes` **only after** the Pod exists and safety is validated. A cron every minute is not a hard budget cap.
7. Prefer a RunPod-native terminate-after option if supported by the chosen creation method, as an independent backup; confirm its exact semantics before relying on it.
8. Obtain the user's explicit approval of the quoted full cost and launch duration immediately before creating any paid resource.
9. After use, **terminate**, don't merely stop, and verify the Pod is no longer listed. Check for leftover volumes/storage charges.

## Stop conditions
- Missing live price or storage fee; unverified model fit; unknown launch time; no independent termination; no explicit approval: **do not create/start Pod or submit paid jobs**.
- No guarantee that $2 is a hard ceiling unless the provider actually enforces such a ceiling.

## Current status
- Read-only RunPod access was previously tested, with zero Pods at that time.
- GitHub offline watchdog tests reported successful.
- Cloudflare watchdog Worker deployed with a one-minute cron and **no RunPod bindings**, therefore disarmed.
- Actual A5000 quote, storage fees, and TRELLIS model fit remain **unverified**.
