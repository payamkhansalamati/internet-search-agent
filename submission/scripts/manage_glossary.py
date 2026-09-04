import argparse

from search_agent.glossary import GlossaryStore
from search_agent.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate, approve, reject, or roll back sustainability glossary data")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("validate")
    approve = subcommands.add_parser("approve")
    approve.add_argument("candidate_ids", nargs="+")
    approve.add_argument("--reviewer", required=True)
    reject = subcommands.add_parser("reject")
    reject.add_argument("candidate_ids", nargs="+")
    reject.add_argument("--reviewer", required=True)
    rollback = subcommands.add_parser("rollback")
    rollback.add_argument("version")
    args = parser.parse_args()

    settings = get_settings()
    store = GlossaryStore(settings.glossary_path, settings.glossary_review_path, settings.glossary_history_path)
    if args.command == "validate":
        glossary = store.load()
        print(f"valid glossary {glossary.document.glossary_version}")
    elif args.command == "approve":
        print(f"approved {store.approve(set(args.candidate_ids), args.reviewer)} candidates")
    elif args.command == "reject":
        print(f"rejected {store.reject(set(args.candidate_ids), args.reviewer)} candidates")
    else:
        store.rollback(args.version)
        print(f"rolled back to {args.version}")


if __name__ == "__main__":
    main()
