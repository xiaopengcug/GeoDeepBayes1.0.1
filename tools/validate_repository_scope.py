"""首次提交与CI的仓库范围门：拒绝数据、缓存、大文件和明显凭据。"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import re
import subprocess


MAX_BYTES = 50 * 1024 * 1024
FORBIDDEN_PARTS = (
    "/open-data/",
    "/work/",
    "/source/",
    "/versions/",
    "/validation/runs/",
    "/output/",
    "/.venv",
    "/__pycache__/",
    "/.stage-",
)
SECRET_PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}
# A drive prefix alone also appears in PowerShell regex literals (for example
# ``:\s*\r``).  Require a complete directory segment to avoid treating those
# expressions as leaked workstation paths.
ABSOLUTE_PATH = re.compile(
    r"(?:\b[A-Za-z]:\\[^\\\r\n]{2,}\\|"
    r"(?<![A-Za-z0-9._-])/(?:home|Users|root)/)"
)
STRICT_TEXT_SUFFIXES = {".py", ".ps1", ".yml", ".yaml", ".toml", ".json"}
CONTROLLED_WP7_VERSION_PREFIXES = (
    "/_bmad-output/planning-artifacts/research/"
    "贝叶斯思想与重磁电电磁深度融合技术体系/"
    "validation/wp7/versions/do27-v2-20260724/",
    "/_bmad-output/planning-artifacts/research/"
    "贝叶斯思想与重磁电电磁深度融合技术体系/"
    "validation/wp7/versions/do27-v4-20260724/",
    "/_bmad-output/planning-artifacts/research/"
    "贝叶斯思想与重磁电电磁深度融合技术体系/"
    "validation/wp7/versions/synthetic-block-v6-20260724/",
)
RESEARCH_RELATIVE = (
    "_bmad-output/planning-artifacts/research/"
    "贝叶斯思想与重磁电电磁深度融合技术体系"
)


def _active_version_prefixes(root: Path) -> tuple[str, ...]:
    """Derive the only WP2-WP5 version directories allowed in Git."""
    prefixes: list[str] = []
    validation = root / RESEARCH_RELATIVE / "validation"
    for work_package in ("wp2-toy", "wp3-physics", "wp4-decision", "wp5-consistency"):
        pointer_path = validation / work_package / "active-output.json"
        if not pointer_path.is_file():
            continue
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        version_path = pointer.get("version_path")
        if (
            not isinstance(version_path, str)
            or not version_path.startswith("versions/")
            or ".." in Path(version_path).parts
        ):
            raise ValueError(f"invalid active version pointer: {pointer_path}")
        prefixes.append(
            f"/{RESEARCH_RELATIVE}/validation/{work_package}/"
            f"{Path(version_path).as_posix().rstrip('/')}/"
        )
    return tuple(prefixes)


def permitted_forbidden_path(
    normalized: str, active_version_prefixes: tuple[str, ...] = ()
) -> bool:
    """Return true only for narrow, reviewable generated-evidence exceptions."""
    if normalized.endswith("/validation/wp1-toy/output/manifest.json"):
        return True
    if normalized.endswith(
        "/research/open-data/00_catalog/open_geophysics_data_manifest.json"
    ):
        return True
    return normalized.startswith(
        (*active_version_prefixes, *CONTROLLED_WP7_VERSION_PREFIXES)
    )


def tracked_files(root: Path) -> list[str]:
    process = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [
        item.decode("utf-8").replace("\\", "/")
        for item in process.stdout.split(b"\0")
        if item
    ]


def validate(root: Path) -> list[str]:
    failures: list[str] = []
    active_version_prefixes = _active_version_prefixes(root)
    for relative in tracked_files(root):
        normalized = f"/{relative}"
        path = root / relative
        if (
            any(part in normalized for part in FORBIDDEN_PARTS)
            and not permitted_forbidden_path(normalized, active_version_prefixes)
        ):
            failures.append(f"禁止纳入Git的路径: {relative}")
            continue
        if not path.is_file():
            continue
        if path.stat().st_size > MAX_BYTES:
            failures.append(f"文件超过50MiB: {relative}")
            continue
        if path.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                failures.append(f"疑似{name}: {relative}")
        if path.suffix.lower() in STRICT_TEXT_SUFFIXES and ABSOLUTE_PATH.search(text):
            failures.append(f"受控代码或配置包含绝对本机路径: {relative}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    failures = validate(args.root.resolve())
    if failures:
        for failure in failures:
            print(f"ERROR {failure}")
        return 1
    print("PASS repository scope")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
