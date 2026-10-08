#!/usr/bin/env python3
"""Fail-closed approval check for RunPod unattended 'Deploy when available'.
No API calls, GPU operations, or secret handling. This does NOT implement protection.
"""
import argparse
import json

p = argparse.ArgumentParser()
p.add_argument("--live-price-verified", action="store_true")
p.add_argument("--storage-verified", action="store_true")
p.add_argument("--trellis-image-validated", action="store_true")
p.add_argument("--queue-identity-verified", action="store_true")
p.add_argument("--watchdog-armed-and-tested", action="store_true")
p.add_argument("--independent-termination-tested", action="store_true")
p.add_argument("--provider-budget-cap-verified", action="store_true")
p.add_argument("--user-approved-auto-start", action="store_true")
args = p.parse_args()
checks = {
    "live_price_verified": args.live_price_verified,
    "storage_verified": args.storage_verified,
    "trellis_image_validated": args.trellis_image_validated,
    "queue_identity_verified": args.queue_identity_verified,
    "watchdog_armed_and_tested": args.watchdog_armed_and_tested,
    "independent_termination_tested": args.independent_termination_tested,
    "provider_budget_cap_verified": args.provider_budget_cap_verified,
    "user_approved_auto_start": args.user_approved_auto_start,
}
approved = all(checks.values())
print(json.dumps({"safe_to_queue": approved, "checks": checks,
                  "note": "This offline checklist does not create or guarantee any spending cap."}, indent=2))
if not approved:
    raise SystemExit(3)
