import importlib.machinery
import importlib.util
import pathlib
import socket
import threading
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "sinnix-quest-player"
SPEC = importlib.util.spec_from_loader("quest_player", importlib.machinery.SourceFileLoader("quest_player", str(SCRIPT)))
quest_player = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quest_player)


class QuestPlayerTest(unittest.TestCase):
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

        descriptor = quest_player.session_descriptor(pathlib.Path("/media/movie.mp4"), Arguments())
        self.assertEqual(descriptor["file"], "/media/movie.mp4")
        self.assertNotIn("token", descriptor)
        self.assertNotIn("transport", descriptor)


if __name__ == "__main__":
    unittest.main()
