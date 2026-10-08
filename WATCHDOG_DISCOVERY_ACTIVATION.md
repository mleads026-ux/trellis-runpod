# Enable RunPod Pod discovery (read-only only)

## Current safety rule
**Do not click RunPod 'Deploy when available'.** Discovery is not an automatic termination guarantee and the $2 target is not a provider-enforced spending limit.

## Configure Cloudflare Worker `trellis-runpod-watchdog`
In Settings > Variables and Secrets:
- Existing secret: `RUNPOD_API_KEY` (do not disclose).
- Plain-text variable: `WATCHDOG_DISCOVERY_ENABLED` = `yes`
- Plain-text variable: `WATCHDOG_EXPECTED_POD_NAME` = `trellis-a5000` **ONLY IF** the queued Pod is actually configured with that exact name. Otherwise use the real, exact Pod name.
- Leave `WATCHDOG_ARMED` unset. Do not set `WATCHDOG_POD_ID` or `WATCHDOG_DEADLINE_UTC` based on a guess.

Deploy the updated Worker code (which imports `src/pod-discovery.js`). Confirm Cloudflare Worker cron every minute and check logs for `Discovery: not_found` while there is no matching Pod. `candidate_unverified` means the name matched; it does NOT authorize termination.

## Validation
- Confirm the deployed Worker includes the import and its dependency.
- Confirm RunPod GraphQL `myself { pods { id name desiredStatus } }` works with the stored secret. A successful read does not imply any paid action.
- Check that no existing unrelated Pod has the same exact name.
- Verify a stable unique identity linking the queued request to the eventual Pod, and a trustworthy creation/billing timestamp.
- Independently test termination and backup shutdown before any unattended paid launch.
- Do not assume a Cloudflare cron job is a guaranteed hard spending cap.

## Failure behavior
Missing or invalid secret, GraphQL error, duplicate names, and missing name all fail closed. Discovery never starts or terminates a Pod.
