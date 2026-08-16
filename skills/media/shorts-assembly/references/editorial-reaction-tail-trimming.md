# Editorial tail trimming after a reaction or reveal

Use this when a clip has a meaningful subject/reaction in the middle, then the camera returns to the original scene and lingers too long.

## Evidence pass

Create a timestamped contact sheet at about 2 fps. Mark:

1. when the camera starts leaving the original scene;
2. when the reaction/person is fully visible;
3. when the camera leaves that subject;
4. the first frame where the original scene is clearly re-established;
5. the point where later footage becomes repetitive or a foreground bystander dominates.

A single last-frame check is insufficient: inspect the final 0.5–1.0 seconds as a short strip because motion can make an individually acceptable frame feel like an abrupt or weak ending.

## Cut rule

Keep a brief return beat after the reaction so the viewer understands where the camera came back to. End before the return turns into repetitive lingering. Prefer an explicit source range over vague commands such as “trim a little.” Record the range in the render report.

Example pattern:

```text
0.0–4.4  establishing action
4.4–6.0  reaction/person
6.0–8.2  short return and resolution
8.2+      repetitive tail removed
```

The numbers are illustrative, not defaults.

## Rendering invariant

Rebuild from the untouched original in one scripted render. Pass an explicit end time to the reusable title/render script; do not trim a previously titled MP4. Preserve AAC with stream copy when no audio processing was requested.

Report and verify:

- exact original-source range;
- output duration and SHA-256;
- dimensions/frame rate;
- decodable audio stream and whether it was copied without processing;
- middle, post-reaction, and late QA frames.
