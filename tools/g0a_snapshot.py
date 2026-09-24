"""Print the current G0A descriptor candidate without publishing a freeze."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from xgtest.core.contract_set import build_contract_descriptor


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="write the candidate descriptor to this path")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    payload = json.dumps(build_contract_descriptor(root), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(args.output)


if __name__ == "__main__":
    main()
