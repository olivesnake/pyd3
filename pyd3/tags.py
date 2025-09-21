"""
Oliver June 2024
"""
import re
import codecs
from typing import Dict, Any

__all__ = ["get_tag", "Mp3Tag"]
DEFAULT_ENCODING = 'ISO-8859-1'  # standard mp3 text encoding
HEADER_LENGTH = 10

INT_KEYS = ('track_number', 'disc_number', 'year')
ARTIST_KEYS = ("composer", "artist1", "artist2")
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
        key = METADATA_MAP[k]
        tag.__setattr__(key, v)

    return tag


def decode_id3_text(text_bytes: bytes, encoding: int) -> str:
    """
    decode text bytes in id3v2 tag
    """
    if encoding == 0:  # iso
        text = text_bytes.decode(DEFAULT_ENCODING)
    elif encoding == 1:
        text = text_bytes.decode("utf-16le")
        if text_bytes.startswith(codecs.BOM_UTF16_LE):
            text = text[1:]
    else:
        text = ''
    return text.replace('\x00', '')


def parse_text_frame(data: bytes) -> str:
    """
    parses text from a text information frame
    <Header for 'Text information frame', ID: "T000" - "TZZZ", excluding "TXXX" described in 4.2.2.>
Text encoding    $xx
Information    <text string according to encoding>
    """
    encoding = data[0]
    # convert to bytes and remove null termination
    text_info = data[1:]
    return decode_id3_text(text_info, encoding)


def find_terminator(data: bytes, offset: int, encoding: int) -> int:
    """
    gets index of start of null terminator from bytes based on text encoding
    """
    length = len(data)
    if encoding == 0:
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
    encoding = data[0]
    language = data[1:4].decode()
    null_index = find_terminator(data, 4, encoding)
    description = decode_id3_text(data[4:null_index], encoding)
    text = decode_id3_text(data[null_index + 2:], encoding)
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
    encoding = data[0]
    mimetype_terminator = find_terminator(data, 1, 0)
    mimetype = data[1:mimetype_terminator].decode()
    picture_type = data[mimetype_terminator + 1]  # TODO: add picture type int to string lookup map
    desc_terminator = find_terminator(data, mimetype_terminator + 2, encoding)
    description = decode_id3_text(data[mimetype_terminator + 2:desc_terminator], encoding)
    return {'mimetype': mimetype, 'description': description, 'type': picture_type, 'bytes': data[desc_terminator + 1:]}


def get_tag(filename: str) -> Mp3Tag | None:
    """
    :param filename: mp3 filename
    :return: Mp3Tags object of mp3 file tag attributes
    """
    metadata = dict()
    with open(filename, "rb") as file:
        if file.read(3) != b"ID3":  # invalid file type or mp3 w/o id3v2
            return None
        if file.read(2)[0] != 3:  # reading two bytes to skip over verison revision number
            raise NotImplementedError("ID3v2.4 not currently supported")
        # decode tag size encoded as synchsafe
        view = memoryview(file.read(4))
        size = (view[0] << 21) | (view[1] << 14) | (view[2] << 7) | (view[3])
        file.read(1)  # version 4 not supported so will be 0
        tag_size = size + HEADER_LENGTH
        # get frames from mp3 file
        while file.tell() < tag_size:
            # parse frame header
            frame_id = file.read(4).decode(DEFAULT_ENCODING)
            frame_size = int.from_bytes(file.read(4))
            file.read(2)  # skip frame flags
            body = file.read(frame_size)
            # extract frame content based on frame type
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
