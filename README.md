# Hermes Story Skills

A Hermes skill pack for creating short vertical videos from uploaded photos, video clips, narration, and music. It covers the complete user workflow: story planning, scene previews, animated stills and collages, covers, soundtrack approval, final assembly, review delivery, and explicit publication.

The pack is designed to be used through normal conversation with Hermes. You upload media, describe the result, and approve intermediate artifacts. You do not need to run the rendering scripts yourself.

## Install in Hermes

### Recommended: ask Hermes to install it

Send this message to Hermes in a local session with terminal access:

> Install all media skills from `https://github.com/sergeychernov/hermes-story-skills`. Clone the repository for the active Hermes profile, add its `skills/media` directory to `skills.external_dirs` without removing any existing external skill directories, verify that every skill listed in the repository README is discoverable, and tell me when I should start a new session.

Hermes should preserve the repository as one dependency graph instead of copying individual `SKILL.md` files. The skills call and reference one another, so installing only `story` or only `shorts-assembly` is incomplete.

Start a new Hermes session after installation so the skill catalog is refreshed.

### Manual installation

If you prefer the terminal, clone the repository somewhere persistent and point Hermes at its `skills/media` directory:

```bash
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
mkdir -p "$HERMES_HOME/external"
git clone https://github.com/sergeychernov/hermes-story-skills.git \
  "$HERMES_HOME/external/hermes-story-skills"
```

Add this absolute directory to the active profile's `skills.external_dirs` setting:

```text
$HERMES_HOME/external/hermes-story-skills/skills/media
```

If this is your first external skill directory, configure it with:

```bash
SKILLS_DIR="$(cd "$HERMES_HOME/external/hermes-story-skills/skills/media" && pwd)"
hermes config set skills.external_dirs "[\"$SKILLS_DIR\"]"
```

If `skills.external_dirs` already contains other directories, do not run the command above because it would replace the list. Use the recommended chat request and ask Hermes to append this directory without removing existing entries. Then start a new session.

### Verify the installation

Ask Hermes:

> List the installed story/media skills and verify that the complete Hermes Story Skills dependency graph is available.

The expected skills are:

- `story`
- `photo-story-archive`
- `still-image-animation`
- `animated-collage`
- `scene-group`
- `media-voiceover`
- `static-cover-collage`
- `story-soundtrack`
- `shorts-assembly`
- `social-publisher`

You can also invoke the orchestrator explicitly:

```text
/story Help me make a Short from the media I am about to upload.
```

### Update

Ask Hermes:

> Update the `hermes-story-skills` checkout with a fast-forward-only pull, keep my existing Hermes configuration, verify the installed skill graph, and tell me whether I need a new session.

Or update the checkout manually:

```bash
git -C "${HERMES_HOME:-$HOME/.hermes}/external/hermes-story-skills" pull --ff-only
```

Start a new session after an update so changed skill instructions are loaded cleanly.

### Remove

Ask Hermes:

> Remove the Hermes Story Skills external directory from the active profile without changing my other external skill directories, then remove its checkout.

Start a new session after removal.

## Quick how-to: make a Short in chat

### 1. Upload the source media

Send original video clips and photos in the best available quality. If order matters, send files in that order or label them `1`, `2`, `3`.

You may also upload:

- your own music;
- recorded narration;
- a logo;
- a preferred cover image;
- a reference video or image for mood and composition.

Do not pre-compress the media just for Hermes unless the messaging platform requires it. Originals should remain unchanged; all edits are made as derived artifacts.

### 2. Describe the result in one message

Include:

- the story in one sentence;
- target platform;
- maximum duration;
- source order;
- language and tone;
- speech, sounds, camera movement, or framing that must be preserved;
- whether music is uploaded, generated, or unwanted;
- any title or cover idea;
- whether the result is for review only or may later be published.

Example:

> Make a YouTube Short under 60 seconds. Use the files in upload order. Keep the original speech and camera pans. Animate the two photos as one collage. Propose short Russian titles and a YouTube cover. Use subtle generated music under the speech. First show me the scene plan and titles; do not publish.

### 3. Approve the story plan

Before rendering, Hermes should propose:

- scene order and approximate durations;
- treatment of every photo and video;
- title text and placement;
- which source audio is preserved;
- music or voiceover treatment;
- required platform covers;
- expected total duration.

Correct the plan now. A plan approval is not approval of rendered scenes, audio, final video, or publication.

### 4. Approve scene previews

Review every scene as an MP4. Ask for changes to crop, movement, title, duration, voiceover, or source audio before the full timeline is assembled.

A contact sheet or isolated frame is supporting QA, not approval of the moving scene.

### 5. Approve covers separately

Request only the platforms you need. These are different artifacts:

- YouTube API thumbnail;
- Instagram cover;
- Telegram first frame.

Approving one does not approve the others and does not approve changes to the video itself.

### 6. Choose and approve the audio

You can ask Hermes to:

- keep only original clip audio;
- use uploaded music under original speech and sounds;
- generate background music from a mood, tempo, and instrument brief;
- add uploaded narration or approved TTS voiceover;
- preserve, lower, boost, or replace source audio for selected scenes;
- create a denoised derivative while preserving the original unchanged.

Approve the standalone audio mix or soundtrack revision before final video assembly. Request gain, music, source-audio, and denoise changes at this stage—not after the final mux.

### 7. Approve the final master

After scenes, covers, and audio are approved, tell Hermes which approved cover belongs in the timeline and request final assembly.

Watch the delivered master from beginning to end. Chat delivery is still review delivery, not permission to publish.

### 8. Approve publication explicitly

Name all of the following in the publication request:

- platform;
- account or channel;
- audience/privacy;
- exact approved master and cover;
- title, caption, tags, and playlist when applicable.

Hermes should summarize the exact package and ask for explicit publication approval before an external write.

## Compact first-message template

> Build a 9:16 Short for `<platform>`, up to `<duration>`. The files are in `<order>`. The story is `<one sentence>`. Keep `<speech/sounds/movements/framing>`. Use `<uploaded/generated/no>` music. Put `<title idea>` on `<scenes/cover>`. First show me the scene plan and titles; do not publish.

## Concrete user recipes

| What you want | What to upload | What to write in chat | Approval sequence |
|---|---|---|---|
| Short from existing video clips | Original clips | “Use upload order; keep original speech; propose cuts and titles; target `<platform/duration>`.” | Plan → scene previews → cover → audio → final master |
| One photo as a narrative scene | One original photo | “Turn this into a `<duration>` scene; use a gentle `<pan/zoom>` focused on `<subject>`; title: `<text>`.” | Motion preview → title/safe-zone preview → scene |
| Animated collage from 2–6 photos | Original photos, preferably labeled | “Make these photos one collage scene; emphasize `<hero photo>`; title `<text>`; avoid cropping `<people/object>`.” | Layout still → animated MP4 → scene |
| Photo cards over a video | Base video plus card photos | “Keep the base video moving; show these photos as cards at `<moments>`; do not cover `<subject/title area>`.” | Timing/layout preview → scene |
| Several scenes as one editorial beat | Approved scene previews | “Group scenes `<IDs>` in this order as one beat; preserve their audio and do not add new mixing.” | Group preview → grouped scene |
| Add narration or voiceover | Target scene/group plus narration, or approved TTS text | “Add this voiceover to `<scene>`; `<preserve/lower/remove>` source audio; review the mix separately.” | Voiceover mix → revised scene |
| Keep original sound and add uploaded music | Original clips plus music file | “Keep speech audible in scenes `<IDs>`; use this music underneath; lower or mute it at `<moments>`.” | Audio-routing plan → mixed-audio preview → final mux |
| Generate background music | Approved visual timeline | “Generate `<mood/tempo/instruments>` music for the frozen timeline; avoid vocals; preserve `<named source sounds>`.” | Music revision → source/music mix → approved audio |
| Clean noisy speech | Original clip | “Create a denoised derivative, preserve the original unchanged, keep natural pauses, and send the audio mix for approval before video.” | Original/cleaned comparison → derivative scene |
| Platform cover | Candidate photos and final title/subtitle | “Create a cover for `<YouTube API/Instagram/Telegram>` using `<photo>`; title `<text>`; keep `<subject>` unobstructed.” | Platform-specific still → cover approval |
| Replace only the cover | Approved final video plus newly approved cover | “Replace only the `<platform>` cover/first-frame segment; keep the approved timeline audio locked.” | Boundary preview → final verification |
| Telegram review copy | Approved master | “Send a Telegram review copy; keep the canonical master unchanged.” | Review delivery only; no publication approval |
| Publish the finished package | Approved master, covers, and metadata | “Publish this exact package to `<platform/account>` for `<audience>` with `<title/caption/tags>`.” | Package summary → explicit publish approval → verified link/record |

## Why the workflow uses this order

The workflow is a dependency graph. Each stage consumes an approved handoff from the previous stage.

1. **Plan before rendering** so scene order, duration, titles, covers, and platform constraints are explicit.
2. **Preserve originals and normalize video once** to avoid repeated lossy processing and timestamp drift.
3. **Approve scenes independently** because crop, motion, titles, and scene audio are cheaper and clearer to correct before assembly.
4. **Approve covers separately** because every platform has a different cover contract.
5. **Freeze the visual timeline before soundtrack** because music duration, transitions, and source-audio windows depend on exact visual timing.
6. **Approve audio before final mux** so assembly cannot silently change the mix the user heard.
7. **Verify the final master before delivery** because successful encoding does not prove correct scene order, complete narration, or correct cover revision.
8. **Publish last and only with explicit approval** because platform writes are externally visible and may not be safely repeatable.

## What changes invalidate approval

- Changing a source, crop, title, scene duration, scene order, cover pixels, or cover frame count invalidates the visual timeline and soundtrack/final-master approvals bound to it.
- Changing music, source-audio routing, voiceover, denoise, or gain invalidates the audio approval and final master, but not approved visual scenes.
- Changing only a Telegram review copy does not invalidate the canonical master.
- Approving a scene, cover, soundtrack, final master, chat delivery, and publication are separate decisions.
