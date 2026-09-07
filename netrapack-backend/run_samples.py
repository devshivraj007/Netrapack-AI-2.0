"""Run the 5 sample inputs through the rule engine and print JSON verdicts.

Usage (from the netrapack-backend directory):
    python run_samples.py
"""

from __future__ import annotations

import json

from app.rule_engine.engine import RuleEngine
from app.schemas.scan import ScanRequest
from tests.sample_inputs import SAMPLES


def main() -> None:
    engine = RuleEngine()
    for sample in SAMPLES:
        req = ScanRequest(**sample)
        verdict = engine.evaluate(req)
        print("=" * 78)
        print(f"INPUT  scan_id={sample['scan_id']}")
        print("-" * 78)
        print(json.dumps(verdict.model_dump(), indent=2, default=str))
        print()


if __name__ == "__main__":
    main()
