"""Data-driven campus location matching and floor-level routing."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
import difflib
import re
import unicodedata
from typing import Any, Optional

try:  # RapidFuzz is optional so the resolver remains standard-library usable.
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - exercised only without the extra package.
    fuzz = None


_SPACE_RE = re.compile(r"\s+")
_WRAPPER_PATTERNS = (
    re.compile(r"^(?:please\s+)?(?:can|could|would) you tell me the location of (.+)$"),
    re.compile(r"^(?:please\s+)?(?:can|could|would) you tell me where(?: is)? (.+)$"),
    re.compile(r"^(?:please\s+)?tell me the location of (.+)$"),
    re.compile(r"^(?:please\s+)?tell me where is (.+)$"),
    re.compile(r"^(?:please\s+)?tell me where (.+)$"),
    re.compile(r"^where can i find (.+)$"),
    re.compile(
        r"^(?:please\s+)?(?:what is|whats|where is|wheres) "
        r"(?:the )?location of (.+)$"
    ),
    re.compile(r"^(?:the )?location of (.+)$"),
    re.compile(r"^(?:please\s+)?where(?: is| are|s) (.+)$"),
    re.compile(r"^(?:please\s+)?(?:locate|find) (.+)$"),
    re.compile(r"^(?:which|what) room is (.+?)(?: in)?$"),
)

_GENERIC_LOCATION_TERMS = {"hall", "lab", "laboratory", "room", "block", "building"}


def normalize(text: Any) -> str:
    """Return case-folded text with punctuation removed and spaces collapsed."""

    if text is None:
        return ""

    value = unicodedata.normalize("NFKC", str(text)).casefold()
    value = "".join(
        character if character.isalnum() or character.isspace() else ""
        for character in value
    )
    return _SPACE_RE.sub(" ", value).strip()


def _compact(text: Any) -> str:
    """Return a normalized form that also ignores word-boundary spacing."""

    return normalize(text).replace(" ", "")


def _forms(text: Any) -> tuple[str, str]:
    normalized = normalize(text)
    return normalized, normalized.replace(" ", "")


@dataclass
class LocationResolution:
    """The outcome of resolving one user-supplied location expression."""

    status: str
    canonical: Optional[str] = None
    candidates: list[str] = field(default_factory=list)
    method: str = ""


class LocationResolver:
    """Resolve registered campus names and produce verified floor-level routes."""

    def __init__(
        self,
        locations: Mapping[Any, Any] | None,
        aliases: Mapping[Any, Any] | None,
        campus_graph: Mapping[Any, Any] | None,
    ) -> None:
        self.locations = dict(locations or {})
        self.aliases = dict(aliases or {})
        self.campus_graph = dict(campus_graph or {})

        self._canonical_by_normalized = self._index_keys(self.locations.keys())
        self._canonical_by_compact = self._index_keys(
            self.locations.keys(), compact=True
        )
        self._valid_aliases: dict[str, str] = {}
        self._invalid_aliases: list[str] = []
        self._alias_by_normalized: dict[str, list[str]] = defaultdict(list)
        self._alias_by_compact: dict[str, list[str]] = defaultdict(list)
        self._index_valid_aliases()

    @staticmethod
    def _index_keys(
        keys: Any,
        *,
        compact: bool = False,
    ) -> dict[str, list[str]]:
        index: dict[str, list[str]] = defaultdict(list)
        for key in keys:
            if not isinstance(key, str):
                continue
            value = _compact(key) if compact else normalize(key)
            if value and key not in index[value]:
                index[value].append(key)
        return dict(index)

    def _canonical_target(self, target: Any) -> Optional[str]:
        """Return the actual key for a valid canonical target, if one exists."""

        if not isinstance(target, str):
            return None
        if target in self.locations:
            return target

        # Alias files can contain a corrected spelling of a canonical key.  The
        # campus data currently has ``CHANDRASKHAR HALL`` while its aliases use
        # ``CHANDRASEKHAR HALL``.  Reconcile only a high-confidence, unique
        # canonical variant so a bad alias target cannot silently become valid.
        target_forms = _forms(target)
        exact = self._lookup_index(
            target_forms[0], self._canonical_by_normalized
        ) or self._lookup_index(target_forms[1], self._canonical_by_compact)
        if len(exact) == 1:
            return exact[0]

        ranked = sorted(
            (
                (self._similarity(target, canonical), canonical)
                for canonical in self.locations
                if isinstance(canonical, str)
            ),
            key=lambda item: (-item[0], item[1]),
        )
        if not ranked or ranked[0][0] < 95.0:
            return None
        if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 2.0:
            return None
        return ranked[0][1]

    def _index_valid_aliases(self) -> None:
        """Index only aliases whose targets identify a canonical location."""

        for alias, target in self.aliases.items():
            if not isinstance(alias, str):
                continue
            canonical = self._canonical_target(target)
            if not normalize(alias):
                continue
            if canonical is None:
                self._invalid_aliases.append(alias)
                continue

            self._valid_aliases[alias] = canonical
            normalized = normalize(alias)
            compact = _compact(alias)
            if canonical not in self._alias_by_normalized[normalized]:
                self._alias_by_normalized[normalized].append(canonical)
            if canonical not in self._alias_by_compact[compact]:
                self._alias_by_compact[compact].append(canonical)

    @staticmethod
    def _unique(values: Any) -> list[str]:
        return list(dict.fromkeys(value for value in values if isinstance(value, str)))

    def _lookup_index(
        self,
        candidate: str,
        index: Mapping[str, list[str]],
    ) -> list[str]:
        return self._unique(index.get(candidate, []))

    def _exact_canonical(self, candidate: str) -> list[str]:
        normalized = self._lookup_index(
            normalize(candidate), self._canonical_by_normalized
        )
        if normalized:
            return normalized
        return self._lookup_index(_compact(candidate), self._canonical_by_compact)

    def _exact_alias(self, candidate: str) -> list[str]:
        normalized = self._lookup_index(
            normalize(candidate), self._alias_by_normalized
        )
        if normalized:
            return normalized
        return self._lookup_index(_compact(candidate), self._alias_by_compact)

    @staticmethod
    def _clean_candidate(candidate: str) -> str:
        candidate = candidate.strip()
        previous = None
        while candidate and candidate != previous:
            previous = candidate
            candidate = re.sub(r"^(?:the|a)\s+", "", candidate)
            candidate = re.sub(r"^(?:the )?location of\s+", "", candidate)
            candidate = re.sub(r"\s+(?:please|located|is|are)$", "", candidate)
        return candidate.strip()

    def _looks_like_invalid_alias(self, candidate: str) -> bool:
        """Keep unsupported registered spellings from reaching fuzzy matching."""

        if not self._invalid_aliases:
            return False
        candidate_forms = _forms(candidate)
        for alias in self._invalid_aliases:
            if candidate_forms[0] == normalize(alias) or candidate_forms[1] == _compact(alias):
                return True
            if self._similarity(candidate, alias) >= 92.0:
                return True
        return False

    def _extract_candidate(self, text: Any) -> Optional[str]:
        """Extract a location expression without treating arbitrary text as one."""

        query = normalize(text)
        if not query:
            return None

        # Bare names and aliases are deliberately admitted only after the exact
        # indexes are built. This keeps greetings such as "hello" out of fuzzy
        # matching and still permits registered short aliases such as "sh".
        if self._exact_canonical(query) or self._exact_alias(query):
            return query

        for pattern in _WRAPPER_PATTERNS:
            match = pattern.match(query)
            if match:
                candidate = self._clean_candidate(match.group(1))
                return candidate or None

        # Fuzzy matching for a bare expression is useful for a misspelled hall
        # name, but only location-shaped text can reach it.
        if re.search(r"\b(?:hall|lab|laboratory|room|block|building)\b", query):
            return self._clean_candidate(query) or None
        return None

    @staticmethod
    def _similarity(left: str, right: str) -> float:
        left_normalized, left_compact = _forms(left)
        right_normalized, right_compact = _forms(right)
        if fuzz is not None:
            return max(
                float(fuzz.ratio(left_normalized, right_normalized)),
                float(fuzz.ratio(left_compact, right_compact)),
            )
        return max(
            difflib.SequenceMatcher(None, left_normalized, right_normalized).ratio()
            * 100,
            difflib.SequenceMatcher(None, left_compact, right_compact).ratio() * 100,
        )

    def _fuzzy(self, candidate: str) -> LocationResolution:
        """Fuzzy-match only the extracted candidate, rejecting weak near-ties."""

        labels: list[tuple[str, str]] = [
            (canonical, canonical) for canonical in self.locations if isinstance(canonical, str)
        ]
        labels.extend(
            (alias, canonical)
            for alias, canonical in self._valid_aliases.items()
            if len(_compact(alias)) >= 4
        )

        scores: dict[str, float] = {}
        for label, canonical in labels:
            score = self._similarity(candidate, label)
            scores[canonical] = max(score, scores.get(canonical, 0.0))

        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        if not ranked:
            return LocationResolution("not_found", method="fuzzy")

        best_canonical, best_score = ranked[0]
        threshold = 91.0 if len(_compact(candidate)) <= 5 else 87.0
        if best_score < threshold:
            return LocationResolution("not_found", method="fuzzy")

        near = [
            canonical
            for canonical, score in ranked[1:]
            if score >= threshold and best_score - score < 5.0
        ]
        if near:
            return LocationResolution(
                "ambiguous",
                candidates=self._unique([best_canonical, *near]),
                method="fuzzy_ambiguous",
            )

        return LocationResolution(
            "resolved",
            canonical=best_canonical,
            method="fuzzy",
        )

    def resolve(self, text: Any) -> LocationResolution:
        """Resolve a bare name, valid alias, or wrapped location question."""

        candidate = self._extract_candidate(text)
        if not candidate:
            return LocationResolution("not_found", method="not_location")

        if normalize(candidate) in _GENERIC_LOCATION_TERMS:
            generic_candidates = [
                canonical
                for canonical in self.locations
                if isinstance(canonical, str)
                and normalize(candidate) in normalize(canonical).split()
            ]
            return LocationResolution(
                "ambiguous",
                candidates=generic_candidates,
                method="generic_ambiguous",
            )

        canonical = self._exact_canonical(candidate)
        if len(canonical) == 1:
            return LocationResolution(
                "resolved",
                canonical=canonical[0],
                method="exact_canonical",
            )
        if len(canonical) > 1:
            return LocationResolution(
                "ambiguous",
                candidates=canonical,
                method="exact_canonical_ambiguous",
            )

        aliases = self._exact_alias(candidate)
        if len(aliases) == 1:
            return LocationResolution(
                "resolved",
                canonical=aliases[0],
                method="exact_alias",
            )
        if len(aliases) > 1:
            return LocationResolution(
                "ambiguous",
                candidates=aliases,
                method="exact_alias_ambiguous",
            )

        if self._looks_like_invalid_alias(candidate):
            return LocationResolution("not_found", method="invalid_alias")

        return self._fuzzy(candidate)

    def find_location(self, text: Any) -> Optional[str]:
        """Return a canonical key for a resolved query, or ``None`` otherwise."""

        resolution = self.resolve(text)
        return resolution.canonical if resolution.status == "resolved" else None

    def is_ambiguous(self, text: Any) -> bool:
        """Report whether a query has multiple plausible locations."""

        return self.resolve(text).status == "ambiguous"

    def find_floor(self, location: Any) -> Optional[Any]:
        """Return the graph floor for a verified canonical location."""

        resolution = self.resolve(location)
        if resolution.status != "resolved" or resolution.canonical is None:
            return None

        target_forms = _forms(resolution.canonical)
        matched_floors: list[Any] = []
        for floor, entries in self.campus_graph.items():
            for entry in self._graph_entries(entries):
                if _forms(entry) == target_forms or _compact(entry) == target_forms[1]:
                    if floor not in matched_floors:
                        matched_floors.append(floor)
                    break

        return matched_floors[0] if len(matched_floors) == 1 else None

    @staticmethod
    def _graph_entries(entries: Any) -> list[str]:
        if isinstance(entries, str):
            return [entries]
        if isinstance(entries, Mapping):
            for key in ("locations", "rooms", "entries", "nodes"):
                value = entries.get(key)
                if isinstance(value, str):
                    return [value]
                if isinstance(value, (list, tuple, set)):
                    return [item for item in value if isinstance(item, str)]
            return [key for key in entries if isinstance(key, str)]
        if isinstance(entries, (list, tuple, set, frozenset)):
            return [item for item in entries if isinstance(item, str)]
        return []

    def generate_route(self, start: Any, destination: Any) -> Optional[list[str]]:
        """Generate steps only when both endpoints resolve to one graph floor."""

        start_resolution = self.resolve(start)
        destination_resolution = self.resolve(destination)
        if (
            start_resolution.status != "resolved"
            or destination_resolution.status != "resolved"
            or start_resolution.canonical is None
            or destination_resolution.canonical is None
        ):
            return None

        start_floor = self.find_floor(start_resolution.canonical)
        destination_floor = self.find_floor(destination_resolution.canonical)
        if start_floor is None or destination_floor is None:
            return None

        route = [
            "This route uses the floor-level campus graph; it is not a room-by-room path.",
            f"Start at {start_resolution.canonical} on {start_floor}.",
        ]
        if start_floor == destination_floor:
            route.append(
                f"Stay on {destination_floor} and proceed to {destination_resolution.canonical}."
            )
        else:
            route.extend(
                [
                    f"Move from {start_floor} to {destination_floor} using the building connection.",
                    f"Proceed to {destination_resolution.canonical} on {destination_floor}.",
                ]
            )
        return route

    def get_route(self, start: Any, destination: Any) -> Optional[list[str]]:
        """Compatibility alias for :meth:`generate_route`."""

        return self.generate_route(start, destination)

    def route(self, start: Any, destination: Any) -> Optional[list[str]]:
        """Compatibility alias for :meth:`generate_route`."""

        return self.generate_route(start, destination)
