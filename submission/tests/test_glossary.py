from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from search_agent.domain import Evidence
from search_agent.glossary import (
    GlossaryDocument,
    GlossaryStore,
    SustainabilityGlossary,
    discover_candidates,
)

GLOSSARY = Path("config/sustainability_glossary.yaml")


def test_approved_glossary_is_valid_and_drives_all_vocabulary_consumers() -> None:
    glossary = SustainabilityGlossary.load(GLOSSARY)
    assert all(qualifier.provenance for qualifier in glossary.document.qualifiers)
    assert glossary.normalize_units("Energy 9,012 thousand gigajoules") == ("thousand GJ",)
    assert glossary.normalize_units("Emissions 94 in 1,000 metric tons of CO2e") == ("kt CO2e",)
    assert any("location based" in query for query in glossary.expand_query("Compare Scope 2 in 2024"))
    assert glossary.row_bonus("total waste", "total amount of waste 345.5") > 0
    assert "Do not treat as equivalent" in glossary.synthesis_guidance("renewable electricity")


def test_schema_rejects_duplicate_aliases_conflicts_and_unknown_relationships() -> None:
    raw = yaml.safe_load(GLOSSARY.read_text())
    raw["concepts"][1]["aliases"].append("direct emissions")
    with pytest.raises(ValidationError, match="concept term conflict"):
        GlossaryDocument.model_validate(raw)

    raw = yaml.safe_load(GLOSSARY.read_text())
    raw["concepts"][0]["related_concepts"].append("not_a_concept")
    with pytest.raises(ValidationError, match="unknown references"):
        GlossaryDocument.model_validate(raw)


def test_discovery_queues_evidence_supported_candidates_without_modifying_glossary(tmp_path: Path) -> None:
    glossary_path = tmp_path / "glossary.yaml"
    glossary_path.write_text(GLOSSARY.read_text())
    review_path = tmp_path / "review.json"
    store = GlossaryStore(glossary_path, review_path, tmp_path / "history")
    glossary = store.load()
    evidence = [
        Evidence(
            "| Biodiversity restoration index | 47 habitat credits |",
            "Example sustainability report",
            "https://example.com/report.pdf",
            "Example Corp",
            2025,
            pdf_page=18,
            document_id="example-2025",
            printed_page="16",
        )
    ]
    before = glossary_path.read_text()
    candidates = discover_candidates(evidence, glossary)
    assert candidates
    assert all(candidate.provenance.supporting_text in evidence[0].text for candidate in candidates)
    assert all(candidate.provenance.pdf_page == 18 for candidate in candidates)
    assert store.queue(candidates) == len(candidates)
    assert store.queue(candidates) == 0
    assert glossary_path.read_text() == before


def test_explicit_approval_is_versioned_atomic_and_rollback_restores_snapshot(tmp_path: Path) -> None:
    glossary_path = tmp_path / "glossary.yaml"
    glossary_path.write_text(GLOSSARY.read_text())
    review_path = tmp_path / "review.json"
    history_path = tmp_path / "history"
    store = GlossaryStore(glossary_path, review_path, history_path)
    evidence = [
        Evidence(
            "Nature intensity: 12 eco-units",
            "New report",
            "https://example.com/new.pdf",
            "New Corp",
            2026,
            pdf_page=8,
            document_id="new-2026",
        )
    ]
    concepts = [candidate for candidate in discover_candidates(evidence, store.load()) if candidate.kind == "concept"]
    assert concepts and store.queue(concepts) == len(concepts)
    store.approve({concepts[0].candidate_id}, "reviewer@example.com")
    approved = store.load().document
    assert approved.glossary_version == "1.0.1"
    added = next(concept for concept in approved.concepts if concept.canonical_name == "Nature intensity")
    assert added.provenance[-1].approval_status == "approved"
    assert added.provenance[-1].source_document == "New report"
    assert (history_path / "glossary-1.0.0.yaml").exists()
    store.rollback("1.0.0")
    assert store.load().document.glossary_version == "1.0.0"


def test_production_modules_do_not_reference_regression_fixtures() -> None:
    production = "\n".join(path.read_text() for path in Path("src").rglob("*.py"))
    assert "tests/fixtures" not in production
    assert "abb_siemens_2024_kpis" not in production


def test_legacy_scattered_vocabulary_definitions_were_removed() -> None:
    parsing = Path("src/search_agent/ingestion/parsing.py").read_text()
    retrieval = Path("src/search_agent/retrieval/service.py").read_text()
    assert "UNIT_PATTERNS" not in parsing
    assert "KPI_ASPECTS" not in retrieval
    assert "kt\\s*CO" not in parsing
    assert "scope\\s*1" not in retrieval
