"""
Oliver June 2024
"""
from __future__ import annotations

import re
import string
from typing import List, Dict, Any

__all__ = ["get_tags", "Mp3Tag"]

DEFAULT_ENCODING = 'ISO-8859-1'  # standard mp3 text encoding
JPEG_SOI_MARKER = b'\xFF\xD8'  # start of image marker for jpeg files
JPEG_EOI_MARKER = b'\xFF\xD9'  # end of image
ID3v2_HEADER_LENGTH = 10
IDENTIFIER_LEN = 3
TAG_SIZE_START_IDX = 6
TAG_OFFSET = 10
INT_KEYS = ('track_number', 'disc_number', 'year')
ARTIST_KEYS = ("composer", "artist1", "artist2")
NULL = '\x00'

FRAME_IDS = [b'TIT2', b'TALB', b'TPUB', b'TCON', b'TYER', b'TRCK',
             b'TOPS', b'TPE1', b'TPE2', b'TCOM', b'APIC', b'COMM', b'WXXX']
FRAME_ENCODING = {
    0: 'ISO-8859-1', 1: 'UTF-16', 2: 'UTF-16BE', 3: 'UTF-8'
}
METADATA_MAP = {
    b'TIT2': 'title', b'TALB': 'album', b'TPUB': 'publisher', b'TCON': 'genre',
    b'TYER': 'year', b'TRCK': 'track_number', b'TOPS': 'disc_number', b'TPE1': 'artist1',
    b'TPE2': 'artist2', b'TCOM': 'composer', b'APIC': 'artwork', b'COMM': 'comments', b'WXXX': 'url'
}


class Mp3Tag:
    """
    object
    """
    album: str
    artists: List[str]  # comprised of composer, artist1 and artist2 from mp3 tag
    artwork: bytes
    comments: str
    genre: str
    publisher: str
    title: str
    track_number: int
    disc_number: int
    url: str
    year: int


def decode_synchsafe(x: int | bytes) -> int:
    """
    decode bytes/int from synchronization safe format to integer
    https://phoxis.org/2010/05/08/synch-safe/
    :param x: synchsafe value
    :return: integer
    """
    if isinstance(x, bytes):
        x = int.from_bytes(x)

    if x & 0x808080:
        # ignore MSB
        x &= 0x7f7f7f7f

    ans = 0
    a = x & 0xff
    b = (x >> 8) & 0xff
    c = (x >> 16) & 0xff
    d = (x >> 24) & 0xff

    ans |= a
    ans |= b << 7
    ans |= c << 14
    ans |= d << 21

    return ans


def extract_text(data: bytes) -> str:
    """
    builds a string out of printable characters from bytes
    :param data: byte data
    :return: string
    """
    x = data.decode(DEFAULT_ENCODING)
    res = []
    for c in x:
        if c in string.printable:
            res.append(c)
    return ''.join(res)


def extract_image_data(data: bytes, tag: bytes) -> bytes | None:
    """
       extract image byte data from mp3 file frame
       https://docs.fileformat.com/image/jpeg/
       :param data: frame data
       :param tag: mp3 tag
       :return: image bytes
       """
    if data[1:11] != b'image/jpeg':  # check mime type is JPEG
        return None
    # get first instance of jpeg image start
    img_start = tag.find(JPEG_SOI_MARKER)
    # get last instance of jpeg image end marker incase of EXIF
    img_end = tag.rfind(JPEG_EOI_MARKER)

    img_data = tag[img_start:img_end + 2]
    return img_data


def get_frame_data(tag: bytes, frame_id: bytes):
    """
    get frame tag content
    :param tag: the tag bytes
    :param frame_id: the frame identifier
    :return: content
    """
    start_idx = tag.find(frame_id)
    if start_idx == -1:
        return None
    offset = start_idx + TAG_OFFSET
    header = tag[start_idx:offset]
    size = decode_synchsafe(header[4:8])
    data = tag[offset:offset + size]
    # extract desired content from bytes data
    if frame_id == b'APIC':
        content = extract_image_data(data, tag)
    else:
        content = extract_text(data)

    return content


def format_tags(frames: Dict[bytes, Any]) -> Mp3Tag:
    """
    tag frames collected in dictionary and
    create Mp3Tag object for code completion and type checking
    :param frames: dictionary of frame names and data
    :return:
    """
    tag = Mp3Tag()
    artists = set()
    for k, v in frames.items():
        key = METADATA_MAP[k]
        if key in ARTIST_KEYS and v is not None:
            artists.add(v)
            continue
        if key in INT_KEYS and v is not None:
            v = v.split('/')[0] if key == "track_number" else int(v)

        tag.__setattr__(key, v)

    tag.artists = list(artists)
    return tag


def get_tags(filename: str) -> Mp3Tag | None:
    """
    :param filename: mp3 filename
    :return: Mp3Tags object of mp3 file tag attributes
    """
    # read data
    file = open(filename, "rb")
    # check if ID3v2 file (first 3 bytes should be ID3)
    if file.read(3) != b'ID3':
        return None
    file.seek(6)  # skip to metadata tag size
    # get the size of the tag
    size = decode_synchsafe(file.read(4))
    # get the mp3 tag
    tag = file.read(size)
    frames = dict()

    for frame_id in FRAME_IDS:
        # check for frame in tag
        frames[frame_id] = get_frame_data(tag, frame_id)

    file.close()

    return format_tags(frames)
