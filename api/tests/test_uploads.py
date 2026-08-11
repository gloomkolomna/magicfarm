import io

import pytest
from PIL import Image

from services.uploads import _process


def _rgba_png(w: int = 100, h: int = 80) -> bytes:
    img = Image.new("RGBA", (w, h), (200, 100, 50, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _la_png(w: int = 100, h: int = 80) -> bytes:
    img = Image.new("LA", (w, h), (128, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _p_mode_png(w: int = 100, h: int = 80) -> bytes:
    palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    flat = [c for t in palette for c in t] + [0] * (768 - len(palette) * 3)
    img = Image.new("P", (w, h))
    img.putpalette(flat)
    for y in range(h):
        for x in range(w):
            img.putpixel((x, y), 1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _rgb_png(w: int = 100, h: int = 80) -> bytes:
    img = Image.new("RGB", (w, h), (90, 160, 70))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _load_pixels(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


# ===== RGBA with transparency → white background =====


def test_rgba_fully_transparent_becomes_white():
    buf = _rgba_png()
    result = _load_pixels(_process(buf, max_size=512))
    assert result.mode == "RGB"
    px = result.getpixel((10, 10))
    assert px == (255, 255, 255)


def test_rgba_opaque_becomes_original_color():
    img = Image.new("RGBA", (40, 40), (0, 128, 255, 255))
    raw = io.BytesIO()
    img.save(raw, format="PNG")
    result = _load_pixels(_process(raw.getvalue(), max_size=512))
    assert result.mode == "RGB"
    px = result.getpixel((5, 5))
    assert px[0] < 5
    assert 120 <= px[1] <= 135
    assert 245 <= px[2] <= 255


def test_rgba_semi_transparent_composites():
    img = Image.new("RGBA", (20, 20), (255, 0, 0, 128))
    raw = io.BytesIO()
    img.save(raw, format="PNG")
    result = _load_pixels(_process(raw.getvalue(), max_size=512))
    assert result.mode == "RGB"
    px = result.getpixel((5, 5))
    assert 250 <= px[0] <= 255
    assert 120 <= px[1] <= 135
    assert 120 <= px[2] <= 135


# ===== LA mode =====


def test_la_fully_transparent_becomes_white():
    buf = _la_png()
    result = _load_pixels(_process(buf, max_size=512))
    assert result.mode == "RGB"
    px = result.getpixel((10, 10))
    assert px == (255, 255, 255)


def test_la_opaque_becomes_gray_white_background():
    img = Image.new("LA", (20, 20), (200, 255))
    raw = io.BytesIO()
    img.save(raw, format="PNG")
    result = _load_pixels(_process(raw.getvalue(), max_size=512))
    assert result.mode == "RGB"
    px = result.getpixel((5, 5))
    assert px == (200, 200, 200)


# ===== P mode =====


def test_p_mode_converted_to_rgb():
    buf = _p_mode_png()
    result = _load_pixels(_process(buf, max_size=512))
    assert result.mode == "RGB"
    px = result.getpixel((10, 10))
    assert px[0] < 2
    assert px[1] > 252
    assert px[2] < 2


# ===== RGB passthrough =====


def test_rgb_passthrough():
    buf = _rgb_png()
    result = _load_pixels(_process(buf, max_size=512))
    assert result.mode == "RGB"
    px = result.getpixel((10, 10))
    assert abs(px[0] - 90) < 2
    assert abs(px[1] - 160) < 2
    assert abs(px[2] - 70) < 2


# ===== Resize =====


def test_resize_downsample():
    img = Image.new("RGB", (800, 600), (100, 200, 50))
    raw = io.BytesIO()
    img.save(raw, format="PNG")
    result_bytes = _process(raw.getvalue(), max_size=400)
    result = _load_pixels(result_bytes)
    assert max(result.size) <= 400


def test_no_resize_when_small():
    img = Image.new("RGB", (200, 150), (50, 100, 150))
    raw = io.BytesIO()
    img.save(raw, format="PNG")
    result_bytes = _process(raw.getvalue(), max_size=400)
    result = _load_pixels(result_bytes)
    assert result.size == (200, 150)


# ===== No max_size =====


def test_no_max_size_returns_original():
    buf = _rgba_png()
    assert _process(buf, max_size=None) == buf
