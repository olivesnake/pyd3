# 2024 Oliver

import string
import re
from typing import List, Dict, Any
from pydantic import BaseModel

# http://www.multiweb.cz/twoinches/mp3inside.htm
# https://mutagen-specs.readthedocs.io/en/latest/id3/id3v2.4.0-structure.html

__all__ = ["get_tags", "Mp3Tag"]
__version__ = "1.0.0"

NULL = '\x00'
TAG_OFFSET = 10  # bytes
ID3v2_HEADER_LENGTH = 10  # bytes
DEFAULT_ENCODING = 'ISO-8859-1'  # standard mp3 text encoding
JPEG_SOI_MARKER = b'\xFF\xD8'  # start of image marker for jpeg files
JPEG_EOI_MARKER = b'\xFF\xD9'  # end of image

FRAME_IDS = [b'TIT2', b'TALB', b'TPUB', b'TCON', b'TYER', b'TRCK',
             b'TOPS', b'TPE1', b'TPE2', b'TCOM', b'APIC', b'COMM', b'WXXX']

METADATA_MAP = {
    'TIT2': 'title', 'TALB': 'album', 'TPUB': 'publisher', 'TCON': 'genre',
    'TYER': 'year', 'TRCK': 'track_number', 'TOPS': 'disc_number', 'TPE1': 'artist1',
    'TPE2': 'artist2', 'TCOM': 'composer', 'APIC': 'artwork', 'COMM': 'comments', 'WXXX': 'url'
}

FRAME_ENCODING = {
    0: 'ISO-8859-1', 1: 'UTF-16', 2: 'UTF-16BE', 3: 'UTF-8'
}


class Mp3Tag(BaseModel):
    album: str
    artists: List[str]
    artwork: bytes
    comments: str
    genre: str
    publisher: str
    title: str
    track_number: int
    url: str
    year: int


def extract_text(s) -> str:
    a = re.sub(r'\x00', '', s)
    return clean_string(a)


def clean_string(s: str) -> str:
    """
    remove nonprintable characters from a string
    :param s: string
    :return: string with only printable characters
    """
    result = ''.join(filter(lambda c: c in string.printable, s))
    return result


def int_from_sync_safe(data: bytes) -> int:
    """
    gets integer value from synchronization safe data
    :param data: binary sync safe data
    :return: integer value
    """
    n = sum(b << ((3 - i) * 7) for i, b in enumerate(data))
    return n


def handle_image_frame(frame_data: bytes, tag: bytes) -> bytes:
    """
    extract image byte data from mp3 file frame
    https://docs.fileformat.com/image/jpeg/
    :param frame_data: frame data
    :param tag: mp3 tag
    :return: image bytes
    """
    # get text encoding
    text_encoding = frame_data[0]
    encoding = FRAME_ENCODING[text_encoding]
    # find mime type and determine starting point of image data
    match = re.search(r'image/[a-z]+', frame_data.decode(encoding))
    mime_type = frame_data[match.start():match.end()]
    if mime_type != b'image/jpeg':
        # TODO: add support for other MIME types
        return None
    # get first instance of jpeg image start
    img_start = tag.find(JPEG_SOI_MARKER)
    # get last instance of jpeg image end marker incase of EXIF
    img_end = tag.rfind(JPEG_EOI_MARKER)
    img_data = tag[img_start:img_end + 2]
    return img_data


def handle_text_frame(frame_data, tag=None):
    """
    extract desired string from text frames of the mp3 tag
    :param frame_data: hex data frame
    :param tag: mp3 tag (placeholder)
    :return:
    """
    text_content = clean_string(frame_data.decode(DEFAULT_ENCODING))
    return text_content


def _get_tag_data(tag, frame_id_bytes):
    """"

    :param tag:
    :param frame_id_bytes:
    :return:
    """
    tag_start_idx = tag.find(frame_id_bytes)
    frame_header = tag[tag_start_idx:tag_start_idx + TAG_OFFSET]  # get the header for the tag
    frame_id = frame_header[0:4].decode(DEFAULT_ENCODING)  # defines the tag (eg. Song title, artist)
    frame_size = int_from_sync_safe(frame_header[4:8])  # how long the tag data is not including the header
    frame_flags = frame_header[8:10]  # get any possible flags
    offset = tag_start_idx + TAG_OFFSET
    frame_data = tag[offset:offset + frame_size]
    content = handle_image_frame(frame_data, tag) if frame_id == 'APIC' else handle_text_frame(frame_data, tag)
    return content


def remove_keys(d, keys):
    """
    remove keys from a dictionary
    :param d: dictionary
    :param keys: list of keys to be removed
    :return: dictionary with removed keys
    """
    for key in filter(lambda k: k in d, keys):
        del d[key]
    return d


def prettify_tags(tag_frames) -> dict:
    """
    modify values so they are of desired formatting
    :tag_frames:
    :return: updated dictionary
    """
    tags = dict()
    for k, v in tag_frames.items():
        key = METADATA_MAP[k]
        if key == 'track_number':
            v = v.split('/')[0]
        if key == 'track_number' or key == 'year':
            v = int(v)
        tags[key] = v

    # put all artists/composer into on key
    v = set()
    for k in ['artist1', 'artist2', 'composer']:
        if tags.get(k):
            v.add(tags[k])

    artists = list(sorted(v))
    tags['artists'] = artists
    tags = remove_keys(tags, keys=['artist1', 'artist2', 'composer'])
    tags = dict(sorted(tags.items()))
    return tags


def get_tags(filename: str) -> Mp3Tag:
    """
    :param filename: mp3 filename
    :return: dictionary of metadata from mp3 file
    """
    with open(filename, mode='rb') as mp3_file:
        id3v2_header = mp3_file.read(ID3v2_HEADER_LENGTH)
        if id3v2_header[0:3] != b'ID3':  # check if id3v2
            return {}  # unsupported currently
        # compute total metadata tag size and get tag data
        tag_size = int_from_sync_safe(id3v2_header[6:10])
        tag = mp3_file.read(tag_size)
    frames = dict()
    # get all (useful) tag data
    for frame_id in filter(lambda fid: tag.find(fid) != -1, FRAME_IDS):
        frames[frame_id.decode(DEFAULT_ENCODING)] = _get_tag_data(tag, frame_id)
    # map tags to more developer/user friendly keys
    tags = prettify_tags(frames)
    tags = Mp3Tag(**tags)
    return tags
