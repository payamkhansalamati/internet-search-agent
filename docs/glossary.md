# Sustainability glossary

`config/sustainability_glossary.yaml` is the approved, version-controlled single source of truth for sustainability
concepts and unit normalization. Production code contains matching, validation, ranking, and persistence logic only;
canonical KPI names, definitions, synonyms, abbreviations, relationships, non-equivalent terms, expected units,
qualifiers, query expansions, value-row patterns, and unit mappings live in the glossary.

Each approved concept and unit has provenance. Provenance records the source document, company, report year,
physical PDF page, printed page label, exact supporting text, UTC extraction time, confidence, approval status, and
reviewer. The initial entries record their migration from the previously reviewed production rules.

## Ingestion and review

Every ingestion compares extracted page and table evidence with the approved glossary. Unfamiliar candidate KPI
labels, aliases, units, and explicit `includes`, `excludes`, or `comprises` relationships are written to
`config/glossary-review-queue.json`. A candidate is accepted only when its proposed term occurs in its retained
supporting evidence. Discovery never edits the approved glossary and rejected candidates remain in the queue with
their review status so they are not repeatedly proposed.

Review the evidence and then use:

```bash
python scripts/manage_glossary.py validate
python scripts/manage_glossary.py approve CANDIDATE_ID --reviewer "name@example.com"
python scripts/manage_glossary.py reject CANDIDATE_ID --reviewer "name@example.com"
python scripts/manage_glossary.py rollback 1.0.0
```

Approval validates duplicates, alias conflicts, references, regular expressions, and synonym/non-equivalence
conflicts before replacing the glossary atomically. The previous version is retained under
`config/glossary-history/`. Relationship candidates can be approved only after both concepts are approved;
`excludes` becomes a non-equivalence assertion, while `includes` and `comprises` become related-concept links.

Restart API and ingestion processes after an approval so subsequent parsing, normalization, query expansion,
retrieval, reranking, and synthesis load the new approved version. Re-ingest existing documents if newly approved
unit normalization must be added to their stored chunk metadata.
