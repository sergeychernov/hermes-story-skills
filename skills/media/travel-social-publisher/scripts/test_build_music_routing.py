import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name('build_music_routing.py')
spec = importlib.util.spec_from_file_location('build_music_routing', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class MusicRoutingTests(unittest.TestCase):
    def test_still_gets_melody_and_rhythm_normal_video_only_rhythm_music_video_neither(self):
        manifest = {'clips': [
            {'type': 'image', 'duration': 3},
            {'type': 'video', 'duration': 4},
            {'type': 'video', 'duration': 5, 'content_type': 'music'},
        ]}
        routing = mod.build_routing(manifest)
        self.assertEqual(routing['melody_intervals'], [[0.0, 3.0]])
        self.assertEqual(routing['rhythm_intervals'], [[0.0, 7.0]])
        self.assertEqual(routing['muted_intervals'], [[7.0, 12.0]])
        self.assertEqual(routing['scene_modes'], ['melody+rhythm', 'rhythm', 'original-only'])

    def test_nosound_video_keeps_melody_and_rhythm(self):
        manifest = {'clips': [
            {'type': 'video', 'duration': 3, 'content_type': 'speech'},
            {'type': 'video', 'duration': 2, 'content_type': 'nosound'},
            {'type': 'video', 'duration': 4, 'content_type': 'music'},
        ]}
        routing = mod.build_routing(manifest)
        self.assertEqual(routing['melody_intervals'], [[3.0, 5.0]])
        self.assertEqual(routing['rhythm_intervals'], [[0.0, 5.0]])
        self.assertEqual(routing['muted_intervals'], [[5.0, 9.0]])
        self.assertEqual(routing['scene_modes'], ['rhythm', 'melody+rhythm', 'original-only'])

    def test_adjacent_music_scenes_are_merged(self):
        manifest = {'clips': [
            {'type': 'video', 'duration': 2, 'content_type': 'music'},
            {'type': 'video', 'duration': 3, 'content_type': 'music'},
        ]}
        routing = mod.build_routing(manifest)
        self.assertEqual(routing['muted_intervals'], [[0.0, 5.0]])
        self.assertEqual(routing['melody_intervals'], [])
        self.assertEqual(routing['rhythm_intervals'], [])

    def test_music_content_type_requires_video(self):
        with self.assertRaisesRegex(ValueError, 'content_type=music requires type=video'):
            mod.build_routing({'clips': [{'type': 'image', 'duration': 3, 'content_type': 'music'}]})

    def test_filter_mutes_both_generated_stems_during_music_video(self):
        manifest = {'clips': [
            {'type': 'image', 'duration': 2},
            {'type': 'video', 'duration': 2},
            {'type': 'video', 'duration': 2, 'content_type': 'music'},
        ]}
        routing = mod.build_routing(manifest)
        filt = mod.build_filter(routing, gain=0.13, fade=0.08)
        self.assertIn('[0:a]asetpts=N/SR/TB,atrim=duration=6.000000', filt)
        self.assertIn('[original][melody][rhythm]', filt)
        self.assertIn('[1:a]', filt)
        self.assertIn('[2:a]', filt)
        self.assertIn('amix=inputs=3:duration=first:normalize=0', filt)
        self.assertIn("volume='0.130000*", filt)
        self.assertNotIn('between(t,4.000000,6.000000)', filt)


if __name__ == '__main__':
    unittest.main()
