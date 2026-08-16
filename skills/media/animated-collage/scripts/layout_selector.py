#!/usr/bin/env python3
"""Deterministic orientation-sequence to collage-layout selection."""
from __future__ import annotations

from typing import NamedTuple, Sequence


class LayoutOption(NamedTuple):
    layout_id: str
    orientation_sequence: str
    label: str


DEFAULT_LAYOUT_CATALOG: tuple[LayoutOption, ...] = (
    LayoutOption("stack", "ll", "Two full-width landscape rows"),
    LayoutOption("2+1", "ppl", "Two portrait panels above one landscape panel"),
    LayoutOption("2x2", "pppp", "Two rows of paired portrait panels"),
    LayoutOption("2+1+1", "ppll", "Portrait pair above two landscape rows"),
    LayoutOption("2+1+2", "pplpp", "Portrait pair, landscape hero, portrait pair"),
    LayoutOption("2+2+1", "ppppl", "Two portrait pairs above one landscape row"),
    LayoutOption("portrait-pairs-descending", "pppppp", "Portrait pairs, top to bottom"),
    LayoutOption("portrait-pairs-ascending", "pppppp", "Portrait pairs, bottom to top"),
    LayoutOption("portrait-triples-descending", "pppppp", "Portrait triples, top to bottom"),
    LayoutOption("portrait-triples-ascending", "pppppp", "Portrait triples, bottom to top"),
    LayoutOption("2+2+1+1", "ppppll", "Two portrait pairs above two landscape rows"),
)


class LayoutSequenceError(ValueError):
    def __init__(self, message: str, *, sequence: str, candidates: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.sequence = sequence
        self.candidates = candidates


class UnsupportedLayoutSequenceError(LayoutSequenceError):
    def __init__(self, sequence: str) -> None:
        super().__init__(
            f"no collage layout matches orientation sequence {sequence!r}",
            sequence=sequence,
        )


class AmbiguousLayoutSequenceError(LayoutSequenceError):
    def __init__(self, sequence: str, candidates: tuple[str, ...]) -> None:
        super().__init__(
            f"orientation sequence {sequence!r} matches multiple collage layouts: {', '.join(candidates)}",
            sequence=sequence,
            candidates=candidates,
        )


class IncompatibleLayoutSequenceError(LayoutSequenceError):
    def __init__(self, sequence: str, requested: str, expected_sequences: tuple[str, ...]) -> None:
        super().__init__(
            f"collage layout {requested!r} expects orientation sequence(s) "
            f"{', '.join(expected_sequences)}, got {sequence!r}",
            sequence=sequence,
            candidates=(requested,),
        )
        self.requested = requested
        self.expected_sequences = expected_sequences


def validate_orientation_sequence(sequence: str) -> str:
    if not isinstance(sequence, str):
        raise TypeError("orientation sequence must be a string")
    normalized = sequence.strip().lower()
    if not normalized:
        raise ValueError("orientation sequence must not be empty")
    if any(symbol not in {"p", "l"} for symbol in normalized):
        raise ValueError("orientation sequence may contain only 'p' and 'l'")
    return normalized


def matching_layouts(
    sequence: str,
    *,
    catalog: Sequence[LayoutOption] = DEFAULT_LAYOUT_CATALOG,
) -> tuple[LayoutOption, ...]:
    normalized = validate_orientation_sequence(sequence)
    return tuple(option for option in catalog if option.orientation_sequence == normalized)


def select_layout(
    sequence: str,
    *,
    requested: str | None = None,
    catalog: Sequence[LayoutOption] = DEFAULT_LAYOUT_CATALOG,
) -> str:
    normalized = validate_orientation_sequence(sequence)
    if requested is not None:
        options = tuple(option for option in catalog if option.layout_id == requested)
        if not options:
            raise ValueError(f"unsupported collage layout id: {requested}")
        if not any(option.orientation_sequence == normalized for option in options):
            expected = tuple(dict.fromkeys(option.orientation_sequence for option in options))
            raise IncompatibleLayoutSequenceError(normalized, requested, expected)
        return requested

    matches = matching_layouts(normalized, catalog=catalog)
    if not matches:
        raise UnsupportedLayoutSequenceError(normalized)
    candidates = tuple(dict.fromkeys(option.layout_id for option in matches))
    if len(candidates) > 1:
        raise AmbiguousLayoutSequenceError(normalized, candidates)
    return candidates[0]
