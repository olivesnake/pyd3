import os
import tempfile
import unittest

from pyd3.tags import decode_id3_text, get_tag


def build_frame(frame_id: str, data: bytes) -> bytes:
    return (
        frame_id.encode("ascii")
        + len(data).to_bytes(4, "big")
        + b"\x00\x00"
        + data
    )


def synchsafe(size: int) -> bytes:
    return bytes(
        [
            (size >> 21) & 0x7F,
            (size >> 14) & 0x7F,
            (size >> 7) & 0x7F,
            size & 0x7F,
        ]
    )


class TestTags(unittest.TestCase):
    def test_decode_id3_text_utf16be_and_utf8(self) -> None:
        self.assertEqual(decode_id3_text("Hi".encode("utf-16-be"), 2), "Hi")
        self.assertEqual(decode_id3_text("Hi".encode("utf-8"), 3), "Hi")

    def test_get_tag_parses_frames(self) -> None:
        title_frame = build_frame("TIT2", b"\x03" + "Song".encode("utf-8"))
        composer_frame = build_frame("TCOM", b"\x03" + "Composer".encode("utf-8"))
        artist_frame = build_frame("TPE1", b"\x03" + "Artist".encode("utf-8"))
        accompaniment_frame = build_frame("TPE2", b"\x03" + "Band".encode("utf-8"))

        comment_data = b"\x00" + b"eng" + b"desc" + b"\x00" + b"comment"
        comment_frame = build_frame("COMM", comment_data)

        image_bytes = b"\xff\xd8\xff"
        apic_data = (
            b"\x00"
            + b"image/jpeg"
            + b"\x00"
            + b"\x03"
            + b"cover"
            + b"\x00"
            + image_bytes
        )
        apic_frame = build_frame("APIC", apic_data)

        frames = (
            title_frame
            + composer_frame
            + artist_frame
            + accompaniment_frame
            + comment_frame
            + apic_frame
        )

        header = b"ID3" + bytes([3, 0]) + b"\x00" + synchsafe(len(frames))

        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(header + frames)
            path = handle.name

        try:
            tag = get_tag(path)
        finally:
            os.unlink(path)

        self.assertIsNotNone(tag)
        self.assertEqual(tag.title, "Song")
        self.assertEqual(tag.comments["text"], "comment")
        self.assertEqual(tag.artwork["bytes"], image_bytes)
        self.assertEqual(tag.artists, ["Composer", "Artist", "Band"])


if __name__ == "__main__":
    unittest.main()
