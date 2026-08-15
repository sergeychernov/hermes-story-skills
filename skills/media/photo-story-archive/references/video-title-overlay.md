# Video Title Overlay with FFmpeg

Use this reference when adding text titles/annotations to video clips for Shorts, Reels, or Stories packages. This complements `references/video-and-publishing-pipeline.md` which covers video inspection and platform export.

## Core pitfall: colon-escaping in drawtext

FFmpeg `drawtext` filter uses colon (`:`) as a filter-graph separator. Passing text containing colons — e.g. `text='6:00 AM'` — causes a parse error:

```
[AVFilterGraph] No option name near '00 AM:fontsize=...'
Error parsing a filter description around: ...
```

### Fix: use textfile= instead of text=

Write each text string to a temporary file, then reference it with `textfile=`:

```bash
printf '6:00 AM' > /tmp/t1.txt
printf 'Подарок получен' > /tmp/t2.txt
printf 'Спать отменяется' > /tmp/t3.txt

ffmpeg -y \
  -i input.mp4 \
  -vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:\
textfile=/tmp/t1.txt:fontsize=52:fontcolor=white:borderw=3:bordercolor=black:\
x=(w-text_w)/2:y=h*0.72:enable='between(t,1,9)',\
drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:\
textfile=/tmp/t2.txt:fontsize=42:fontcolor=white:borderw=3:bordercolor=black:\
x=(w-text_w)/2:y=h*0.80:enable='between(t,2.5,9)',\
drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:\
textfile=/tmp/t3.txt:fontsize=42:fontcolor=white:borderw=3:bordercolor=black:\
x=(w-text_w)/2:y=h*0.87:enable='between(t,4,9)'" \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
  -c:a copy \
  output_titled.mp4
```

### Alternative: escape colons in text=

If `textfile=` is impractical, escape colons with backslash:

```
text='6\:00 AM'
```

The `textfile=` approach is cleaner for multi-line titles and avoids all escaping ambiguity.

## Title placement for vertical Shorts (9:16)

- Place titles in the lower third (y = 0.72–0.90 of frame height) to avoid covering faces and central action.
- Use white text with black border (`borderw=3:bordercolor=black`) for readability over varied backgrounds.
- Stagger title lines with `enable='between(t,start,end)'` to build a cascading reveal.
- Large header (fontsize 52) for the lead line; smaller (fontsize 42) for secondary lines.
- Keep total title duration within the clip's visible window; fade out before clip end.

## Title choice workflow

Per the `story` skill, offer exactly three concise title choices after each new video:

1. direct/descriptive;
2. atmospheric/narrative;
3. self-ironic, observational and kind.

Persist the exact choice set. Apply the user's selection as the overlay text via the above ffmpeg command.

## Scene-adaptive title placement

The vertical position may stay in the lower fifth while the horizontal position changes per scene. Do not assume a centered title is safe throughout a moving clip.

- Inspect at least the start, main reveal/midpoint, and final frame. Add a frame where a person or key object enters late.
- If a centered title covers a late-arriving person or action, shift the box left or right within horizontal safe margins rather than moving it to the top.
- Account for `boxborderw`: the box extends beyond the drawtext `x` coordinate.
- Re-render and inspect the exact collision frame. A title that is safe at the midpoint can still fail in the final second.

For example, use `x=70` for a short left-aligned title when the subject enters near the lower center/right; retain the normal lower-fifth `y` expression.

## Spoken clips: preserve the full timeline and process derivative audio

Speech is part of the scene contract. Do not trim a clip merely because the opening is dark, shaky, or visually quiet. Unless the user explicitly approves an exact cut, omit `-ss`, `-t`, `--start`, and `--end` and render the full source. A later instruction to “leave the whole clip” invalidates all earlier trim decisions.

When denoise and normalization are requested, process only the derivative audio and re-encode it rather than stream-copying:

```bash
ffmpeg -i input.mp4 \
  -vf "scale=1080:1920,fps=30,drawtext=..." \
  -af "afftdn=nr=12:nf=-35:tn=1,loudnorm=I=-16:LRA=11:TP=-1.5" \
  -c:v libx264 -c:a aac -b:a 192k -ar 48000 \
  output.mp4
```

Avoid hard gates and silence removal: they can cut quiet consonants, word endings, and low-level phrases. Explicitly force 48 kHz because `loudnorm` may otherwise leave a 96 kHz result depending on the filter graph.

Verify stream-level timing and the encoded audio, not only `format.duration` or configured targets:

```bash
ffprobe -v error \
  -show_entries format=start_time,duration:stream=index,codec_type,start_time,duration \
  -of json output.mp4
```

Check that:

- a full render spans the complete source video and audio timelines, allowing only codec/frame rounding;
- video and audio start together within roughly one output frame;
- the finished encoded file decodes through its final word;
- measured EBU R128 integrated loudness is near target and measured true peak does not clip;
- start, midpoint/reveal, final frame, first word, and last word are all intact.

See `references/spoken-video-audio-integrity.md` for the complete integrity checklist and failure patterns.

## Verification

After rendering, extract a mid-clip frame and visually inspect it (vision_analyze) to confirm:

- All expected text lines are present and readable;
- Text is well-positioned (not covering faces/key subjects);
- Font size and contrast are adequate for mobile viewing.

```bash
ffmpeg -y -i output_titled.mp4 -ss 5 -frames:v 1 -update 1 /tmp/titled_preview.jpg
```

## Project folder layout for Shorts assembly

When collecting multiple clips for a YouTube Shorts compilation:

```text
ilya-shorts/YYYY-MM-DD-event/
├── clip01-6am-gift.mp4       # original
├── clip01-titled.mp4         # with overlay
├── clip02-*.mp4
├── clip02-titled.mp4
├── ...
├── shorts-final.mp4          # assembled final
└── publish-manifest.md
```

Name clips with two-digit sequence + short scene name. Keep originals alongside titled versions for re-editing flexibility.