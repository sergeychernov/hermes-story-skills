---
name: collage-layout-design
description: Use when animated-collage has no layout for a photo orientation sequence. Interactively design and approve a new layout.
version: 1.0.0
author: Sergey Chernov / Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [collage, layout-design, interactive, photos, vertical-video]
    related_skills: [animated-collage]
---

# Collage Layout Design

## Overview

Design a collage layout only after `animated-collage` raises `UnsupportedLayoutSequenceError`. This exceptional workflow stays out of the normal rendering context: existing layouts are selected by `animated-collage`; this skill is loaded only when no catalog entry matches the displayed source orientation sequence.

The outcome is either:

- an approved one-off custom geometry for the current collage;
- an approved reusable layout ID added to `animated-collage` with executable geometry and tests;
- an approved split into multiple collage scenes when the source count exceeds renderer capability.

A layout is not approved merely because it renders. The user chooses its grouping, direction, hierarchy, and final preview.

## When to use

Use only when:

- `select_layout(sequence)` raised `UnsupportedLayoutSequenceError`;
- the exception's `sequence` matches the current source order;
- no existing candidate can be selected.

Do not use when:

- `AmbiguousLayoutSequenceError` supplied candidates: show those choices without loading this skill;
- the user has already named a compatible layout ID: validate it through `select_layout(sequence, requested=id)`;
- only animation timing or title placement is changing: keep that in `animated-collage`.

## Interactive workflow

### 1. Re-establish the failed contract

Record:

- the exact sequence from the exception;
- source paths and displayed dimensions in source order;
- current narrative order;
- `hero` and `title_safe` metadata;
- renderer source-count limit.

Treat `p` as displayed width `<` displayed height and `l` as displayed width `>=` displayed height. Do not reorder sources silently to manufacture a catalog match.

Completion criterion: the displayed dimensions reproduce the exception's exact sequence.

### 2. Handle unsupported source counts first

If the sequence is longer than the current renderer limit, ask the user to choose between:

- splitting at a proposed semantic boundary;
- designing and implementing a denser reusable renderer layout.

Show the proposed scene groups when offering a split. Do not truncate, drop, or duplicate photos.

Completion criterion: every source belongs to exactly one approved scene or to the approved new dense layout.

### 3. Ask only decisions that change geometry

Collect these choices interactively:

1. grouping: pairs, triples, hero plus supporting cards, or another explicit grouping;
2. fill direction: descending, ascending, or simultaneous/static;
3. hierarchy: equal cards or named hero source;
4. title zone: which source or empty region may carry text;
5. overlap: tiled, overlapping paper cards, or no preference.

When several answers are already obvious from the user's request, propose defaults rather than asking redundant questions.

Completion criterion: grouping and fill direction are explicit, and title/hero constraints do not conflict.

### 4. Produce candidate layouts

Create two or three candidates unless the user requested one exact geometry. For each candidate provide:

- a stable descriptive ID without project, city, or scene numbers;
- the exact orientation sequence;
- grouping and fill direction;
- source-to-cell mapping;
- normalized `[x,y,w,h]` cells or a named executable geometry preset;
- title-safe region;
- a labeled final-frame preview.

Candidate IDs describe capability, for example `portrait-pairs-ascending`, not `scene-17-layout`.

Completion criterion: every candidate covers the 9:16 canvas, preserves every source once, and has a reviewable preview.

### 5. Obtain explicit choice

Show the candidates together and ask the user to choose one or request a change. Do not infer approval from a preference stated before previews existed.

Completion criterion: one exact candidate revision is approved.

### 6. Materialize the approved layout

For a one-off 3–6 source overlapping collage, encode the approved cells in the scene spec with `layout: overlap_stack`, `base_layout: custom`, and `base_cells`. Keep the orientation sequence and approved candidate ID in the story manifest even though the global catalog is unchanged.

For a reusable layout:

1. add a `LayoutOption` entry to `animated-collage/scripts/layout_selector.py`;
2. add executable geometry and, when relevant, ascending/descending entrance behavior to `render_collage.py`;
3. add capability-oriented tests for exact sequence, geometry, source order, direction, and report fields;
4. prove ambiguity when another layout already uses the same sequence;
5. update `animated-collage/SKILL.md` only after the executable contract passes.

Do not add a selector entry whose layout ID cannot actually be rendered.

Completion criterion: `select_layout(sequence, requested=id)` returns the approved ID and a real render produces the approved geometry.

### 7. Return to animated-collage

Unload this exceptional design context conceptually and resume the normal `animated-collage` render/QA workflow with the approved layout or split scenes.

Completion criterion: the final report records orientation sequence, selected layout ID, source order, and approved visual QA status.

## Common pitfalls

1. **Inventing a fallback.** No match is a design gate, not permission to choose by source count.
2. **Treating ambiguity as failure.** Existing candidates require user choice, not a new layout.
3. **Reordering to force a match.** Preserve narrative order unless the user approves a new order.
4. **Catalog-only additions.** A name without executable geometry is not a layout.
5. **Project archaeology in IDs.** Reusable names describe grouping/direction, never the story where they first appeared.
6. **Silent source splitting.** A split changes the story and requires approval.
7. **Premature approval.** Approve a rendered preview, not a verbal description alone.

## Verification checklist

- [ ] no-match exception and exact sequence recorded
- [ ] displayed source dimensions reproduce the sequence
- [ ] all sources accounted for exactly once
- [ ] grouping, direction, hierarchy, title zone, and overlap decided
- [ ] two or three labeled candidates shown unless one exact layout was requested
- [ ] one exact preview revision explicitly approved
- [ ] one-off geometry saved in the scene spec, or reusable geometry added with tests
- [ ] reusable selector entry is actually renderable
- [ ] ambiguity is preserved when multiple IDs match one sequence
- [ ] final result handed back to `animated-collage` for render and QA
