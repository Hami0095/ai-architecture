"""Loads and validates standards configuration (archai_standards.yaml).

Rules are only ever what the user configured, plus clearly labelled ArchAI
defaults. Nothing here encodes an organization's standards on its behalf.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

DEFAULT_CONFIG_FILENAME = "archai_standards.yaml"
CONFIG_VERSION = 1

RULE_KINDS = {
    "forbidden_dependency",
    "layer_boundary",
    "circular_dependency",
    "coupling_threshold",
    "required_tests",
}

_RULE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")

# The only rule ArchAI evaluates without being asked. It is a widely used
# engineering heuristic, not a universal or customer-mandated standard.
ARCHAI_DEFAULT_RULES: List[Dict[str, Any]] = [
    {
        "id": "archai.default.no-import-cycles",
        "kind": "circular_dependency",
        "description": "Internal Python modules should not form import cycles. (ArchAI default)",
        "rationale": ("ArchAI default heuristic: module-level import cycles can cause "
                      "partially initialised modules and make layers hard to separate. "
                      "This is not your organization's standard unless you adopt it."),
    },
]


class StandardsConfigError(ValueError):
    """Raised for missing, unreadable or malformed configuration."""


@dataclass
class RuleSpec:
    id: str
    kind: str
    description: str
    rationale: str
    origin: str  # "user-config" | "archai-default"
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StandardsConfig:
    rules: List[RuleSpec]
    layers: Dict[str, List[str]] = field(default_factory=dict)
    source_roots: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    path: Optional[str] = None
    sha256: Optional[str] = None
    uses_defaults_only: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "uses_defaults_only": self.uses_defaults_only,
            "source_roots": self.source_roots,
            "exclude": self.exclude,
            "layers": self.layers,
            "rules": [{"id": r.id, "kind": r.kind, "origin": r.origin, "params": r.params}
                      for r in self.rules],
        }


def _str_list(value: Any, where: str, allow_empty: bool = False) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise StandardsConfigError(f"{where} must be a string or a list of non-empty strings.")
    if not value and not allow_empty:
        raise StandardsConfigError(f"{where} must not be empty.")
    return [v.strip() for v in value]


def _require(raw: Dict[str, Any], key: str, where: str) -> Any:
    if key not in raw or raw[key] in (None, "", []):
        raise StandardsConfigError(f"{where}: missing required key '{key}'.")
    return raw[key]


def _parse_rule(raw: Any, index: int, layers: Dict[str, List[str]], origin: str) -> RuleSpec:
    where = f"rules[{index}]"
    if not isinstance(raw, dict):
        raise StandardsConfigError(f"{where} must be a mapping.")
    rule_id = _require(raw, "id", where)
    if not isinstance(rule_id, str) or not _RULE_ID.match(rule_id):
        raise StandardsConfigError(
            f"{where}: id '{rule_id}' must be 1-100 characters of letters, digits, '.', '_' or '-'.")
    where = f"rule '{rule_id}'"
    kind = _require(raw, "kind", where)
    if kind not in RULE_KINDS:
        raise StandardsConfigError(f"{where}: unknown kind '{kind}'. Supported: {', '.join(sorted(RULE_KINDS))}.")

    params: Dict[str, Any] = {}
    if kind == "forbidden_dependency":
        params["from"] = _str_list(_require(raw, "from", where), f"{where}.from")
        params["to"] = _str_list(_require(raw, "to", where), f"{where}.to")
    elif kind == "layer_boundary":
        layer = _require(raw, "layer", where)
        if layer not in layers:
            raise StandardsConfigError(f"{where}: layer '{layer}' is not declared under 'layers'.")
        params["layer"] = layer
        has_forbidden, has_allowed = "forbidden_layers" in raw, "allowed_layers" in raw
        if has_forbidden == has_allowed:
            raise StandardsConfigError(f"{where}: set exactly one of 'forbidden_layers' or 'allowed_layers'.")
        key = "forbidden_layers" if has_forbidden else "allowed_layers"
        names = _str_list(raw[key], f"{where}.{key}", allow_empty=(key == "allowed_layers"))
        unknown = [n for n in names if n not in layers]
        if unknown:
            raise StandardsConfigError(f"{where}.{key}: undeclared layer(s) {', '.join(unknown)}.")
        params[key] = names
    elif kind == "circular_dependency":
        params["scope"] = _str_list(raw.get("scope", ["*"]), f"{where}.scope")
    elif kind == "coupling_threshold":
        metric = raw.get("metric", "fan_out")
        if metric not in ("fan_out", "fan_in"):
            raise StandardsConfigError(f"{where}: metric must be 'fan_out' or 'fan_in'.")
        maximum = _require(raw, "max", where)
        if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 0:
            raise StandardsConfigError(f"{where}: max must be a non-negative integer.")
        params.update(metric=metric, max=maximum,
                      scope=_str_list(raw.get("scope", ["*"]), f"{where}.scope"))
    elif kind == "required_tests":
        params["scope"] = _str_list(_require(raw, "scope", where), f"{where}.scope")
        templates = _str_list(_require(raw, "test_paths", where), f"{where}.test_paths")
        for t in templates:
            if not re.search(r"\{(leaf|module|module_path|parent_path)\}", t):
                raise StandardsConfigError(
                    f"{where}.test_paths: '{t}' uses none of {{leaf}}, {{module}}, {{module_path}}, {{parent_path}}.")
        params["test_paths"] = templates
        params["include_packages"] = bool(raw.get("include_packages", False))

    description = raw.get("description") or f"{kind} rule '{rule_id}'"
    rationale = raw.get("rationale") or "No rationale was supplied in the configuration."
    return RuleSpec(id=rule_id, kind=kind, description=str(description),
                    rationale=str(rationale), origin=origin, params=params)


def parse_config(data: Any, include_defaults: bool = True, path: Optional[str] = None,
                 sha256: Optional[str] = None) -> StandardsConfig:
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise StandardsConfigError("The standards configuration must be a YAML mapping.")
    unknown_top = set(data) - {"version", "layers", "rules", "source_roots", "exclude", "defaults"}
    if unknown_top:
        raise StandardsConfigError(f"Unknown top-level key(s): {', '.join(sorted(unknown_top))}.")
    version = data.get("version", CONFIG_VERSION)
    if version != CONFIG_VERSION:
        raise StandardsConfigError(f"Unsupported config version {version!r}; expected {CONFIG_VERSION}.")

    layers_raw = data.get("layers") or {}
    if not isinstance(layers_raw, dict):
        raise StandardsConfigError("'layers' must map layer names to module patterns.")
    layers = {str(k): _str_list(v, f"layers.{k}") for k, v in layers_raw.items()}

    rules_raw = data.get("rules") or []
    if not isinstance(rules_raw, list):
        raise StandardsConfigError("'rules' must be a list.")
    rules = [_parse_rule(r, i, layers, "user-config") for i, r in enumerate(rules_raw)]

    defaults_setting = data.get("defaults", "auto")
    if defaults_setting not in ("auto", True, False):
        raise StandardsConfigError("'defaults' must be true, false or 'auto'.")
    want_defaults = include_defaults and (defaults_setting is True or (defaults_setting == "auto" and not rules))
    if want_defaults:
        taken = {r.id for r in rules}
        kinds = {r.kind for r in rules}
        for i, raw in enumerate(ARCHAI_DEFAULT_RULES):
            if raw["id"] not in taken and raw["kind"] not in kinds:
                rules.append(_parse_rule(raw, i, layers, "archai-default"))

    ids = [r.id for r in rules]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise StandardsConfigError(f"Duplicate rule id(s): {', '.join(duplicates)}.")

    return StandardsConfig(
        rules=rules,
        layers=layers,
        source_roots=_str_list(data.get("source_roots", []), "source_roots", allow_empty=True),
        exclude=_str_list(data.get("exclude", []), "exclude", allow_empty=True),
        path=path,
        sha256=sha256,
        uses_defaults_only=bool(rules) and all(r.origin == "archai-default" for r in rules),
    )


def load_config(repo_root: Path, config_path: Optional[Path] = None,
                include_defaults: bool = True) -> StandardsConfig:
    """Loads an explicit config, else <repo>/archai_standards.yaml, else defaults only."""
    if config_path is None:
        candidate = Path(repo_root) / DEFAULT_CONFIG_FILENAME
        if not candidate.exists():
            return parse_config({}, include_defaults=include_defaults)
        config_path = candidate
    config_path = Path(config_path)
    if not config_path.is_file():
        raise StandardsConfigError(f"Standards config not found: {config_path}")
    raw_bytes = config_path.read_bytes()
    try:
        data = yaml.safe_load(raw_bytes.decode("utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as e:
        raise StandardsConfigError(f"Could not parse {config_path.name}: {e}") from e
    return parse_config(data, include_defaults=include_defaults, path=config_path.name,
                        sha256=hashlib.sha256(raw_bytes).hexdigest())
