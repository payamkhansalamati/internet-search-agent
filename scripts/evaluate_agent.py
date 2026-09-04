import json
from pathlib import Path


def main() -> None:
    cases = json.loads(Path("evaluation/cases.json").read_text())
    print(f"Loaded {len(cases)} deterministic cases. Run pytest for automated checks.")


if __name__ == "__main__":
    main()
