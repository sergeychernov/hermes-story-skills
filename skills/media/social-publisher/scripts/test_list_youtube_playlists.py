import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))


class YouTubePlaylistListingTests(unittest.TestCase):
    def test_fetches_live_owned_playlists_for_selected_registered_channel(self):
        import list_youtube_playlists

        credentials = {
            "YOUTUBE_CLIENT_ID": "client",
            "YOUTUBE_CLIENT_SECRET": "secret",
            "YOUTUBE_REFRESH_TOKEN": "refresh",
        }
        token_response = io.StringIO('{"access_token":"sensitive-token"}')
        with mock.patch.object(
            list_youtube_playlists,
            "credentials_for_channel",
            return_value=({"channel_id": "UC1"}, credentials),
        ), mock.patch.object(
            list_youtube_playlists, "req", return_value=token_response
        ), mock.patch.object(
            list_youtube_playlists,
            "verify_authorized_channel",
            return_value={"id": "UC1", "title": "Channel"},
        ) as verify, mock.patch.object(
            list_youtube_playlists,
            "list_owned_playlists",
            return_value=[
                {"id": "PL2", "snippet": {"title": "Zoo"}},
                {"id": "PL1", "snippet": {"title": "alpha"}},
            ],
        ) as listing:
            result = list_youtube_playlists.fetch_owned_playlists("current")

        verify.assert_called_once_with("sensitive-token", "UC1")
        listing.assert_called_once_with("sensitive-token")
        self.assertEqual(
            result["playlists"],
            [{"id": "PL1", "title": "alpha"}, {"id": "PL2", "title": "Zoo"}],
        )
        self.assertNotIn("sensitive-token", repr(result))
        self.assertTrue(result["read_only"])

    def test_rejects_playlist_without_exact_id_or_title(self):
        import list_youtube_playlists

        with mock.patch.object(
            list_youtube_playlists,
            "credentials_for_channel",
            return_value=(
                {"channel_id": "UC1"},
                {
                    "YOUTUBE_CLIENT_ID": "client",
                    "YOUTUBE_CLIENT_SECRET": "secret",
                    "YOUTUBE_REFRESH_TOKEN": "refresh",
                },
            ),
        ), mock.patch.object(
            list_youtube_playlists,
            "req",
            return_value=io.StringIO('{"access_token":"token"}'),
        ), mock.patch.object(
            list_youtube_playlists,
            "verify_authorized_channel",
            return_value={"id": "UC1", "title": "Channel"},
        ), mock.patch.object(
            list_youtube_playlists,
            "list_owned_playlists",
            return_value=[{"id": "PL1", "snippet": {}}],
        ):
            with self.assertRaisesRegex(ValueError, "without ID or title"):
                list_youtube_playlists.fetch_owned_playlists("current")


if __name__ == "__main__":
    unittest.main()
