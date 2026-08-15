# FFmpeg Titling Recipes for Shorts

## Title style (canonical)

The canonical title style is implemented by `scripts/brand_title_style.py` and consumed by every title-capable renderer. Never duplicate font paths, size, weight, spacing, box opacity, border, or safe-zone expressions in project scripts. Reports must record `style_version`, resolved font path, and font SHA-256 so the look remains reproducible across sessions and hosts.

Canonical v2 values at 1080 px width:

```text
style_version=sergey-vertical-title-v2
font=DejaVuSans-Bold.ttf (resolved by helper; hash recorded)
font_weight=Bold
box=1:boxcolor=black@0.406:boxborderw=24
fontsize=54
line_spacing=12
fontcolor=white
position=lower_fifth; complete box bottom=h*0.72
```

Scale numeric values proportionally for other widths via the helper. If the exact font file is unavailable, fail explicitly rather than silently changing the brand.

This produces a semi-transparent dark background box behind the text, which is
far more readable over complex backgrounds (grass, patterns, moving video) than
the old `borderw=3` outline style.

**Do NOT use `borderw=3:bordercolor=black`** — it is the deprecated old style.
Always use the box style above.

## drawtext textfile workaround

`drawtext` `text=` treats colons as filter-option delimiters.
Any text containing `:` (times, URLs) or other special chars breaks the filter chain.

**Fix:** write all title lines to a single textfile with `\n` separators and use `textfile=`:

```bash
printf '6:00 AM\nПодарок получен\nСпать отменяется' > titles.txt
```

## Title Y position (proportional, resolution-independent)

The `LOWER_FIFTH_Y` formula in `still_image_animation.py` is:

```
y=min(h*0.80-text_h/2, h-text_h-h*0.1875)
```

- `h*0.80` — center the text block at 80% of height (lower fifth).
- `h*0.1875` — proportional safe bottom margin (18.75% of height).

**Never use a fixed pixel value like `360`** — it is correct for 1080×1920
(360/1920 = 18.75%) but pushes titles to 57% height on 720×1280
(360/1280 = 28%, clamping the `min()` too early).

Resolved Y for common resolutions (3-line text, ~194px tall):

| Resolution  | h*0.80   | h-text_h-h*0.1875 | Y (min) | % of height |
|-------------|----------|--------------------|---------|-------------|
| 720×1280    | 927      | 846                | 846     | 66.1%       |
| 1080×1920   | 1439     | 1366               | 1366    | 71.1%       |

## Title overlay on existing video (box style, single multi-line drawtext)

```bash
# Use -preset veryfast for 720p to avoid terminal timeouts.
# -preset slow can exceed 180s on 720×1280 with drawtext.
ffmpeg -y -i input.mp4 \
  -vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:\
textfile=titles.txt:fontcolor=white:fontsize=54:line_spacing=12:\
x=max(70,min((w-text_w)/2,820-text_w)):\
y=min(h*0.80-text_h/2,h-text_h-h*0.1875):\
box=1:boxcolor=black@0.406:boxborderw=24:enable='between(t,1,10)'" \
  -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p \
  -c:a copy \
  output-titled.mp4
```

Key parameters:
- `line_spacing=12` — spacing between multi-line text
- `box=1:boxcolor=black@0.406:boxborderw=24` — semi-transparent background box
- `x=max(70,min((w-text_w)/2,820-text_w))` — centered with safe margins
- `y=min(h*0.80-text_h/2,h-text_h-h*0.1875)` — lower fifth, proportional safe margin
- `enable='between(t,1,10)'` — appear at 1s, disappear at 10s (adjust per clip)

## Still photo → animated video (PREFERRED: use still-image-animation skill)

Always prefer the `still-image-animation` skill's `animate_still.py` script:

```bash
python3 <skill-dir>/scripts/animate_still.py --root . --spec clip-spec.json
```

This handles pan/zoom, title overlay (same box style), fade in/out, and produces
a JSON verification report. Do NOT create static stills with bare ffmpeg.

## Shell quoting safety

Complex ffmpeg filter chains with backslash-continued lines and nested quotes
can break in inline `terminal()` commands. Two reliable approaches:

1. Write a `.sh` script to the project workdir (not `/tmp` — may be blocked by
   `HERMES_WRITE_SAFE_ROOT`) and run via `bash script.sh`.
2. Keep the filter string on a single line (no backslash continuations).

## FLUX 3 image_to_video: child photo rejection

`bfl_flux3_image_to_video` returns:
```
status: Request Moderated
Moderation Reasons: ["Protected Content"]
```
for any photo containing a child, even in benign family contexts.
This consumes a generation credit with no output.

**Fallback:** use `still-image-animation` skill (`animate_still.py` with
pan/zoom), which is not subject to content moderation and produces better
results for known subjects anyway.