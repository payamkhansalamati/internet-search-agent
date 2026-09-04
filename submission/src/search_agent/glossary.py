import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from search_agent.domain import Evidence

DEFAULT_GLOSSARY_PATH = Path("config/sustainability_glossary.yaml")


class Provenance(BaseModel):
    source_document: str
    company: str | None
    report_year: int | None
    pdf_page: int | None
    printed_page: str | None
    supporting_text: str
    extracted_at: datetime
    confidence: float = Field(ge=0, le=1)
    approval_status: Literal["pending", "approved", "rejected"]
    approved_by: str | None = None


class Concept(BaseModel):
    id: str
    canonical_name: str
    definition: str
    aliases: list[str] = []
    abbreviations: list[str] = []
    related_concepts: list[str] = []
    non_equivalent_terms: list[str] = []
    expected_units: list[str] = []
    qualifiers: list[str] = []
    query_expansion: list[str] = []
    value_patterns: list[str] = []
    provenance: list[Provenance]

    @field_validator("provenance", mode="before")
    @classmethod
    def provenance_as_list(cls, value: object) -> object:
        return value if isinstance(value, list) else [value]


class UnitDefinition(BaseModel):
    id: str
    canonical: str
    aliases: list[str]
    pattern: str
    broader_unit: str | None = None
    suppressed_by: list[str] = []
    provenance: list[Provenance]

    @field_validator("provenance", mode="before")
    @classmethod
    def provenance_as_list(cls, value: object) -> object:
        return value if isinstance(value, list) else [value]


class Qualifier(BaseModel):
    id: str
    definition: str
    provenance: list[Provenance]

    @field_validator("provenance", mode="before")
    @classmethod
    def provenance_as_list(cls, value: object) -> object:
        return value if isinstance(value, list) else [value]


class GlossaryDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    glossary_version: str
    concepts: list[Concept]
    units: list[UnitDefinition]
    qualifiers: list[Qualifier]

    @model_validator(mode="after")
    def validate_references_and_duplicates(self) -> "GlossaryDocument":
        _unique([concept.id for concept in self.concepts], "concept id")
        _unique([unit.id for unit in self.units], "unit id")
        _unique([qualifier.id for qualifier in self.qualifiers], "qualifier id")
        concept_ids = {concept.id for concept in self.concepts}
        unit_ids = {unit.id for unit in self.units}
        qualifier_ids = {qualifier.id for qualifier in self.qualifiers}
        terms: dict[str, str] = {}
        for concept in self.concepts:
            for term in (concept.canonical_name, *concept.aliases, *concept.abbreviations):
                key = term.casefold().strip()
                if key in terms and terms[key] != concept.id:
                    raise ValueError(f"concept term conflict: {term!r} belongs to {terms[key]} and {concept.id}")
                terms[key] = concept.id
            _references(concept.related_concepts, concept_ids, f"{concept.id}.related_concepts")
            _references(concept.expected_units, unit_ids, f"{concept.id}.expected_units")
            _references(concept.qualifiers, qualifier_ids, f"{concept.id}.qualifiers")
            if {item.casefold() for item in concept.non_equivalent_terms} & {
                item.casefold() for item in (concept.canonical_name, *concept.aliases, *concept.abbreviations)
            }:
                raise ValueError(f"{concept.id} marks one of its synonyms as non-equivalent")
        unit_terms: dict[str, str] = {}
        for unit in self.units:
            re.compile(unit.pattern, re.I)
            for term in (unit.canonical, *unit.aliases):
                key = term.casefold().strip()
                if key in unit_terms and unit_terms[key] != unit.id:
                    raise ValueError(f"unit term conflict: {term!r} belongs to {unit_terms[key]} and {unit.id}")
                unit_terms[key] = unit.id
            if unit.broader_unit and unit.broader_unit not in unit_ids:
                raise ValueError(f"unknown broader unit {unit.broader_unit!r}")
            _references(unit.suppressed_by, unit_ids, f"{unit.id}.suppressed_by")
        return self


class ReviewCandidate(BaseModel):
    candidate_id: str
    kind: Literal["concept", "alias", "unit", "relationship"]
    term: str
    canonical_id: str | None = None
    relationship: str | None = None
    proposed_entry: dict[str, object]
    provenance: Provenance

    @model_validator(mode="after")
    def validate_support(self) -> "ReviewCandidate":
        if self.term.casefold() not in self.provenance.supporting_text.casefold():
            raise ValueError("candidate term is absent from its exact supporting text")
        if self.provenance.approval_status == "approved" and not self.provenance.approved_by:
            raise ValueError("approved candidates require an approver")
        return self


class ReviewQueue(BaseModel):
    schema_version: Literal[1] = 1
    candidates: list[ReviewCandidate] = []


class SustainabilityGlossary:
    def __init__(self, document: GlossaryDocument) -> None:
        self.document = document
        self._concept_patterns = [
            (
                concept,
                re.compile(
                    r"(?<!\w)(?:" + "|".join(re.escape(term) for term in _concept_terms(concept) if term) + r")(?!\w)",
                    re.I,
                ),
            )
            for concept in document.concepts
        ]
        self._unit_patterns = [(unit, re.compile(unit.pattern, re.I)) for unit in document.units]

    @classmethod
    def load(cls, path: Path) -> "SustainabilityGlossary":
        return cls(GlossaryDocument.model_validate(yaml.safe_load(path.read_text(encoding="utf-8"))))

    @classmethod
    def load_default(cls) -> "SustainabilityGlossary":
        return cls.load(DEFAULT_GLOSSARY_PATH)

    def concepts_for(self, text: str) -> list[Concept]:
        return [concept for concept, pattern in self._concept_patterns if pattern.search(text)]

    def expand_query(self, query: str) -> list[str]:
        match = re.search(r"\b(?:19|20)\d{2}\b", query)
        year = match.group(0) if match else "reporting year"
        return [" ".join((*concept.query_expansion, year)) for concept in self.concepts_for(query)]

    def row_bonus(self, query: str, text: str) -> float:
        return sum(
            0.8
            for concept in self.concepts_for(query)
            if any(re.search(pattern, text, re.I | re.S) for pattern in concept.value_patterns)
        )

    def normalize_units(self, text: str) -> tuple[str, ...]:
        matched = [unit for unit, pattern in self._unit_patterns if pattern.search(text)]
        suppressed = {unit.broader_unit for unit in matched if unit.broader_unit}
        matched_ids = {unit.id for unit in matched}
        return tuple(
            unit.canonical
            for unit in matched
            if unit.id not in suppressed and not (set(unit.suppressed_by) & matched_ids)
        )

    def synthesis_guidance(self, question: str) -> str:
        concepts = self.concepts_for(question)
        if not concepts:
            return ""
        rows = []
        for concept in concepts:
            qualifiers = ", ".join(concept.qualifiers) or "none"
            non_equivalent = ", ".join(concept.non_equivalent_terms) or "none"
            rows.append(
                f"{concept.canonical_name}: {concept.definition} Qualifiers: {qualifiers}. "
                f"Do not treat as equivalent: {non_equivalent}."
            )
        return "\n".join(rows)


class GlossaryStore:
    def __init__(self, glossary_path: Path, review_path: Path, history_path: Path) -> None:
        self.glossary_path = glossary_path
        self.review_path = review_path
        self.history_path = history_path

    def load(self) -> SustainabilityGlossary:
        return SustainabilityGlossary.load(self.glossary_path)

    def queue(self, candidates: list[ReviewCandidate]) -> int:
        queue = self._review_queue()
        existing = {candidate.candidate_id for candidate in queue.candidates}
        additions = [candidate for candidate in candidates if candidate.candidate_id not in existing]
        if additions:
            queue.candidates.extend(additions)
            _atomic_write(self.review_path, json.dumps(queue.model_dump(mode="json"), indent=2))
        return len(additions)

    def approve(self, candidate_ids: set[str], approved_by: str) -> int:
        queue = self._review_queue()
        selected = [
            candidate
            for candidate in queue.candidates
            if candidate.candidate_id in candidate_ids and candidate.provenance.approval_status == "pending"
        ]
        if len(selected) != len(candidate_ids):
            raise ValueError("one or more candidate IDs are not pending")
        raw = yaml.safe_load(self.glossary_path.read_text(encoding="utf-8"))
        self._snapshot(raw)
        for candidate in selected:
            _merge_candidate(raw, candidate, approved_by)
        raw["glossary_version"] = _next_version(str(raw["glossary_version"]))
        validated = GlossaryDocument.model_validate(raw)
        _atomic_write(self.glossary_path, yaml.safe_dump(validated.model_dump(mode="json"), sort_keys=False))
        queue.candidates = [candidate for candidate in queue.candidates if candidate.candidate_id not in candidate_ids]
        _atomic_write(self.review_path, json.dumps(queue.model_dump(mode="json"), indent=2))
        return len(selected)

    def reject(self, candidate_ids: set[str], reviewed_by: str) -> int:
        queue = self._review_queue()
        selected = [
            candidate
            for candidate in queue.candidates
            if candidate.candidate_id in candidate_ids and candidate.provenance.approval_status == "pending"
        ]
        if len(selected) != len(candidate_ids):
            raise ValueError("one or more candidate IDs are not pending")
        for candidate in selected:
            candidate.provenance.approval_status = "rejected"
            candidate.provenance.approved_by = reviewed_by
        _atomic_write(self.review_path, json.dumps(queue.model_dump(mode="json"), indent=2))
        return len(selected)

    def rollback(self, version: str) -> None:
        snapshot = self.history_path / f"glossary-{version}.yaml"
        if not snapshot.exists():
            raise ValueError(f"unknown glossary version {version}")
        raw = yaml.safe_load(snapshot.read_text(encoding="utf-8"))
        GlossaryDocument.model_validate(raw)
        self._snapshot(yaml.safe_load(self.glossary_path.read_text(encoding="utf-8")))
        _atomic_write(self.glossary_path, yaml.safe_dump(raw, sort_keys=False))

    def _review_queue(self) -> ReviewQueue:
        if not self.review_path.exists():
            return ReviewQueue()
        return ReviewQueue.model_validate_json(self.review_path.read_text(encoding="utf-8"))

    def _snapshot(self, raw: dict[str, object]) -> None:
        self.history_path.mkdir(parents=True, exist_ok=True)
        path = self.history_path / f"glossary-{raw['glossary_version']}.yaml"
        if not path.exists():
            _atomic_write(path, yaml.safe_dump(raw, sort_keys=False))


def discover_candidates(evidence: list[Evidence], glossary: SustainabilityGlossary) -> list[ReviewCandidate]:
    candidates: list[ReviewCandidate] = []
    known_terms = {term.casefold() for concept in glossary.document.concepts for term in _concept_terms(concept)}
    known_units = {term.casefold() for unit in glossary.document.units for term in (unit.canonical, *unit.aliases)}
    for item in evidence:
        for line in (line.strip(" |") for line in item.text.splitlines() if line.strip()):
            compact = " ".join(line.split())
            if len(compact) > 500:
                continue
            for match in re.finditer(r"\b\d[\d,.]*\s+([A-Za-zµμ³₂%][A-Za-z0-9µμ³₂% /.-]{0,35})", compact):
                unit = match.group(1).strip(" .;,:|")
                if unit.casefold() not in known_units and not glossary.normalize_units(unit):
                    candidates.append(_candidate("unit", unit, item, compact, 0.72, {"canonical": unit}))
            metric = _metric_label(compact)
            if metric and metric.casefold() not in known_terms and not glossary.concepts_for(metric):
                candidates.append(
                    _candidate(
                        "concept",
                        metric,
                        item,
                        compact,
                        0.68,
                        {"canonical_name": metric, "definition": f"Candidate KPI evidenced as: {compact}"},
                    )
                )
            relationship = re.search(r"^(.{2,80}?)\s+(includes?|excludes?|comprises?)\s+(.{2,120})$", compact, re.I)
            if relationship:
                candidates.append(
                    _candidate(
                        "relationship",
                        relationship.group(1).strip(),
                        item,
                        compact,
                        0.7,
                        {"target": relationship.group(3).strip()},
                        relationship.group(2).casefold(),
                    )
                )
        for concept in glossary.document.concepts:
            for term in _concept_terms(concept):
                alias_match = re.search(rf"{re.escape(term)}\s*\(([A-Z][A-Z0-9-]{{1,12}})\)", item.text, re.I)
                if alias_match and alias_match.group(1).casefold() not in known_terms:
                    candidates.append(
                        _candidate(
                            "alias",
                            alias_match.group(1),
                            item,
                            alias_match.group(0),
                            0.9,
                            {"alias": alias_match.group(1)},
                            canonical_id=concept.id,
                        )
                    )
    return list({candidate.candidate_id: candidate for candidate in candidates}.values())


def _candidate(
    kind: Literal["concept", "alias", "unit", "relationship"],
    term: str,
    item: Evidence,
    supporting_text: str,
    confidence: float,
    proposal: dict[str, object],
    relationship: str | None = None,
    canonical_id: str | None = None,
) -> ReviewCandidate:
    if term.casefold() not in supporting_text.casefold():
        raise ValueError("candidate term must occur in its supporting evidence")
    identity = f"{kind}|{term.casefold()}|{item.document_id}|{item.pdf_page}|{supporting_text}"
    provenance = Provenance(
        source_document=item.title,
        company=item.company,
        report_year=item.year,
        pdf_page=item.pdf_page,
        printed_page=item.printed_page,
        supporting_text=supporting_text,
        extracted_at=datetime.now(UTC),
        confidence=confidence,
        approval_status="pending",
    )
    return ReviewCandidate(
        candidate_id=hashlib.sha256(identity.encode()).hexdigest()[:20],
        kind=kind,
        term=term,
        canonical_id=canonical_id,
        relationship=relationship,
        proposed_entry=proposal,
        provenance=provenance,
    )


def _merge_candidate(raw: dict[str, object], candidate: ReviewCandidate, approved_by: str) -> None:
    provenance = candidate.provenance.model_copy(update={"approval_status": "approved", "approved_by": approved_by})
    concepts = raw["concepts"]
    units = raw["units"]
    assert isinstance(concepts, list) and isinstance(units, list)
    if candidate.kind == "alias":
        concept = next(item for item in concepts if item["id"] == candidate.canonical_id)
        concept.setdefault("aliases", []).append(candidate.term)
        _append_provenance(concept, provenance)
    elif candidate.kind == "concept":
        identifier = _slug(candidate.term)
        concepts.append(
            {
                "id": identifier,
                "canonical_name": candidate.term,
                "definition": candidate.proposed_entry["definition"],
                "aliases": [],
                "abbreviations": [],
                "related_concepts": [],
                "non_equivalent_terms": [],
                "expected_units": [],
                "qualifiers": candidate.proposed_entry.get("qualifiers", []),
                "query_expansion": [candidate.term],
                "value_patterns": [rf"{re.escape(candidate.term)}.{{0,160}}\d"],
                "provenance": [provenance.model_dump(mode="json")],
            }
        )
    elif candidate.kind == "unit":
        identifier = _slug(candidate.term)
        units.append(
            {
                "id": identifier,
                "canonical": candidate.term,
                "aliases": [candidate.term],
                "pattern": re.escape(candidate.term),
                "broader_unit": None,
                "suppressed_by": [],
                "provenance": [provenance.model_dump(mode="json")],
            }
        )
    else:
        source = _raw_concept_for_term(concepts, candidate.term)
        target_term = str(candidate.proposed_entry["target"])
        target = _raw_concept_for_term(concepts, target_term)
        if candidate.relationship == "excludes":
            non_equivalent = source.setdefault("non_equivalent_terms", [])
            assert isinstance(non_equivalent, list)
            non_equivalent.append(str(target["canonical_name"]))
        else:
            related = source.setdefault("related_concepts", [])
            assert isinstance(related, list)
            related.append(str(target["id"]))
        _append_provenance(source, provenance)


def _append_provenance(entry: dict[str, object], provenance: Provenance) -> None:
    current = entry.get("provenance", [])
    rows = current if isinstance(current, list) else [current]
    rows.append(provenance.model_dump(mode="json"))
    entry["provenance"] = rows


def _raw_concept_for_term(concepts: list[object], term: str) -> dict[str, object]:
    for raw in concepts:
        assert isinstance(raw, dict)
        terms = [raw.get("canonical_name", ""), *raw.get("aliases", []), *raw.get("abbreviations", [])]
        if term.casefold() in {str(item).casefold() for item in terms}:
            return raw
    raise ValueError(f"relationship term {term!r} is not an approved concept")


def _metric_label(line: str) -> str | None:
    if "|" in line:
        label = line.split("|", 1)[0].strip()
    elif match := re.match(r"([^:]{3,100}):\s*[-+]?\d", line):
        label = match.group(1).strip()
    else:
        return None
    return label if 2 <= len(label.split()) <= 12 and not re.fullmatch(r"[-: ]+", label) else None


def _concept_terms(concept: Concept) -> tuple[str, ...]:
    return (concept.canonical_name, *concept.aliases, *concept.abbreviations)


def _unique(values: list[str], label: str) -> None:
    folded = [value.casefold() for value in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"duplicate {label}")


def _references(values: list[str], allowed: set[str], label: str) -> None:
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"unknown references in {label}: {sorted(unknown)}")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _next_version(version: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
