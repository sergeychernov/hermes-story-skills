# YouTube Short thumbnails: vertical-first workflow

Use this when a published Short has a dull, gray, misleading, or poorly cropped cover, or the user asks for a more colorful/clickable thumbnail.

## Surface-specific cover package

Do not design or approve one ambiguous “YouTube cover.” Route each artifact by the actual platform operation:

1. **API thumbnail — 3840×2160, 16:9.** This is the native landscape asset passed to `thumbnails.set` for watch/search, Open Graph, CDN renditions and Telegram link previews. Never pass a portrait image and accept padding, blurred side fields or an automatic 16:9 fit as the finished design.
2. **Optional opening-frame cover — video-native 9:16.** Embed only when the approved video should visibly begin on a cover frame. It is part of the encoded Short, not the API thumbnail.
3. **Optional Shorts-grid/mobile cover — portrait.** Prepare only when the owner-facing mobile selector is part of the requested workflow. The Data API cannot select or verify this surface.

The API publishing path requires the wide API thumbnail. Opening-frame and Shorts-grid artifacts are separate optional surfaces, generated and approved only when requested. Store independent hashes; approval never transfers between surfaces.

## Do not confuse two thumbnail surfaces

- A Short is a normal YouTube video ID, and `thumbnails.set` may accept a custom JPEG for it.
- **The Shorts channel grid uses a separate portrait-cover surface.** A successful `thumbnails.set` can update `maxresdefault.jpg`, Open Graph, watch/search, and Telegram previews while the Shorts tab still shows an old in-video frame or a gray placeholder. The Data API has no field for selecting that Shorts-grid frame.
- To change the actual Shorts-grid cover after upload, use the owner-facing YouTube/YouTube Studio mobile flow on the Short (`⋮` → edit → edit thumbnail/cover) and either choose the approved custom vertical image when offered or select an in-video frame. Verify the channel's Shorts tab on the real device afterward; if the client offers no post-upload cover control, a replacement upload with the approved cover selected during upload is the last resort and requires new publication approval.
- **API acceptance is not visual verification.** YouTube may show different renditions on the channel/search surfaces and in the vertical Shorts UI.
- A cache-busted `maxresdefault.jpg` is a useful check for the conventional 16:9 thumbnail surface, but it does **not** prove what the user sees as the vertical Short cover.
- For Sergey's API publication workflow, the required master is the native wide **3840×2160 (16:9)** `youtube_api_thumbnail`. Portrait covers are separate optional surfaces and must never be routed to `thumbnails.set`.
- If YouTube's client displays a gray frame or an unexpected in-video frame after an API upload, treat that user/device observation as authoritative for the Shorts surface. Do not insist that the CDN response proves the cover is correct.

## Design workflow

1. Inspect the currently visible API thumbnail/CDN rendition and the actual target surfaces when accessible.
2. Prefer authentic high-resolution sources and compose the API thumbnail natively at **3840×2160 (16:9)**. Fill the landscape canvas intentionally; no portrait fit, blurred side fields, letterboxing or empty padding.
3. Use a truthful editorial hierarchy: one clear hero, supporting context and concise title. Keep all text and essential subjects inside a conservative inner 5% margin; this margin is local policy because YouTube does not publish numeric text-safe coordinates on the cited size page.
4. When an optional portrait opening-frame or Shorts-grid cover is requested, build it as a separate 9:16 composition and apply its own mobile UI-safe policy. Do not resize the wide API thumbnail into portrait or route portrait pixels back into `thumbnails.set`.
5. Run literal typography, bounds, crop and phone-size QA. Compare names against canonical metadata character by character and reject clipping or plausible misspellings.
6. Deliver the exact wide JPEG/PNG and wait for explicit approval before `thumbnails.set`, including an in-place update. Any changed bytes require fresh approval.
7. Keep claims surface-specific: API/CDN verification does not prove the optional portrait Shorts-grid surface.

## First-frame safeguard

Before publication, decode and inspect exact encoded frames `0`, `1`, `2`, `3`, and `4`. Never let a Short begin on black/gray/transparent video or a fade-in from blank. For Sergey's YouTube Shorts publication path, frames `0..3` must be the same approved vertical safe-zone-compliant cover and frame `4` must be the first live frame; one-frame and longer cover intervals are invalid. The publisher rechecks this boundary from the immutable video snapshot before OAuth. Apply any fade only after frame `4` and never from blank. Changing encoded first frames of an already published Short requires a replacement upload and therefore fresh package/cover/publication approval.

## Upload pattern

Refresh OAuth, then upload the JPEG bytes to:

```text
POST https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=<VIDEO_ID>&uploadType=media
Authorization: Bearer <access token>
Content-Type: image/jpeg
```

Expected response kind: `youtube#thumbnailSetResponse`. Never print or persist OAuth tokens.

## Verification hierarchy

1. Confirm the API response contains an item and ETag; record this only as **accepted**, not displayed.
2. Re-fetch YouTube metadata/CDN renditions after propagation and inspect them visually.
3. Open the `/shorts/<id>` surface or obtain a real-device screenshot when possible. This check outranks CDN assumptions for a Short.
4. Ask the user to verify the actual client only when the authenticated/mobile surface cannot be inspected. If they report gray or incorrect imagery, revise rather than arguing from API success.
5. Record the local path, SHA-256, source dimensions, video ID, API acceptance, and which surfaces were actually verified.

## Telegram link-preview cache and first-share gate

A corrected YouTube thumbnail and a stale Telegram link card can coexist. Treat them as separate surfaces and verify them independently. Telegram Bot API has no reliable operation for globally purging the cached preview of a URL.

**Before the first Telegram share of a newly uploaded YouTube video:** do not place the clickable YouTube URL in the publication-success message. Telegram may crawl and cache it immediately, before the owner completes the Shorts cover choice. Report only the non-linked video ID, verify YouTube's conventional CDN/OG image, wait for the user's cover decision, and expose the URL only after explicit approval/request. If the user needs a deterministic Telegram post, send the approved cover as a Telegram photo with the URL in its caption, or send text with `link_preview_options={"is_disabled": true}` (legacy wrappers may expose `disable_web_page_preview=true`).

1. Fetch the current YouTube watch-page `og:image` / `twitter:image` and inspect the referenced image. This establishes what YouTube currently advertises, not what Telegram has cached.
2. Do not assume `@WebpageBot` success means every cached URL variant was invalidated. Telegram may retain a preview for the exact previously shared `youtu.be` URL, including its query string.
3. Existing Telegram messages do not retroactively redraw their cards. For a new share, use a fresh URL variant with a harmless query parameter, then verify that exact URL before giving it to the user.
4. When the personal MTProto session is configured, perform a reversible probe: send the fresh URL to Saved Messages with link previews enabled, wait until `MessageMediaWebPage` contains a photo, download and visually inspect that photo, then delete the probe message. This is stronger evidence than checking YouTube CDN thumbnails alone.
5. Report the state precisely: “YouTube advertises the new thumbnail,” “Telegram generated the new preview for this exact fresh URL,” or “the old Telegram card remains cached.” Never call the problem fixed solely because `thumbnails.set` returned success.

Preserve the canonical video ID and avoid implying that a cache-busting URL is a new upload. If analytics attribution is not wanted, use a neutral version parameter rather than inventing campaign semantics.

## Reporting language

Use precise claims:

- `YouTube API accepted the wide 16:9 thumbnail` — valid after `thumbnails.set` succeeds.
- `The conventional CDN rendition updated` — valid after visually checking that rendition.
- `The vertical Shorts cover is verified` — say this only after the actual Shorts surface or the user's device shows it.

Never claim universal replacement from API success alone. Mention that some Shorts surfaces may still use an in-video frame and that propagation/cache delay is possible, but do not use caching as an unsupported explanation for a gray screen.
