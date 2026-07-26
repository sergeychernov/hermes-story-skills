# YouTube Shorts UI safe zones and publication semantics

Use this reference when rendering or verifying burned-in text for YouTube Shorts, and when explaining how Shorts appear in YouTube.

## Classification and metadata

- Shorts are classified from the uploaded media, not from `#Shorts`: for current standard channels, vertical or square uploads up to three minutes are treated as Shorts under YouTube's current rules.
- Do not add `#Shorts` to titles or descriptions by default. It consumes scarce title/search context while adding no classification benefit. Add it only when the user explicitly wants it for a campaign or measurable discovery reason.
- Shorts use the same underlying video resource as other YouTube uploads. `/watch?v=<id>` and `/shorts/<id>` can address the same ID. A working watch URL does not prove that the item appears in the public channel's Videos tab.
- Verify the public Shorts and Videos tabs separately. Studio may list all uploaded video resources together even when the public channel separates them.

## Burned-in text safe zone for 1080×1920

YouTube's mobile UI varies by device, locale, account state, and enabled controls. Treat these as conservative defaults, then verify using a real-device screenshot:

- avoid roughly the top 250 px;
- reserve roughly the rightmost 200–230 px for reaction/action controls;
- avoid roughly the bottom 520–600 px, where channel identity, description, audio/remix controls, promotion controls, and navigation can appear;
- keep essential text primarily within approximately `x=70..850`, `y=750..1300`;
- wrap captions conservatively (about 20–22 Cyrillic characters at 48 px) so the box does not intrude into the right control rail;
- use a high-contrast box or outline, but do not rely on the box to rescue text placed behind platform chrome.

For Sergey's shared travel master, aim low while enforcing explicit renderer-wide UI reserves: use `y=min(h*0.80-text_h/2,h-text_h-360)` and constrain the text box's right edge to `x=820` on a 1080-wide frame. The first term targets the lower 4/5 area; the second prevents the box from drifting into the extreme bottom controls; the x constraint avoids the right action rail. These defaults live once in `build_episode.py`, and the manifest template deliberately omits `title_y` / `caption_y` so it cannot silently undo them. Device UI still varies, so inspect the final target preview; use a single package-wide override only when real-device QA demonstrates a collision.

**FFmpeg expression pitfall:** commas inside a `drawtext` option value are filter separators unless escaped. Keep the human-readable formula above in documentation, but emit it as `min(h*0.80-text_h/2\,h-text_h-360)` in the generated filter string. Assert the escaped expression in a unit test, then exercise at least one real FFmpeg render: string-only tests can pass while FFmpeg still rejects the filter graph.

## UI-overlay QA gate

Codec/dimension checks and clean source-frame inspection are insufficient. Before approval:

1. Extract representative frames for the intro and every caption style.
2. Composite them with a current Shorts UI mask or inspect a screenshot from the actual YouTube mobile app.
3. Check top controls, the full right action rail, channel/title/description overlays, promotion controls, and bottom navigation.
4. Require every line to remain readable without hiding UI or requiring the viewer to pause.
5. If a real-device screenshot shows overlap, treat verification as failed even when `verification.json` is green.

## Correcting an already-published Short

YouTube does not replace the media bytes of an existing uploaded video. A burned-in-title correction requires a new render and a new upload. Preserve the existing item until the replacement has been uploaded, processed, classified as a Short, and visually verified.

Treat replacement intent as part of the publish transaction:

- if the approved package declares `replaces_youtube_id`, or the user has already described the draft as a replacement, a standalone **«публикуй»** authorizes the safe replacement sequence by default: upload new → verify processing/title/privacy/public page → validate that the old ID belongs to the same destination channel → delete the old item;
- do not leave both versions public merely because deletion is a separate API call; that creates the duplicate the replacement workflow was intended to avoid;
- keep the old item only when the user explicitly asks to retain it, or when replacement intent is genuinely ambiguous;
- never delete first: if the new upload or processing fails, preserve the old publication;
- before deletion, query the old ID through the API and verify its channel and expected title/context; after deletion, query both IDs and require `old_present=false` and `new_present=true` with the approved visibility;
- write a concise deletion record containing the old ID, timestamp, API result, and replacement ID—never credentials.

Metadata-only corrections can update the existing ID and preserve its URL, views, likes, and comments; they may require the `youtube.force-ssl` OAuth scope in addition to upload/read scopes.
