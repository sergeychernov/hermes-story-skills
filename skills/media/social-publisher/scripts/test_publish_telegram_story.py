#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


class StoryMediaAttributesTests(unittest.TestCase):
    def test_audience_maps_to_story_privacy(self):
        from publish_telegram_story import privacy_rules_for_audience

        self.assertEqual(type(privacy_rules_for_audience('contacts')[0]).__name__, 'InputPrivacyValueAllowContacts')
        self.assertEqual(type(privacy_rules_for_audience('everyone')[0]).__name__, 'InputPrivacyValueAllowAll')
        self.assertIsNone(privacy_rules_for_audience('link'))
        with self.assertRaisesRegex(ValueError, 'Unsupported audience'):
            privacy_rules_for_audience('unknown')

    def test_channel_audience_is_public_only(self):
        from publish_telegram_story import validate_target_audience

        validate_target_audience('self', 'contacts')
        validate_target_audience('self', 'everyone')
        validate_target_audience('self', 'link')
        validate_target_audience('travel', 'everyone')
        with self.assertRaisesRegex(ValueError, 'require --audience everyone'):
            validate_target_audience('travel', 'contacts')
        with self.assertRaisesRegex(ValueError, 'require --audience everyone'):
            validate_target_audience('travel', 'link')

    def test_video_has_filename_and_video_metadata(self):
        from publish_telegram_story import video_attributes

        attrs = video_attributes(50.033, 720, 1280, 'telegram-story.mp4')
        self.assertEqual([type(a).__name__ for a in attrs], [
            'DocumentAttributeFilename',
            'DocumentAttributeVideo',
        ])
        self.assertEqual(attrs[0].file_name, 'telegram-story.mp4')
        self.assertEqual(attrs[1].duration, 50)
        self.assertIsNone(attrs[1].video_codec)
        self.assertTrue(attrs[1].supports_streaming)


if __name__ == '__main__':
    unittest.main()
