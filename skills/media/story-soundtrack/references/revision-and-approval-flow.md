# Revision and approval flow

## Revision loop

1. Пользователь слушает `source_mixed_approval_m4a` (или stems previews на ранних фазах).
2. Заполнить `story-soundtrack-feedback.json`:
   - `from_revision` = текущая revision spec
   - `requested_revision` = from + 1
   - `user_feedback` — дословный текст пользователя
   - `requested_changes[]` — target + machine-readable change
3. **Скопировать** предыдущий spec → новый файл `v{N+1}.json`; применить только запрошенные поля. Token `vN` в paths заменяется **только** exact revision match (не трогает unrelated `v10` text).
4. `state` остаётся `PLANNED`; output paths → новый `v{N+1}`.
5. `apply_feedback_revision.py` требует `--root`; output spec и `.feedback.json` confined under root.

### Change targets

| target | change payload |
|--------|----------------|
| `style` | partial style object |
| `theme` | `{id, energy?, ...}` |
| `rhythm` | `{rhythm_gain}` (all scenes) |
| `melody` | `{melody_gain}` |
| `routing` | `{scene_id, source_gain?, rhythm_gain?, melody_gain?}` |
| `source_mix` | `{scene_id, source_gain}` — scene_id обязателен, no-op отклоняется |
| `loudness` | partial qa object |

## Approval

Только после явного «OK» пользователя на `source_mixed_approval_m4a`:

```bash
approve_story_soundtrack.py --root <work> --spec <spec> --approval-note "цитата"
```

Создаёт:
- `approval_json` — hash-bound M4A, spec, timeline, report, source_mixed_wav
- `handoff_json` — для `shorts-assembly`

`state` → `USER_APPROVED` / `HANDED_OFF_TO_SHORTS`.

## Invalidation

Изменение composition, routing, gain, timeline или пересборка mix после approval меняет hashes → `verify --require-approved-handoff` fail. Нужна новая revision.

## Shorts handoff

Handoff разрешает только:
- `video_concat`, `video_encode`, `audio_stream_copy_or_exact_mux`, `container_faststart`

Запрещено: loudnorm, denoise, ducking, stem remix, trim меняющий duration.

`audio_processing_locked: true` обязателен.
