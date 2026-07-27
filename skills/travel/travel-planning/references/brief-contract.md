# Travel brief contract v1

Required root fields are `schema_version`, `id`, `title`, `status`, `travelers`, `constraints`, `route`, `capture_suggestions`, and `sources`.

- `status`: `draft` or `validated`.
- `constraints.avoid_modes`: case-insensitive hard exclusions such as `ferry`; values and route modes normalize to lowercase.
- `route.legs`: ordered objects containing non-empty `mode`, `from`, and `to`.
- `sources`: map/transit evidence with an absolute HTTPS URL and an ISO-8601 observation timestamp including timezone.
- `capture_suggestions`: optional travel observations, not Story approvals.

The Story projection has only generic context fields. Domain data is nested under `context.extensions.travel` so the `story` skill remains independent of travel.
