from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Report:
    company: str
    year: int
    title: str
    url: str
