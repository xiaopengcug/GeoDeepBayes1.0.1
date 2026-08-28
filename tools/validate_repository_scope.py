"""首次提交与CI的仓库范围门：拒绝数据、缓存、大文件和明显凭据。"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess


MAX_BYTES = 50 * 1024 * 1024
FORBIDDEN_PARTS = (
    "/_bmad-output/",
    "/open-data/",
    "/work/",
    "/source/",
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
    r"(?:\b[A-Za-z]:\\[^\\\r\n]{2,}\\|/(?:home|Users|root)/)"
)
STRICT_TEXT_SUFFIXES = {".py", ".ps1", ".yml", ".yaml", ".toml", ".json"}


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
    for relative in tracked_files(root):
        normalized = f"/{relative}"
        path = root / relative
        if not path.is_file():
            continue
        if normalized == "/CLAUDE.md" or normalized.endswith("/.run.lock"):
            failures.append(f"精选发布树禁止成员: {relative}")
            continue
        wp1_manifest = normalized.endswith(
            "/validation/wp1-toy/output/manifest.json"
        )
        if any(part in normalized for part in FORBIDDEN_PARTS) and not wp1_manifest:
            failures.append(f"禁止纳入Git的路径: {relative}")
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
