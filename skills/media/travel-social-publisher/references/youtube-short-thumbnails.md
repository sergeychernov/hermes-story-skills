# YouTube Short thumbnails — compatibility forwarding reference

This compatibility facade does not own YouTube thumbnail dimensions, surfaces or publication behavior.

Before preparing or publishing a YouTube cover, load `social-publisher` and read its canonical `references/youtube-short-thumbnails.md`. Cover rendering and exact platform contracts belong to `static-cover-collage`.

Current routing invariant:

- YouTube Data API `thumbnails.set` receives the native wide `youtube_api_thumbnail` at 3840×2160 (16:9).
- Never route a portrait Shorts/mobile cover to `thumbnails.set`; doing so can create padding, blurred side fields or inefficient use of the landscape surface.
- Portrait opening-frame and Shorts-grid/mobile covers are separate optional surfaces and require separate generation and approval.
- The external write remains blocked until explicit publication approval.

Do not duplicate mutable platform dimensions or safe-zone policy in this compatibility skill.
