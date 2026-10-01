import base64, io
from PIL import Image, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 20_000_000


def validate_image(encoded):
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > 8_000_000:
            raise ValueError("Image exceeds 8 MB.")
        with Image.open(io.BytesIO(raw)) as img:
            if img.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Use PNG, JPG or WEBP.")
            if img.width * img.height > 20_000_000:
                raise ValueError("Image is too large.")
            img.verify()
    except (UnidentifiedImageError, Image.DecompressionBombError) as e:
        raise ValueError("Invalid or oversized image.") from e
    return encoded
