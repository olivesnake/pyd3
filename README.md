# pyd3 🐍🎧

A lightweight, slightly opionionated metadata extractor for mp3 files that combines strengths and fills in the gaps
from other options.

## Features

* Returns object class for easy access and code completion for its attributes in IDEs
* 'artwork' attribute that contains the bytes for the song's artwork allowing you to easily write the full definition
  image to disk

## Get Started

```python
from pyd3 import get_tags

metadata = get_tags("song.mp3")
``` 

## Examples

### Populate database insertion with just an mp3 file

```python
import sqlite3
from pyd3 import get_tags

con = sqlite3.connect("mydb.db")
cur = con.cursor()

metadata = get_tags("song.mp3")

# artist attribute is a list of strings sourced from the composer, artist1, and artist2 tags
cur.executemany("INSERT INTO artist (name) VALUES (?);", metadata.artists)

cur.execute(
    "INSERT INTO track (title, track_num, disc_num, album_name) VALUES (?, ?, ?, ?);",
    (metadata.title, metadata.track_number, metadata.disc_number, metadata.album)
)

con.commit()
con.close()
```

### Create JPEG file of album artwork

```python
from pyd3 import get_tags

tags = get_tags("song.mp3")

with open("artwork.jpeg", mode="wb") as file:
    file.write(tags.artwork)
```