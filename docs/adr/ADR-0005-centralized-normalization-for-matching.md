# ADR-0005: Centralized Normalization for Cross-Bookmaker Matching

- Status: Accepted
- Date: 2026-02-10
- Owners: Matcher Platform

## Context
Bookmakers use inconsistent naming for competitions, events, teams, and selections.
Without canonical normalization, event grouping and odds matching become unreliable.

## Decision
Use one normalization service as source of truth:
- normalize competition names to canonical keys
- normalize teams/events for cross-bookmaker grouping
- normalize selection names with `selection_key` priority where available
- support fuzzy matching as fallback safety

## Consequences
Benefits:
- consistent event grouping across platforms
- fewer false mismatches in matcher
- reusable logic across API, worker, and validation

Tradeoffs:
- mapping tables need ongoing maintenance
- wrong alias can create silent matching drift

## Alternatives Considered
1. Per-scraper normalization:
- rejected due to duplication and drift.

2. Fuzzy matching only:
- rejected; too error-prone without canonical maps.

## Follow-ups
- Expand normalization tests with Entain/Punterstech/Kindred edge cases.
- Keep market-shape and selection-key checks aligned with normalization outputs.

