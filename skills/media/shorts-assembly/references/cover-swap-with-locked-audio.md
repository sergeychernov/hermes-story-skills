# Frame-exact cover swap with locked audio

Use when an existing mixed master has the correct scene timing and approved audio, but its opening cover must change without recomposing or remixing the soundtrack.

For Sergey's YouTube Shorts publication masters, reject every interval except exactly four frames rendered from the same approved, central-crop-safe cover image at 30 fps. Frames `0..3` are the cover and frame `4` is live footage. A longer visible intro is a separate edit and cannot carry the publication report contract. Verify visual equivalence after lossy encode rather than requiring byte-identical decoded frames.

## Source of truth

Probe the actual master before editing. Do not trust a stale manifest when it disagrees with the encoded file or the locked soundtrack duration.

Record:

- exact CFR and decoded video-frame count;
- actual opening-cover frame range;
- dimensions and pixel format;
- audio codec, sample rate, channels, start and duration;
- source video and cover hashes.

When the approved soundtrack is bound to the existing master timeline, preserve the master's cover-frame count. Replacing a 90-frame cover with a 30-frame cover would shift every scene and invalidate the locked audio even if a stale manifest says one second.

## Video-only replacement

For a 30 fps master with an `N`-frame cover:

1. Generate the new still cover as exactly `N` frames, with no black lead-in or fade unless explicitly approved.
2. Trim the old video from `start_frame=N`.
3. Concatenate only the replacement cover and retained video tail.
4. Map the original audio stream and use `-c:a copy`. Do not denoise, normalize, trim, regenerate, remix, or re-encode it.
5. Write a new versioned MP4; never overwrite the approved/source master.

Core filter pattern:

```text
[new] fps=30,trim=end_frame=N,setpts=PTS-STARTPTS [cover]
[old] trim=start_frame=N,setpts=PTS-STARTPTS,fps=30 [tail]
[cover][tail] concat=n=2:v=1:a=0,settb=1/30,setpts=N [video]
```

At output, explicitly set:

```text
-r 30 -fps_mode cfr -video_track_timescale 90000
```

This matters because a looped still input can otherwise make the encoder inherit 25 fps, drop frames, or emit a fractional `avg_frame_rate` despite apparently correct filter expressions.

## Mandatory verification

Reject the output unless all checks pass:

- decoded output frame count equals decoded source frame count;
- `r_frame_rate` and `avg_frame_rate` are both `30/1`;
- dimensions, SAR, start time and expected total duration are unchanged;
- full video and audio decode succeed;
- copied AAC packet-payload SHA-256 is identical before and after mux;
- frame `0` is the new cover with no black/gray lead-in;
- frame `N-1` is still the complete cover with no fade;
- frame `N` is the same first post-cover scene as source frame `N`;
- representative middle and final frames are intact;
- retained-tail SSIM against the source is high enough to detect alignment mistakes (a normal H.264 re-encode may prevent byte/pixel identity).

A matching container duration alone is insufficient. AAC padding can obscure truncation, and timestamp seeking is not frame-authoritative near the cut.

## Manifest reconciliation

After successful replacement, reconcile the canonical story manifest and generated timeline to the actual audio-bound frame contract. Record:

- replacement cover image and scene hashes;
- cover frame range and duration;
- output video hash;
- unchanged audio packet hash;
- scene frame contract;
- boundary QA evidence;
- `video-review-pending` independently from cover approval and publication approval.

Do not claim that cover approval approves the rebuilt full video.