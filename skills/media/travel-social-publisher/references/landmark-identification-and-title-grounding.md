# Landmark identification and title grounding

Use this workflow when a travel photo contains a potentially identifiable building, monument, fortification, bridge, mosque, church, tower, or skyline feature and the user wants accurate titles.

## Identification ladder

1. **Preserve the user's provenance separately from visual evidence.** Record statements such as “shot from Galata Bridge” as user-provided context, not as facts inferred from pixels.
2. **Inspect discriminating visual features.** Count minarets/towers, compare dome or roof geometry, façade materials, waterfront or hillside placement, nearby buildings, orientation, and visible signage. Avoid recognition from overall resemblance alone.
3. **Triangulate the sightline.** Search maps/geocoding for candidates around the stated viewpoint. Check whether each candidate's coordinates, elevation, and relation to water/streets are compatible with the camera direction.
4. **Verify with an external place source.** Prefer an official site or authoritative tourism/cultural source; OpenStreetMap/Nominatim is useful for coordinates and exact POI names. A general encyclopedia can support stable architectural facts but should not be the only source for a contested identity.
5. **Compare the strongest alternative explicitly.** State one concrete reason the image is not the most plausible look-alike (for example, waterfront vs hillside position, number of minarets, or surrounding complex).
6. **Assign confidence.** Use `high`, `medium`, or `low`; do not silently turn a probable match into certainty.

## Title rules

- Use the proper landmark name in title candidates only at high or well-supported medium confidence.
- When useful, pair the local name with a familiar translation once: `Yeni Cami (Новая мечеть)`; do not overload every title with aliases.
- Make the three options semantically distinct: direct place label, atmospheric/local-language variant, and one kind self-ironic observation.
- If confidence is low, title the verified viewpoint or district instead of the building.
- Preserve exact user wording as provenance. Treat it as final only when the user clearly chooses it; otherwise follow the three-title gate.

## Framing consequences

Identification affects crop safety. Before reframing a landscape landmark for 9:16, list the identity-bearing features that must remain visible. If a crop would remove a minaret, bridge, moon, sign, or separated skyline feature, use `contain` over a blurred background or a designed collage rather than a destructive center crop.

## Example pattern

A night photo reported as taken from Galata Bridge shows a waterfront mosque in Eminönü with two minarets and cascading domes. Map triangulation places `Yeni Camii` directly at the waterfront; the lower waterfront setting distinguishes it from Süleymaniye Mosque on the hill. Record the match as high confidence, use `Yeni Cami` or `Новая мечеть` in title options, and preserve both minarets when converting the wide image to vertical.