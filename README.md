# pyd3

```python
from pyd3 import get_tags
```

### Create JPEG file
```python
from pyd3 import get_tags

tags = get_tags("song.mp3")

with open("artwork.jpeg", mode="wb") as file:
    file.write(tags.artwork)
```