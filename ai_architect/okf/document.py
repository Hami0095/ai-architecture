"""OKF v0.2 concept documents: markdown with YAML frontmatter.

Follows SPEC.md of https://github.com/GoogleCloudPlatform/open-knowledge-format
(v0.2). Parsing mirrors the reference implementation's behaviour of keeping
timestamps as the strings the author wrote, so parse/serialize round-trips.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import yaml

OKF_VERSION = "0.2"
FRONTMATTER_DELIM = "---"
RESERVED_FILENAMES = ("index.md", "log.md")


class _Loader(yaml.SafeLoader):
    """SafeLoader without the YAML 1.1 timestamp resolver (values stay strings)."""


_Loader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


class OKFDocumentError(ValueError):
    pass


@dataclass
class OKFDocument:
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    body: str = ""
    has_frontmatter: bool = True

    @classmethod
    def parse(cls, text: str) -> "OKFDocument":
        lines = text.splitlines()
        if not lines or lines[0].strip() != FRONTMATTER_DELIM:
            return cls(frontmatter={}, body=text, has_frontmatter=False)
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == FRONTMATTER_DELIM), None)
        if end is None:
            raise OKFDocumentError("Unterminated YAML frontmatter block")
        try:
            data = yaml.load("\n".join(lines[1:end]), Loader=_Loader) or {}
        except yaml.YAMLError as e:
            raise OKFDocumentError(f"Invalid YAML in frontmatter: {e}") from e
        if not isinstance(data, dict):
            raise OKFDocumentError("Frontmatter must be a YAML mapping")
        body = "\n".join(lines[end + 1:])
        if body.startswith("\n"):
            body = body[1:]
        return cls(frontmatter=data, body=body, has_frontmatter=True)

    def serialize(self) -> str:
        body = self.body if self.body.endswith("\n") else self.body + "\n"
        if not self.has_frontmatter:
            return body
        fm = yaml.safe_dump(self.frontmatter, sort_keys=False, allow_unicode=True,
                            default_flow_style=False, width=4096).rstrip()
        return f"{FRONTMATTER_DELIM}\n{fm}\n{FRONTMATTER_DELIM}\n\n{body}"


def normalize_verified(frontmatter: Dict[str, Any]) -> List[Dict[str, Any]]:
    """OKF §5.2: a bare `verified` mapping is a one-element list."""
    verified = frontmatter.get("verified")
    if isinstance(verified, dict):
        return [verified]
    if isinstance(verified, list):
        return [v for v in verified if isinstance(v, dict)]
    return []


def trust_tier(frontmatter: Dict[str, Any]) -> str:
    """OKF §5.3: unverified | machine-confirmed | human-reviewed."""
    events = normalize_verified(frontmatter)
    if not events:
        return "unverified"
    if any(str(e.get("by", "")).startswith("human:") for e in events):
        return "human-reviewed"
    return "machine-confirmed"
