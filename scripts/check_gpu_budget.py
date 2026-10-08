#!/usr/bin/env python3
"""Offline RunPod budget gate. Never starts, stops, or changes any Pod."""
import argparse
from decimal import Decimal, InvalidOperation
import json


def positive(value):
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("Invalid decimal") from exc
    if not number.is_finite() or number <= 0:
        raise argparse.ArgumentTypeError("Must be positive")
    return number


def main():
    p = argparse.ArgumentParser(description="Estimate affordable GPU minutes; no API requests")
    p.add_argument("--gpu-hourly-usd", required=True, type=positive, help="Verified RunPod GPU $/hour")
    p.add_argument("--storage-hourly-usd", default=Decimal("0"), type=Decimal)
    p.add_argument("--budget-usd", default=Decimal("2"), type=positive)
    p.add_argument("--reserve-usd", default=Decimal("0.50"), type=Decimal)
    p.add_argument("--expected-setup-minutes", required=True, type=positive)
    p.add_argument("--expected-generation-minutes", required=True, type=positive)
    args = p.parse_args()
    if args.storage_hourly_usd < 0 or args.reserve_usd < 0 or args.reserve_usd >= args.budget_usd:
        p.error("Storage must be nonnegative and reserve must be below budget")
    hourly = args.gpu_hourly_usd + args.storage_hourly_usd
    available = args.budget_usd - args.reserve_usd
    affordable_minutes = available * 60 / hourly
    planned_minutes = args.expected_setup_minutes + args.expected_generation_minutes
    planned_cost = planned_minutes * hourly / 60
    allowed = planned_minutes <= affordable_minutes
    print(json.dumps({
        "budget_usd": str(args.budget_usd),
        "reserve_usd": str(args.reserve_usd),
        "verified_total_hourly_usd": str(hourly),
        "affordable_minutes": str(round(affordable_minutes, 2)),
        "planned_minutes": str(planned_minutes),
        "estimated_cost_usd": str(round(planned_cost, 4)),
        "within_budget": allowed,
        "gpu_started": False,
        "warning": "Estimate only; does not guarantee billing caps or automatic stop.",
    }, indent=2))
    if not allowed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
