"""The Arches-Instrumentation master alarm catalog, consumed at render time
(Task.md C-07).

``catalog/alarms.yaml``'s header states "the same catalog is consumed by HQ
so alarms render without hardcoding". Until now nothing here read it: a
device alarm could only be shown as a bare numeric code, losing the symbolic
name, probable cause, specific problem, description, escalation rule,
auto-clear policy and ``hq_reportable`` flag.

The catalog is VENDORED at ``app/data/alarms_catalog.yaml`` rather than read
from a sibling repo at runtime -- HQ is a standalone cloud deployable and
must not depend on another checkout at import time. The vendored copy
records its origin in the header comment; re-vendor it (and note the new
source revision) when Instrumentation's catalog changes. Breaking changes to
the locked 32-bit layout itself are a fleet incident, not a re-vendor: the
layout is locked and both the device's C++ header and this loader decode
against it.

Entries marked ``hq_reportable: false`` are device-internal conditions the
catalog explicitly withholds from fleet rendering -- the alarms list and the
web panel skip them. They are still stored, so a device that raises one is
not silently invisible to the API's raw rows.
"""

import functools
from dataclasses import dataclass
from importlib import resources
from typing import Any

import yaml

# The catalog spells ids with positional underscores ("0x1_04_1_0007") but
# the packed value is what arrives on the wire and what DeviceAlarm rows
# store: underscores are presentation, not digits.
DATA_PACKAGE = "app.data"
DATA_FILE = "alarms_catalog.yaml"


@dataclass(frozen=True)
class CatalogEntry:
    """One alarm catalog entry, decoded against the locked 32-bit layout."""

    code: int
    name: str
    severity: str
    probable_cause: str
    specific_problem: str
    description: str
    escalation: str
    auto_clear: str
    hq_reportable: bool

    @property
    def domain(self) -> int:
        return (self.code >> 28) & 0xF

    @property
    def module(self) -> int:
        return (self.code >> 20) & 0xFF

    @property
    def alarm_type(self) -> int:
        return (self.code >> 16) & 0xF

    @property
    def index(self) -> int:
        return self.code & 0xFFFF


@functools.lru_cache(maxsize=1)
def load_catalog() -> dict[int, CatalogEntry]:
    """Parse the vendored catalog into ``{packed_code: entry}``."""
    text = resources.files(DATA_PACKAGE).joinpath(DATA_FILE).read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    entries: dict[int, CatalogEntry] = {}
    for row in doc.get("entries", []):
        # PyYAML parses "0x1_01_3_0001" straight to the packed int (underscores
        # are digit separators in YAML's int resolver); be tolerant of both the
        # int and the raw-string forms.
        raw = row["id"]
        code = raw if isinstance(raw, int) else int(str(raw).replace("_", ""), 16)
        entries[code] = CatalogEntry(
            code=code,
            name=row.get("name", ""),
            severity=row.get("severity", ""),
            probable_cause=row.get("probable_cause", ""),
            specific_problem=row.get("specific_problem", ""),
            description=row.get("description", ""),
            escalation=row.get("escalation", "none"),
            auto_clear=row.get("auto_clear", "manual"),
            hq_reportable=bool(row.get("hq_reportable", True)),
        )
    return entries


def lookup(code: int) -> CatalogEntry | None:
    return load_catalog().get(code)


# ---- locked 32-bit layout --------------------------------------------------
# The decode/encode pair was previously private to the alarms router; with the
# AlarmEvent ingest path sharing it (Task.md C-06), it lives here so both
# callers cannot drift. Source of truth: Arches-Instrumentation's
# catalog/alarms.yaml header (LOCKED).
_DOMAIN_SHIFT, _DOMAIN_MASK = 28, 0xF
_MODULE_SHIFT, _MODULE_MASK = 20, 0xFF
_TYPE_SHIFT, _TYPE_MASK = 16, 0xF
_INDEX_MASK = 0xFFFF


def decode_alarm_code(code: int) -> tuple[int, int, int, int]:
    """Unpack a packed alarm code into ``(domain, module, alarm_type, index)``.

    Severity is deliberately absent -- it travels as its own field, not inside
    the code.
    """
    return (
        (code >> _DOMAIN_SHIFT) & _DOMAIN_MASK,
        (code >> _MODULE_SHIFT) & _MODULE_MASK,
        (code >> _TYPE_SHIFT) & _TYPE_MASK,
        code & _INDEX_MASK,
    )


def encode_alarm_code(domain: int, module: int, alarm_type: int, index: int) -> int:
    """Pack ``(domain, module, alarm_type, index)`` back into a 32-bit code."""
    return (
        ((domain & _DOMAIN_MASK) << _DOMAIN_SHIFT)
        | ((module & _MODULE_MASK) << _MODULE_SHIFT)
        | ((alarm_type & _TYPE_MASK) << _TYPE_SHIFT)
        | (index & _INDEX_MASK)
    )


def reportable(code: int) -> bool:
    """Whether the catalog surfaces this code to fleet rendering (C-07)."""
    entry = load_catalog().get(code)
    return True if entry is None else entry.hq_reportable


def enrich(code: int) -> dict[str, Any]:
    """Catalog fields for a packed code, or {} when the code is unknown."""
    entry = load_catalog().get(code)
    if entry is None:
        return {}
    return {
        "name": entry.name,
        "probable_cause": entry.probable_cause,
        "specific_problem": entry.specific_problem,
        "description": entry.description,
        "escalation": entry.escalation,
        "auto_clear": entry.auto_clear,
        "hq_reportable": entry.hq_reportable,
    }