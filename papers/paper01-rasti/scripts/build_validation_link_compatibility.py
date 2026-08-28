#!/usr/bin/env python3
"""生成历史 validation path/hash 到当前精选发布字节的兼容侧车。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from replay_release import (
    build_validation_link_compatibility,
    write_validation_link_compatibility,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
    )
    args = parser.parse_args(argv)
    repository = args.repository_root.resolve()
    target = write_validation_link_compatibility(repository)
    payload = build_validation_link_compatibility(repository)
    print(
        json.dumps(
            {
                "output": target.relative_to(repository).as_posix(),
                **payload["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
