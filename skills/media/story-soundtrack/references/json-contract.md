# JSON contract — story-soundtrack

`schema_version: 1`. Неизвестные поля на любом уровне → отклонение.

## Top-level

| Поле | Тип | Правила |
|------|-----|---------|
| `story_id` | string | идентификатор истории |
| `revision` | int ≥ 1 | версия spec |
| `state` | enum | **только** `PLANNED` (transitions в report/approval/handoff) |
| `timeline` | object | путь, fps, total_frames, sample_rate_hz=48000 |
| `style` | object | preset `procedural_pentatonic_v1`, bpm, seed, … |
| `dramaturgy` | object | `climax_scene_id` ∈ scenes |
| `themes` | array | уникальные id, energy 0..1 |
| `scenes` | array | непрерывное покрытие [0, total_frames) |
| `outputs` | object | 10 уникальных путей с token `v{revision}` |
| `qa` | object | LUFS range, true peak, transition_ms, `encoded_lufs_tolerance_db`, `encoded_true_peak_tolerance_db` |

## Source media duration policy

- Source **короче** сцены: только explicit tail silence padding; report `decoded_source_frames`, `padded_tail_frames`.
- Source **длиннее** сцены: FAIL (trim только codec padding ≤1024 samples, report `trimmed_codec_padding_frames`).
- Без `-shortest`.

## Scene

| `audio_class` | `source_audio` | default routing |
|---------------|----------------|-----------------|
| `silent` | forbidden (null) | rhythm 1, melody 1 |
| `voice` | required | source 1, rhythm 0.456, melody 0 |
| `source_music` | required | source 1, stems 0 |

`frames`: `[start, end)` полуинтервал, плотное покрытие без дыр.

## Timeline file

```json
{
  "schema_version": 1,
  "story_id": "...",
  "fps": 30,
  "total_frames": 300,
  "scenes": [{"id": "...", "frames": [0, 150]}]
}
```

Должен совпадать со spec по story_id, fps, total_frames, порядку и frames сцен.

## Exact frames

`exact_pcm_frames = total_frames * 48000 / fps` — обязано быть целым.

## Outputs (все relative под `--root`)

- `rhythm_wav`, `melody_wav`, `full_score_wav` — PCM16 stereo 48 kHz
- `source_mixed_wav` — финальный PCM master
- `rhythm_preview_m4a`, `full_preview_m4a`, `source_mixed_approval_m4a` — AAC review
- `report_json`, `approval_json`, `handoff_json`

Пути уникальны; output ≠ input. Без `--overwrite` существующие outputs не перезаписываются; первый `mix` после `render` потребляет STEMS `report_json` без `--overwrite`; повторный mix / `source_mixed_*` — с `--overwrite`. approval/handoff предпочтительно never overwrite.

## Approval M4A QA (source_mix report `qa`)

- `raw_decoded_frames`: полный raw decode AAC без apad/atrim
- `codec_tail_padding_frames`: excess над expected PCM (0..1024 допустимо)
- ffprobe duration tolerance — дополнительная проверка, не замена frame count

## Report fields

implementation SHA-256, input/output hashes, exact PCM frames, Python/NumPy/FFmpeg versions, routing, state.
