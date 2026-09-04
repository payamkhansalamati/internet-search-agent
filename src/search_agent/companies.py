from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True, slots=True)
class Company:
    name: str
    aliases: tuple[str, ...]
    domains: tuple[str, ...]
    warning: str | None = None


class CompanyRegistry:
    def __init__(self, companies: list[Company]) -> None:
        self.companies = companies

    @classmethod
    def load(cls, path: Path) -> "CompanyRegistry":
        data = yaml.safe_load(path.read_text())
        return cls(
            [Company(x["name"], tuple(x["aliases"]), tuple(x["domains"]), x.get("warning")) for x in data["companies"]]
        )

    def resolve(self, text: str) -> list[Company]:
        lowered = text.casefold()
        return [c for c in self.companies if any(a.casefold() in lowered for a in (c.name, *c.aliases))]

    def approved_domains(self) -> set[str]:
        return {domain.casefold() for company in self.companies for domain in company.domains}
