from __future__ import annotations

from scripts.sync_readme_gallery import (
    END_MARKER,
    START_MARKER,
    build_gallery,
    replace_gallery_block,
)


def test_build_gallery_uses_grouped_screenshot_paths() -> None:
    gallery = build_gallery()

    assert "docs/screenshots/readme/v4-login.png" in gallery
    assert "docs/screenshots/readme/v4-control-plane.png" in gallery
    assert "docs/screenshots/v4-login.png" not in gallery
    # webui-* screenshots don't exist in the repo and were dropped from the gallery.
    assert "webui" not in gallery


def test_replace_gallery_block_swaps_only_marker_region() -> None:
    source = f"before\n{START_MARKER}\nold\n{END_MARKER}\nafter\n"

    updated = replace_gallery_block(source, "new-gallery")

    assert updated == f"before\n{START_MARKER}\nnew-gallery\n{END_MARKER}\nafter\n"
