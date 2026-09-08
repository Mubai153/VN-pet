"""Verify committed Codex pet packages against their approval records."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
FRAME_COUNTS = (6, 8, 8, 4, 5, 8, 6, 6, 6, 8, 8)
ATLAS_LAYOUT = {
    "width": 1536,
    "height": 2288,
    "cell_width": 192,
    "cell_height": 208,
    "columns": 8,
    "rows": 11,
    "standard_frames": 57,
    "look_frames": 16,
    "neutral_cells": 1,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_file(directory: Path, target: str) -> Path:
    require(not re.match(r"^(?:[a-zA-Z][\w+.-]*:|[/\\])", target),
            f"Expected relative package path: {target}")
    path = (directory / target).resolve()
    require(path.is_relative_to(directory.resolve()), f"Path escapes directory: {target}")
    require(path.is_file(), f"Missing file: {path}")
    return path


def verify_links(package: Path) -> None:
    """Keep the public package usable without the rest of the repository."""
    for path in (package / "README.md", package / "preview.html"):
        content = path.read_text(encoding="utf-8")
        if path.suffix == ".md":
            targets = re.findall(r"\[[^\]]*\]\(([^)]+)\)", content)
        else:
            targets = re.findall(r"(?:href|src)\s*=\s*['\"]([^'\"]+)['\"]", content)
            styles = re.findall(r"<style[^>]*>(.*?)</style>", content, re.DOTALL)
            styles += re.findall(r"\bstyle=['\"]([^'\"]*)['\"]", content)
            targets += re.findall(r"url\(\s*['\"]?([^)'\"\s]+)", "\n".join(styles))
            # Dynamic CSS uses atlas.src; verify the literal image input separately.
            atlas_paths = re.findall(r"atlas\.src\s*=\s*['\"]([^'\"]+)['\"]", content)
            require(atlas_paths == ["spritesheet.webp"], "Preview must load package spritesheet.webp")
            targets += atlas_paths
        for target in targets:
            if target.startswith(("data:", "#")):
                continue
            local_file(package, target.split("#")[0])


def verify_package(root: Path, package_id: str) -> None:
    require(bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", package_id)),
            f"Invalid package ID: {package_id}")
    package = root / "packages" / package_id
    record = json.loads((root / "releases" / f"{package_id}.json").read_text(encoding="utf-8"))
    manifest = json.loads(local_file(package, "pet.json").read_text(encoding="utf-8"))
    require(record["package_id"] == manifest["id"] == package_id, "Package IDs do not match")
    require(record["sprite_version_number"] == manifest["spriteVersionNumber"] == 2,
            "Only the approved v2 atlas contract is supported")
    require(manifest["spritesheetPath"] == "spritesheet.webp", "Unexpected spritesheetPath")
    require(record["atlas"] == ATLAS_LAYOUT, "Release atlas layout differs from v2 contract")
    require(set(record["package_files"]) == {"pet.json", "spritesheet.webp"},
            "Approval record must cover pet.json and spritesheet.webp")
    for name, expected in record["package_files"].items():
        require(sha256(local_file(package, name)) == expected, f"Approved hash mismatch: {name}")
    master = record["design_master"]
    master_path = local_file(root, master["path"])
    require(master_path.is_relative_to((root / "design").resolve()), "Master must be under design/")
    require(sha256(master_path) == master["sha256"], "Approved master hash mismatch")

    with Image.open(package / "spritesheet.webp") as atlas:
        require(atlas.format == "WEBP" and atlas.mode == "RGBA", "Expected RGBA WebP")
        require(atlas.size == (1536, 2288), "Expected 1536x2288 atlas")
        alpha = atlas.getchannel("A")
        for row, count in enumerate(FRAME_COUNTS):
            for column in range(8):
                cell = alpha.crop((column * 192, row * 208, (column + 1) * 192, (row + 1) * 208))
                expected = column < count or (row == 0 and column == 6)
                require((cell.getbbox() is not None) == expected,
                        f"Unexpected occupied/empty cell: row={row}, column={column}")
        hidden_rgb = atlas.convert("RGB")
        hidden_rgb.paste((0, 0, 0), (0, 0, *atlas.size), alpha.point(lambda value: 255 if value else 0))
        require(hidden_rgb.getbbox() is None, "RGB residue in fully transparent pixels")
    verify_links(package)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_id", nargs="?", help="Package ID; default: all registered packages")
    args = parser.parse_args()
    try:
        if args.package_id:
            package_ids = [args.package_id]
        else:
            packages = {path.name for path in (ROOT / "packages").iterdir() if path.is_dir()}
            releases = {path.stem for path in (ROOT / "releases").glob("*.json")}
            require(packages == releases and bool(packages), "Package directories and release records differ")
            package_ids = sorted(packages)
        for package_id in package_ids:
            verify_package(ROOT, package_id)
            print(f"PASS {package_id}: approved hashes, v2 atlas, transparency and standalone resources")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")


if __name__ == "__main__":
    main()
