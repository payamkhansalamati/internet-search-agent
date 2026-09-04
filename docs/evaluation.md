# Evaluation

`evaluation/cases.json` covers conversation bypass, indexed research, freshness-triggered search, one-company questions, and comparisons. It contains no claimed scores.

For a reproducible run, create a clean Python 3.12 environment, install `.[dev]`, run `pytest`, then run `python scripts/evaluate_agent.py`. Automated tests mock model/search behavior and require neither keys nor internet. A fuller evaluation should freeze an indexed corpus and mocked search fixtures, then record route correctness, source precision, citation support, warning recall, latency, and failure behavior. Human review remains necessary for table-derived figures and comparability.

