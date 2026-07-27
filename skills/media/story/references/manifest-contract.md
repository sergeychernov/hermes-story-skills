# Story manifest v1

The canonical root is deliberately domain-neutral. Accepted root fields are `schema_version`, `id`, `title`, `status`, `story_type`, `arc`, `scenes`, `context`, and `publication`; readiness fields are derived by validation.

Travel, cooking, project, family, or event details belong under `context.extensions.<domain>`. This keeps a story reusable and prevents an optional source of context from becoming an architectural dependency.

A scene requires a stable `id`, stable archive `media_id`, `kind` (`image` or `video`), and approval state. Full render is ready only when at least one scene exists and every scene is approved.

`publication.status` is editorial state only. External writes are exclusively owned by `social-publisher` and still require its explicit gates.
