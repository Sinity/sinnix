import importlib.machinery
import importlib.util
import pathlib
import socket
import threading
import types
import unittest
from unittest import mock

SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "sinnix-quest-player"
SPEC = importlib.util.spec_from_loader(
    "quest_player", importlib.machinery.SourceFileLoader("quest_player", str(SCRIPT))
)
quest_player = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quest_player)


class QuestPlayerTest(unittest.TestCase):
    def test_clipboard_accepts_local_file_uri(self):
        with mock.patch.object(
            quest_player.subprocess,
            "check_output",
            return_value="file:///media/a%20b.mp4",
        ):
            self.assertEqual(quest_player.clipboard_path(), "/media/a b.mp4")

    def test_clipboard_rejects_remote_url(self):
        with mock.patch.object(
            quest_player.subprocess,
            "check_output",
            return_value="https://media.example/video.mp4",
        ):
            with self.assertRaises(ValueError):
                quest_player.clipboard_path()

    def test_media_key_controls_active_quest_session(self):
        args = types.SimpleNamespace(key="next")
        with (
            mock.patch.object(
                quest_player, "read_json", return_value={"status": "active"}
            ),
            mock.patch.object(quest_player, "control") as control,
        ):
            quest_player.media_key(args)
        self.assertEqual((args.action, args.value), ("seek", "+10"))
        control.assert_called_once_with(args)

    def test_media_key_uses_playerctl_without_active_session(self):
        args = types.SimpleNamespace(key="toggle")
        with (
            mock.patch.object(
                quest_player, "read_json", return_value={"status": "stopped"}
            ),
            mock.patch.object(quest_player.subprocess, "run") as run,
        ):
            quest_player.media_key(args)
        run.assert_called_once_with(["playerctl", "play-pause"], check=True)

    def test_fragmented_remote_protocol(self):
        left, right = socket.socketpair()
        with left, right:
            data = b'{"currentTime":12}'
            wire = quest_player.struct.pack("<I", len(data)) + data

            def send():
                for byte in wire:
                    left.sendall(bytes([byte]))

            thread = threading.Thread(target=send)
            thread.start()
            self.assertEqual(quest_player.receive(right), {"currentTime": 12})
            thread.join()

    def test_session_descriptor_never_contains_token_or_transport(self):
        class Arguments:
            stereo = "sbs"
            projection = "flat"
            codec = "h265"
            height = 2160
            cold = False

        descriptor = quest_player.session_descriptor(
            pathlib.Path("/media/movie.mp4"), Arguments()
        )
        self.assertEqual(descriptor["file"], "/media/movie.mp4")
        self.assertNotIn("token", descriptor)
        self.assertNotIn("transport", descriptor)


if __name__ == "__main__":
    unittest.main()
