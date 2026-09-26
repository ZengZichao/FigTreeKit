# SPDX-License-Identifier: GPL-2.0-or-later
# This file is part of FigTreeKit; see LICENSE and NOTICE for licensing terms.
"""Post-render appearance pass for bitmap output.

Stock FigTree 1.4.4 writes the *global appearance* colours (background,
foreground/branch) into its GUI model but its headless ``-graphic`` renderer
does not apply them to raster output, so a scripted or headless render would
silently ignore ``--background-color`` and ``--foreground-color``.

FigTreeKit applies those two settings as a documented post-processing step of
its own render path instead of leaving it to individual front ends.  Keeping
it here means the scripted workflow and any graphical front end produce the
same pixels from the same command line, which is what makes an exported
command a replay record.

Vector output (PDF/SVG) is returned untouched: those formats carry the
FigTree-drawn content and cannot be recoloured losslessly.

Requires Pillow, which is an optional dependency of FigTreeKit.  When Pillow
is unavailable the pass reports that it did nothing, so callers can warn
rather than silently differ.
"""

from __future__ import annotations

import os
from typing import Optional

__all__ = ["apply_appearance_pass", "appearance_pass_supported"]

#: Raster formats the pass can rewrite.
RASTER_FORMATS = ("PNG", "JPEG", "JPG")

#: Pixels whose brightest channel is below this value are treated as FigTree's
#: default black drawing colour and are recoloured to the requested foreground.
NEAR_BLACK_THRESHOLD = 50

#: Pixels within this RGB distance of the protected colour (typically the
#: tip-label colour, which FigTree *does* honour through ``[&!color=...]``
#: node annotations) are left alone so they are not flattened by the recolour.
PROTECTED_DISTANCE = 80


def appearance_pass_supported() -> bool:
    """Return ``True`` when Pillow is importable and the pass can run."""
    try:
        import PIL.Image  # noqa: F401
    except Exception:
        return False
    return True


def _hex_to_rgb(value: str) -> Optional[tuple]:
    """Parse ``#RRGGBB`` / ``#RGB`` into an ``(r, g, b)`` tuple."""
    if not value:
        return None
    text = str(value).strip().lstrip("#").upper()
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return None
    try:
        return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def apply_appearance_pass(
    image_path: str,
    *,
    background_color: Optional[str] = None,
    foreground_color: Optional[str] = None,
    protected_color: Optional[str] = None,
    image_format: Optional[str] = None,
) -> bool:
    """Recolour and flatten a rendered raster image in place.

    Args:
        image_path: Path to the rendered image; rewritten in place.
        background_color: ``#RRGGBB`` to flatten transparency onto.  When
            ``None`` white is used, because Pillow's ``RGB`` conversion would
            otherwise turn transparent regions black.
        foreground_color: ``#RRGGBB`` for FigTree's default-black drawing
            elements (branches, scale bar, axis text).
        protected_color: ``#RRGGBB`` already honoured by FigTree through node
            annotations; pixels close to it are not recoloured.
        image_format: Force the format; inferred from ``image_path`` when
            ``None``.

    Returns:
        ``True`` when the image was rewritten, ``False`` when the pass was a
        no-op (vector format, nothing requested, or Pillow unavailable).

    Raises:
        RenderError: If the image is requested to be recoloured but cannot be
            read.
    """
    fmt = (image_format or os.path.splitext(image_path)[1].lstrip(".")).upper()
    if fmt not in RASTER_FORMATS:
        return False
    if not (background_color or foreground_color):
        return False
    try:
        from PIL import Image
    except Exception:
        return False

    from .exceptions import RenderError

    try:
        with Image.open(image_path) as handle:
            img = handle.convert("RGBA")
    except Exception as exc:
        raise RenderError(
            f"FigTreeKit could not open {image_path!r} for the appearance "
            f"post-processing pass: {exc}"
        ) from exc

    changed = False
    fg = _hex_to_rgb(foreground_color) if foreground_color else None
    protect = _hex_to_rgb(protected_color) if protected_color else None
    if fg:
        pixels = img.load()
        w, h = img.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                if a == 0 or max(r, g, b) >= NEAR_BLACK_THRESHOLD:
                    continue
                if protect is not None:
                    dist = ((r - protect[0]) ** 2
                            + (g - protect[1]) ** 2
                            + (b - protect[2]) ** 2) ** 0.5
                    if dist < PROTECTED_DISTANCE:
                        continue
                pixels[x, y] = (fg[0], fg[1], fg[2], a)
        changed = True

    # Always flatten transparency (to the requested colour or to white):
    # leaving an alpha channel in a JPEG is not representable and Pillow's
    # RGB conversion would paint the background black.
    bg = _hex_to_rgb(background_color) or (255, 255, 255)
    backdrop = Image.new("RGBA", img.size, bg + (255,))
    img = Image.alpha_composite(backdrop, img)

    out_format = "JPEG" if fmt in ("JPEG", "JPG") else "PNG"
    img.convert("RGB").save(image_path, format=out_format,
                            **({"quality": 95} if out_format == "JPEG" else {}))
    return changed or True
