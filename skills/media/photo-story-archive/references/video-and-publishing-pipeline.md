# Video and cross-platform publishing pipeline

Use this reference when an archive includes videos or the user wants one source set turned into Instagram and YouTube deliverables.

## Archive each video

1. Copy the original without transcoding into `videos/` using `YYYY-MM-DD_HH-MM-short-scene-name.ext`.
2. Compare source and destination SHA-256.
3. Inspect with `ffprobe`: duration, dimensions, orientation, codecs, frame rate, audio streams, creation time, size and bitrate.
4. For visual review, extract representative frames or a contact sheet with FFmpeg. Keep previews separate from originals.
5. Record whether time came from embedded metadata or chat receipt time.
6. Append it to the same chronological story as photos. Give it both a video sequence number and a global material number.
7. Record its editing role: hook, greeting, establishing shot, transition, detail, voiceover bed or closing shot.

Example probes:

```bash
ffprobe -v error \
  -show_entries format=duration,size,bit_rate:format_tags=creation_time:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels \
  -of json input.mp4

ffmpeg -y -v error -i input.mp4 \
  -vf "fps=1/3,scale=360:-1,tile=3x1" -frames:v 1 preview.jpg
```

Choose the sampling interval and tile size from actual duration; a fixed three-frame tile can leave black cells for very short clips.

## Produce once, adapt twice

Create a shared vertical master, normally 9:16 H.264/AAC, then export platform-specific copies only after checking the platforms' current requirements.

The draft package should contain:

```text
project/
├── story.md
├── photos/                 # untouched originals
├── videos/                 # untouched originals
├── previews/
├── exports/
│   ├── instagram-carousel/
│   ├── instagram-reel.mp4
│   ├── youtube-short.mp4
│   └── cover.jpg
└── publish-manifest.md
```

`publish-manifest.md` must show:

- exact media and order;
- Instagram caption, location and alt text where supported;
- YouTube title, description, visibility and audience / made-for-kids choice;
- hashtags;
- music/audio provenance;
- final file checksums;
- status: `draft`, `approved`, `publishing`, `published` or `failed`;
- returned post/video IDs and URLs only after successful publication.

## Two-phase approval gate

Treat ordinary instructions such as “собери”, “подготовь” or “покажи черновик” as draft-only. Do not publish.

Before accepting “публикуй” as authorization, show the final manifest and verify all of these:

- target accounts/channels;
- exact media order and crop;
- caption/title/description;
- location and audience/visibility;
- audio rights;
- whether to publish now or schedule.

The publication command authorizes only the displayed manifest revision. Any material edit after approval resets status to `draft` and requires fresh approval.

## Official publishing paths

Prefer official APIs over password/cookie/browser automation.

### Instagram

Meta's Content Publishing API supports content publishing for eligible Instagram professional accounts. Media must be reachable by Meta during publishing, or uploaded through a supported resumable path. Required account type, permissions, Page relationship and endpoints change over time; verify the current Meta documentation before setup. Never store access tokens in SKILL.md, story files or publish manifests.

### YouTube

Use YouTube Data API `videos.insert` with OAuth for uploads. A Short is uploaded as a normal video; classification depends on current YouTube rules and media characteristics. Verify current duration/aspect requirements before rendering. Store OAuth material only in the platform's secret store or credential path, never in project content.

If API access is absent, stop at a complete upload-ready package. Do not claim publication.

## Music and identity safety

- Use original audio, user-owned/licensed tracks, royalty-free assets with recorded provenance, or leave music insertion to the platform library.
- Never infer a person's identity from an image.
- Do not promote a visual resemblance into a factual brand/building identification. Preserve it as the user's joke unless corroborated by a reliable source.

## Verification

- Originals preserved and checksum-matched.
- Final files play from start to finish and have expected video/audio streams.
- No accidental black frames, clipped text, stretched images or missing audio.
- Metadata text matches rendered media.
- Publication occurs only for the currently approved manifest revision.
- A successful API response is verified by returned ID/URL; partial platform success is reported per platform.