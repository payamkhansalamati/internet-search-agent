import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from ai_platform.models import Workload
from ai_platform.planner import plan_workload


def load_workload(path: Path) -> Workload:
    raw: Any = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError("workload file must contain a YAML object")
    return Workload.model_validate(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and plan an AI workload")
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan", help="print a dry-run deployment plan")
    plan.add_argument("workload", type=Path)
    args = parser.parse_args()
    workload = load_workload(args.workload)
    print(json.dumps(plan_workload(workload).as_dict(), indent=2))


if __name__ == "__main__":
    main()
