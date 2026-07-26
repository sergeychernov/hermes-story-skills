---
name: travel-planning
description: Plan a trip or outing by composing maps and live-transit-navigation, preserving traveler constraints and producing an optional capture brief that a domain-neutral story can consume. Use for destinations, routes, day plans, transport choices, or travel capture suggestions; not for editing media or publishing.
---

# Travel Planning

Plan travel; do not build or publish a story here.

## Composition

1. Load `maps` for geocoding, POIs, route geometry, walking/driving alternatives, and shareable map links.
2. Load `live-transit-navigation` when the request needs current public transport, departures, disruptions, or immediate navigation.
3. Treat live provider output as time-sensitive evidence. Record source URLs and observation time in the brief.
4. Preserve stated traveler constraints before optimizing convenience. Reject any route leg whose mode appears in `constraints.avoid_modes`.
5. When useful, suggest moments to capture, but do not choose titles, scene order, animation, music, or publication state.

## Workflow

1. Establish origin, destination, travelers, timing, and hard constraints.
2. Resolve ambiguous places with `maps`.
3. Generate feasible alternatives and eliminate constraint violations.
4. For transit, verify the selected route with `live-transit-navigation` near departure time.
5. Write or validate a versioned travel brief with:

```bash
python3 <skill-dir>/scripts/validate_travel_brief.py brief.json --output normalized.json
```

6. If material should feed a story, pass only the generated Story `context` projection. Travel-specific data belongs under `context.extensions.travel`; never add travel fields to the root Story contract.

## Boundaries

- Does not render, animate, archive, authenticate, or publish media.
- Does not duplicate map or transit-provider implementations.
- A draft plan is not live navigation. Recheck time-sensitive legs when the user starts moving.
- Capture suggestions are optional prompts, not approved Story scenes.

See `references/brief-contract.md` and `templates/travel-brief.json`.
