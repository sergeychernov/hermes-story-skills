# Telegram skill-command visibility

Use this note when this skill works when typed manually but does not appear in Telegram's slash-command picker.

## Key distinction

Hermes keeps the canonical skill command hyphenated (`/travel-social-publisher`) and converts it to Telegram's compatible form (`/travel_social_publisher`) when building the bot menu. The skill resolver converts the underscore form back to the canonical key. Therefore, do **not** rename the skill directory or blindly change frontmatter from `-` to `_`; Hermes normalizes underscores back to hyphens internally and path changes can break references without fixing menu visibility.

A missing picker entry may instead be caused by Telegram menu truncation. Diagnose both layers:

1. Generate the effective Telegram command menu at the configured cap and check whether `travel_social_publisher` is present.
2. Count its position in the uncapped built-in + plugin + skill ordering.
3. Resolve `travel_social_publisher` through the skill-command resolver and confirm it maps to `/travel-social-publisher`.

If dispatch resolves but the menu entry is absent, treat it as **menu prioritization**, not a naming defect.

## Durable local workaround

When Hermes does not natively prioritize skill entries, use a class-level user plugin such as `telegram-skill-menu-priority` under `~/.hermes/plugins/` that wraps Telegram menu construction at gateway startup. It should:

- pin selected skill commands using their canonical hyphenated keys;
- sanitize the visible Telegram name through Hermes' own helper;
- preserve all built-in and plugin commands;
- replace only an ordinary visible skill at the cap;
- leave command dispatch untouched so `/travel_social_publisher` still resolves through the normal skill handler;
- be generic enough to accept additional pinned skills later.

Enable it with the plugin-specific CLI (`hermes plugins enable <name>`), not a generic config setter containing JSON text: the latter can store a string where `plugins.enabled` must be a YAML list.

## Verification

Before reporting success, verify in a fresh process that:

- plugin discovery marks the plugin enabled with no load error;
- the capped menu contains `travel_social_publisher` exactly once;
- `resolve_skill_command_key("travel_social_publisher")` returns `/travel-social-publisher`;
- the menu length still respects the configured cap.

The Telegram menu is registered when the gateway connects. After changing plugin enablement or menu construction, a gateway restart is required before the picker updates. Do not claim the live picker has changed until that restart has occurred.
