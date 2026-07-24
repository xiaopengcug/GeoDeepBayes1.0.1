"""WP6历史索引、worker边界、证据根与孤儿版本治理。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Iterable


VERSION_RE = re.compile(r"^\d{8}T\d{9}Z-[0-9a-f]{32,40}$")
STAGE_RE = re.compile(r"^\.stage-[0-9a-f]{32}$")


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def canonical_file_bytes(path: Path) -> bytes:
    """文本按Git跨平台语义冻结；二进制保持原字节。"""
    content = path.read_bytes()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def resolve_inside(root: Path, candidate: Path) -> Path:
    root_resolved = root.resolve(strict=True)
    candidate_absolute = candidate.absolute()
    try:
        lexical_relative = candidate_absolute.relative_to(root.absolute())
    except ValueError as error:
        raise ValueError("目标不在受控根目录内") from error
    current = root.absolute()
    for part in lexical_relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("受控路径包含符号链接")
    candidate_resolved = candidate.resolve(strict=True)
    if candidate_resolved == root_resolved or root_resolved not in candidate_resolved.parents:
        raise ValueError("目标不在受控根目录内")
    return candidate_resolved


def validate_worker_boundary(
    versions_root: Path,
    stage: Path,
    worker_identity: str,
    supervisor_identity: str,
) -> None:
    if not worker_identity or not supervisor_identity:
        raise ValueError("worker和supervisor身份不能为空")
    if worker_identity.casefold() == supervisor_identity.casefold():
        raise ValueError("worker与supervisor必须是不同身份")
    if stage.parent.resolve() != versions_root.resolve():
        raise ValueError("stage必须是versions根的直属子目录")
    if not STAGE_RE.fullmatch(stage.name):
        raise ValueError("stage名称不符合受控格式")
    resolve_inside(versions_root, stage)


def validate_legacy_index(research_root: Path, index_path: Path) -> list[str]:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    seen: set[str] = set()
    for item in index["artifacts"]:
        path = item["path"]
        if path in seen:
            errors.append(f"legacy索引重复路径: {path}")
            continue
        seen.add(path)
        candidate = research_root / path
        try:
            candidate = resolve_inside(research_root, candidate)
        except (FileNotFoundError, ValueError):
            errors.append(f"legacy索引路径越界或不可解析: {path}")
            continue
        if not candidate.is_file():
            errors.append(f"legacy索引文件不存在: {path}")
            continue
        canonical = canonical_file_bytes(candidate)
        if len(canonical) != item["bytes"]:
            errors.append(f"legacy索引大小漂移: {path}")
        if sha256(canonical).hexdigest() != item["sha256"]:
            errors.append(f"legacy索引哈希漂移: {path}")
        if item["migration_state"] not in {"v2-sidecar", "Legacy-frozen"}:
            errors.append(f"legacy索引状态非法: {path}")
    return errors


@dataclass(frozen=True)
class GcCandidate:
    path: str
    bytes: int
    age_days: int
    reason: str


def gc_report(
    versions_root: Path,
    protected_names: Iterable[str],
    *,
    retention_days: int = 30,
    quota_bytes: int = 20 * 1024**3,
    now: datetime | None = None,
) -> dict[str, object]:
    """只计算候选；实际删除由显式Prune包装器在二次验证后执行。"""
    now = now or datetime.now(timezone.utc)
    protected = set(protected_names)
    versions: list[tuple[Path, int, int]] = []
    total = 0
    if not versions_root.exists():
        return {"total_bytes": 0, "quota_bytes": quota_bytes, "candidates": []}
    for path in versions_root.iterdir():
        if not path.is_dir() or path.is_symlink() or not VERSION_RE.fullmatch(path.name):
            continue
        size = sum(item.stat().st_size for item in path.rglob("*") if item.is_file() and not item.is_symlink())
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        age = max(0, (now - modified).days)
        versions.append((path, size, age))
        total += size
    candidates: list[GcCandidate] = []
    projected_total = total
    for path, size, age in sorted(versions, key=lambda item: item[0].stat().st_mtime):
        if path.name in protected:
            continue
        if age >= retention_days or projected_total > quota_bytes:
            reason = "retention" if age >= retention_days else "quota"
            candidates.append(GcCandidate(path.name, size, age, reason))
            projected_total -= size
    return {
        "total_bytes": total,
        "quota_bytes": quota_bytes,
        "retention_days": retention_days,
        "candidates": [candidate.__dict__ for candidate in candidates],
    }


def build_evidence_root(
    project_root: Path,
    relative_paths: Iterable[str],
    *,
    commit_sha: str,
) -> dict[str, object]:
    artifacts = []
    project_root = project_root.resolve(strict=True)
    for relative in sorted(set(relative_paths)):
        path = resolve_inside(project_root, project_root / relative)
        if not path.is_file():
            raise FileNotFoundError(relative)
        artifacts.append(
            {
                "path": relative.replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    return {
        "schema_version": "1.0.0",
        "commit_sha": commit_sha,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "artifacts": artifacts,
        "root_sha256": canonical_sha256(artifacts),
    }


def current_identity() -> str:
    return f"{os.name}:{os.getpid()}:{os.environ.get('USERNAME') or os.environ.get('USER') or 'unknown'}"
