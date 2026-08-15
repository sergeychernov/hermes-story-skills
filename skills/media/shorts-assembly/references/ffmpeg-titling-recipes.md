# FFmpeg titling contract for Shorts

## Canonical style

Use `scripts/brand_title_style.py` for every title-capable renderer. Do not duplicate font paths, size, weight, spacing, box opacity, border, or style version in project scripts.

At 1080 px width the current style is `sergey-vertical-title-v2`; the helper scales it for other widths. Reports must record the style version, resolved font path, and font SHA-256. Fail explicitly if the exact font is unavailable.

## Safe geometry

Use `scripts/youtube_safe_title.py` as the only source of title placement. The complete title box must end exactly at `h*0.72`, remain left of the configured controls strip, and include `boxborderw` in the calculation.

Do not copy a raw `x=` or `y=` formula into project scripts. Generate the filter arguments from the shared helpers so policy changes propagate to every renderer.

## Textfile input

FFmpeg `drawtext` treats colons and other characters in inline `text=` as filter syntax. Write the complete approved multiline title to a UTF-8 text file and use `textfile=`. Keep one title block in one `drawtext` filter.

Example input file:

```text
6:00 AM
Подарок получен
Спать отменяется
```

## Existing-video overlay

For a titled video revision:

1. obtain style values from `brand_title_style.py`;
2. obtain safe geometry from `youtube_safe_title.py`;
3. use a UTF-8 `textfile=` and the approved enable interval;
4. encode video once to H.264/yuv420p and copy the already approved audio stream;
5. write a versioned output rather than overwriting the input;
6. fully decode the output and inspect representative titled frames.

## Shell safety

Complex filter graphs with nested quotes are error-prone in inline shell commands. Generate a versioned script under the project workdir or invoke a reusable skill entrypoint. Never keep a second project-local implementation after the reusable skill path exists.
