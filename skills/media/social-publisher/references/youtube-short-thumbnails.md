# YouTube Short thumbnails: vertical-first workflow

Use this when a published Short has a dull, gray, misleading, or poorly cropped cover, or the user asks for a more colorful/clickable thumbnail.

## Do not confuse two thumbnail surfaces

- A Short is a normal YouTube video ID, and `thumbnails.set` may accept a custom JPEG for it.
- **The Shorts channel grid uses a separate portrait-cover surface.** A successful `thumbnails.set` can update `maxresdefault.jpg`, Open Graph, watch/search, and Telegram previews while the Shorts tab still shows an old in-video frame or a gray placeholder. The Data API has no field for selecting that Shorts-grid frame.
- To change the actual Shorts-grid cover after upload, use the owner-facing YouTube/YouTube Studio mobile flow on the Short (`⋮` → edit → edit thumbnail/cover) and either choose the approved custom vertical image when offered or select an in-video frame. Verify the channel's Shorts tab on the real device afterward; if the client offers no post-upload cover control, a replacement upload with the approved cover selected during upload is the last resort and requires new publication approval.
- **API acceptance is not visual verification.** YouTube may show different renditions on the channel/search surfaces and in the vertical Shorts UI.
- A cache-busted `maxresdefault.jpg` is a useful check for the conventional 16:9 thumbnail surface, but it does **not** prove what the user sees as the vertical Short cover.
- For Sergey's Shorts, the requested master is **vertical 1080×1920 (9:16)**. Do not substitute a 1280×720 design merely because conventional YouTube guidance defaults to 16:9.
- If YouTube's client displays a gray frame or an unexpected in-video frame after an API upload, treat that user/device observation as authoritative for the Shorts surface. Do not insist that the CDN response proves the cover is correct.

## Design workflow

1. Inspect the currently visible cover on the actual target surface when accessible. Also fetch `maxresdefault.jpg`, but label it as only the conventional thumbnail rendition.
2. Prefer an authentic, high-resolution source photo over a captioned frame extracted from the rendered video.
3. Create a truthful 1080×1920 cover from the episode's actual hook:
   - clear faces when available;
   - bright but natural saturation and contrast;
   - one large promise/hook plus one short support line;
   - essential text inside generous vertical safe margins;
   - no banner across faces.
4. If the source is less tall than 9:16, use a blurred/cropped copy as the 1080×1920 background, place the unblurred source above or centrally, and reserve a dedicated dark text panel below it.
5. Run a **literal typography QA pass before upload**:
   - compare every city/person/place name against the canonical title or manifest character by character;
   - check spelling, punctuation, and word endings—not only clipping and readability;
   - inspect at full size and at phone-thumbnail size;
   - reject plausible-looking misspellings such as `СТАМБУЛЬ` when the canonical name is `СТАМБУЛ`.

## First-frame safeguard

Before publication, decode and inspect the exact encoded frames at `0.000`, `0.033`, `0.10`, `0.25`, and `0.50` seconds. Never let a Short begin on black/gray/transparent video or a fade-in from blank: some Shorts clients may use or momentarily expose that first decoded frame as the grid cover/placeholder. Put the explicitly approved vertical cover into the video itself for roughly `0.5–0.8` seconds from frame zero, then transition quickly into the opening scene; apply any fade only between visible images, never from blank. Verify the first frame again on the final upload candidate. Changing encoded first frames of an already published Short requires a replacement upload and therefore fresh package/cover/publication approval.

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

## Telegram link-preview cache after a thumbnail change

A corrected YouTube thumbnail and a stale Telegram link card can coexist. Treat them as separate surfaces and verify them independently.

1. Fetch the current YouTube watch-page `og:image` / `twitter:image` and inspect the referenced image. This establishes what YouTube currently advertises, not what Telegram has cached.
2. Do not assume `@WebpageBot` success means every cached URL variant was invalidated. Telegram may retain a preview for the exact previously shared `youtu.be` URL, including its query string.
3. Existing Telegram messages do not retroactively redraw their cards. For a new share, use a fresh URL variant with a harmless query parameter, then verify that exact URL before giving it to the user.
4. When the personal MTProto session is configured, perform a reversible probe: send the fresh URL to Saved Messages with link previews enabled, wait until `MessageMediaWebPage` contains a photo, download and visually inspect that photo, then delete the probe message. This is stronger evidence than checking YouTube CDN thumbnails alone.
5. Report the state precisely: “YouTube advertises the new thumbnail,” “Telegram generated the new preview for this exact fresh URL,” or “the old Telegram card remains cached.” Never call the problem fixed solely because `thumbnails.set` returned success.

Preserve the canonical video ID and avoid implying that a cache-busting URL is a new upload. If analytics attribution is not wanted, use a neutral version parameter rather than inventing campaign semantics.

## Reporting language

Use precise claims:

- `YouTube API accepted the vertical thumbnail` — valid after `thumbnails.set` succeeds.
- `The conventional CDN rendition updated` — valid after visually checking that rendition.
- `The vertical Shorts cover is verified` — say this only after the actual Shorts surface or the user's device shows it.

Never claim universal replacement from API success alone. Mention that some Shorts surfaces may still use an in-video frame and that propagation/cache delay is possible, but do not use caching as an unsupported explanation for a gray screen.
