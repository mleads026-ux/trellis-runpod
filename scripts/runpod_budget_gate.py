#!/usr/bin/env python3
"""Offline planning only. Never creates Pods, authorizes spend, or guarantees a hard cap."""
import argparse
import json
import math
import sys

def nonnegative(value):
    n = float(value)
    if not math.isfinite(n) or n < 0:
        raise argparse.ArgumentTypeError("Must be finite and nonnegative")
    return n

p = argparse.ArgumentParser(description="Conservative RunPod budget preview (no network)")
p.add_argument("--gpu-hourly", type=nonnegative, required=True, help="LIVE checkout GPU price in USD/hour")
p.add_argument("--storage-hourly", type=nonnegative, required=True, help="ALL storage charges in USD/hour")
p.add_argument("--other-fixed", type=nonnegative, default=0, help="Other confirmed fees in USD")
p.add_argument("--budget", type=nonnegative, default=2.0)
p.add_argument("--reserve", type=nonnegative, default=0.5)
p.add_argument("--safety-factor", type=nonnegative, default=1.25, help="Conservative multiplier >= 1")
args = p.parse_args()
if args.safety_factor < 1:
    p.error("--safety-factor must be >= 1")
rate = (args.gpu_hourly + args.storage_hourly) * args.safety_factor
spendable = args.budget - args.reserve - args.other_fixed
if spendable <= 0 or rate <= 0:
    p.error("No safe positive session time; verify budget, fees, and rate")
minutes = math.floor(spendable / rate * 60)
print(json.dumps({
    "planning_only": True,
    "hard_spend_cap": False,
    "gpu_hourly_usd": args.gpu_hourly,
    "storage_hourly_usd": args.storage_hourly,
    "budget_usd": args.budget,
    "reserve_usd": args.reserve,
    "other_fixed_usd": args.other_fixed,
    "safety_factor": args.safety_factor,
    "maximum_planned_minutes": minutes,
    "warning": "Live price and storage must be verified. Cron is not a guaranteed cap. Do not launch without approval."
}, indent=2))
if minutes < 5:
    print("FAIL: Less than 5 minutes planned; do not launch.", file=sys.stderr)
    sys.exit(2)
