from io import BytesIO

import pytest
from gilbic_backend.client_photo_repository import InvalidClientPhoto, prepare_photo
from PIL import Image


def picture(kind="PNG", size=(80, 60), color="red", **kwargs):
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format=kind, **kwargs)
    return output.getvalue()


def test_photo_is_decoded_oriented_and_metadata_removed():
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private camera note"
    photo = prepare_photo(picture("JPEG", exif=exif), "image/jpeg")
    with Image.open(BytesIO(photo.content)) as decoded:
        assert decoded.size == (60, 80)
        assert decoded.format == "JPEG"
        assert not decoded.getexif()
    assert photo.content_type == "image/jpeg"
    assert b"private camera note" not in photo.content


def test_large_photo_is_bounded_and_png_supported():
    photo = prepare_photo(picture(size=(3200, 1600)), "image/png")
    with Image.open(BytesIO(photo.content)) as decoded:
        assert decoded.size == (1600, 800)


@pytest.mark.parametrize(
    "content,kind",
    [
        (b"", "image/jpeg"),
        (b"\xff\xd8\xff\xe0truncated", "image/jpeg"),
        (picture(), "image/jpeg"),
        (picture(), "image/svg+xml"),
        (b"x" * (5 * 1024 * 1024 + 1), "image/png"),
        (picture(size=(8193, 1)), "image/png"),
    ],
    ids=["empty", "truncated", "wrong-mime", "unsupported", "too-large", "too-wide"],
)
def test_invalid_or_disguised_photo_is_rejected(content, kind):
    with pytest.raises(InvalidClientPhoto):
        prepare_photo(content, kind)


def test_animated_png_is_not_a_profile_photo():
    output = BytesIO()
    Image.new("RGB", (80, 60), "red").save(
        output,
        format="PNG",
        save_all=True,
        append_images=[Image.new("RGB", (80, 60), "blue")],
        duration=100,
    )
    with pytest.raises(InvalidClientPhoto):
        prepare_photo(output.getvalue(), "image/png")
