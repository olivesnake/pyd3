"""
Oliver June 2024
"""
import re
from typing import Dict, Any, List

__all__ = ["get_tag", "Mp3Tag"]
DEFAULT_ENCODING = 'ISO-8859-1'  # standard mp3 text encoding
HEADER_LENGTH = 10

INT_KEYS = ('track_number', 'disc_number', 'year')
ARTIST_KEYS = ("composer", "artist", "accompaniment")
NULL = '\x00'

FRAME_ENCODING = {
    0: 'ISO-8859-1', 1: 'utf-16le', 2: 'UTF-16BE', 3: 'UTF-8'
}

METADATA_MAP = {
    'TIT2': 'title', 'TALB': 'album', 'TPUB': 'publisher', 'TCON': 'genre',
    'TYER': 'year', 'TRCK': 'track_number', 'TPOS': 'disc_number', 'TPE1': 'artist',
    'TPE2': 'accompaniment',  'TCOM': 'composer', 'APIC': 'artwork', 'COMM': 'comments', 'WXXX': 'url'
}


class Mp3Tag:
    """
    object
    """
    album: str
    artist: str
    artists: List[str]
    accompaniment: str
    composer: str
    artwork: Dict[str, Any]
    comments: Dict[str, Any]
    genre: str
    publisher: str
    title: str
    track_number: str
    disc_number: str
    url: str
    year: str


def format_tags(frames: Dict[bytes, Any]) -> Mp3Tag:
    """
    tag frames collected in dictionary and
    create Mp3Tag object for code completion and type checking
    :param frames: dictionary of frame names and data
    :return:
    """
    tag = Mp3Tag()
    for k, v in frames.items():
        key = METADATA_MAP.get(k)
        if not key:
            continue
        tag.__setattr__(key, v)

    artists = []
    for key in ARTIST_KEYS:
        value = getattr(tag, key, None)
        if value:
            artists.append(value)
    tag.__setattr__("artists", artists)

    return tag


def decode_id3_text(text_bytes: bytes, encoding: int) -> str:
    """
    decode text bytes in id3v2 tag
    """
    if encoding == 0:  # iso
        text = text_bytes.decode(DEFAULT_ENCODING, errors="replace")
    elif encoding == 1:
        text = text_bytes.decode("utf-16", errors="replace")
    elif encoding == 2:
        text = text_bytes.decode("utf-16-be", errors="replace")
    elif encoding == 3:
        text = text_bytes.decode("utf-8", errors="replace")
    else:
        text = ""
    return text.replace('\x00', '')


def parse_text_frame(data: bytes) -> str:
    """
    parses text from a text information frame
    <Header for 'Text information frame', ID: "T000" - "TZZZ", excluding "TXXX" described in 4.2.2.>
Text encoding    $xx
Information    <text string according to encoding>
    """
    if not data:
        return ""
    encoding = data[0]
    # convert to bytes and remove null termination
    text_info = data[1:]
    return decode_id3_text(text_info, encoding)


def find_terminator(data: bytes, offset: int, encoding: int) -> int:
    """
    gets index of start of null terminator from bytes based on text encoding
    """
    length = len(data)
    if encoding in (0, 3):
        for i in range(offset, length):
            if data[i] == 0:
                return i
    else:
        for i in range(offset, length - 1, 2):
            if data[i] == 0 and data[i + 1] == 0:
                return i

    return -1


def parse_comment_frame(data: bytes) -> dict:
    """
    parses a comment frame
    <Header for 'Comment', ID: "COMM">
    Text encoding           $xx
    Language                $xx xx xx
    Short content descrip.  <text string according to encoding> $00 (00)
    The actual text         <full text string according to encoding>
    """
    if len(data) < 4:
        return {"language": "", "description": "", "text": ""}
    encoding = data[0]
    language = data[1:4].decode(DEFAULT_ENCODING, errors="replace")
    null_index = find_terminator(data, 4, encoding)
    terminator_length = 1 if encoding in (0, 3) else 2
    if null_index == -1:
        description = decode_id3_text(data[4:], encoding)
        text = ""
    else:
        description = decode_id3_text(data[4:null_index], encoding)
        text = decode_id3_text(data[null_index + terminator_length:], encoding)
    return {
        "language": language,
        "description": description,
        "text": text
    }


def parse_apic_frame(data: bytes):
    """
    <Header for 'Attached picture', ID: "APIC">
    Text encoding   $xx
    MIME type       <text string> $00
    Picture type    $xx
    Description     <text string according to encoding> $00 (00)
    Picture data    <binary data>
    """
    if not data:
        return {"mimetype": "", "description": "", "type": 0, "bytes": b""}
    encoding = data[0]
    mimetype_terminator = find_terminator(data, 1, 0)
    if mimetype_terminator == -1:
        return {"mimetype": "", "description": "", "type": 0, "bytes": b""}
    mimetype = data[1:mimetype_terminator].decode(DEFAULT_ENCODING, errors="replace")
    if mimetype_terminator + 1 >= len(data):
        return {"mimetype": mimetype, "description": "", "type": 0, "bytes": b""}
    picture_type = data[mimetype_terminator + 1]  # TODO: add picture type int to string lookup map
    desc_terminator = find_terminator(data, mimetype_terminator + 2, encoding)
    terminator_length = 1 if encoding in (0, 3) else 2
    if desc_terminator == -1:
        description = decode_id3_text(data[mimetype_terminator + 2:], encoding)
        image_bytes = b""
    else:
        description = decode_id3_text(data[mimetype_terminator + 2:desc_terminator], encoding)
        image_bytes = data[desc_terminator + terminator_length:]
    return {'mimetype': mimetype, 'description': description, 'type': picture_type, 'bytes': image_bytes}


def get_tag(filename: str) -> Mp3Tag | None:
    """
    :param filename: mp3 filename
    :return: Mp3Tags object of mp3 file tag attributes
    """
    metadata = dict()
    with open(filename, "rb") as file:
        if file.read(3) != b"ID3":  # invalid file type or mp3 w/o id3v2
            return None
        version = file.read(2)
        if len(version) < 2:
            return None
        if version[0] != 3:  # reading two bytes to skip over version revision number
            raise NotImplementedError("ID3v2.4 not currently supported")
        file.read(1)  # header flags
        # decode tag size encoded as synchsafe
        size_bytes = file.read(4)
        if len(size_bytes) < 4:
            return None
        view = memoryview(size_bytes)
        size = (view[0] << 21) | (view[1] << 14) | (view[2] << 7) | (view[3])
        tag_size = size + HEADER_LENGTH
        # get frames from mp3 file
        while file.tell() < tag_size:
            # parse frame header
            frame_id_bytes = file.read(4)
            if len(frame_id_bytes) < 4:
                break
            frame_id = frame_id_bytes.decode(DEFAULT_ENCODING)
            if frame_id.strip(NULL) == "":
                break
            frame_size_bytes = file.read(4)
            if len(frame_size_bytes) < 4:
                break
            frame_size = int.from_bytes(frame_size_bytes, "big")
            file.read(2)  # skip frame flags
            body = file.read(frame_size)
            # extract frame content based on frame type
            if frame_id not in METADATA_MAP:
                continue
            if re.match(r"^T[0-9A-Z]{3}$", frame_id) and frame_id != "TXXX":  # text information frame
                content = parse_text_frame(body)
            elif frame_id == "APIC":  # attached picture
                content = parse_apic_frame(body)
            elif frame_id == "COMM":  # comments
                content = parse_comment_frame(body)
            else:
                continue
            metadata.update({frame_id: content})

    return format_tags(metadata)
