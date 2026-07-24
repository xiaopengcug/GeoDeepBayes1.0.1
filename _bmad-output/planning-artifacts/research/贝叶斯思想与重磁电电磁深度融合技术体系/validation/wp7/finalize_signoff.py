from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import tempfile


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--synthetic-run", type=Path, required=True)
    parser.add_argument("--do27-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reviews = json.loads(args.reviews.read_text(encoding="utf-8-sig"))
    expected = {"numerical", "qa", "science"}
    if {item["id"] for item in reviews} != expected:
        raise RuntimeError("three required independent roles are missing")
    outputs = [Path(item["output"]).resolve() for item in reviews]
    if len(set(outputs)) != 3:
        raise RuntimeError("review outputs must be three distinct files")
    role_records = []
    review_digests = set()
    for item, output in zip(reviews, outputs, strict=True):
        text = output.read_text(encoding="utf-8")
        if not re.search(
            r"(?mi)^#{1,6}\s+\**Verdict:\s*\**Approved\**\s*$", text
        ):
            raise RuntimeError(f"{item['id']} did not approve")
        output_digest = sha256(text.encode("utf-8")).hexdigest()
        if output_digest in review_digests:
            raise RuntimeError("review outputs must have distinct content")
        review_digests.add(output_digest)
        role_records.append({
            "role": item["id"], "identity_type": "ai", "decision": "Approved",
            "review_sha256": output_digest, "review_text": text,
        })
    decided_at = datetime.now(timezone.utc).isoformat()
    manifests = {}
    for label, run in (("synthetic", args.synthetic_run), ("do27", args.do27_run)):
        producer_path = run / "run-manifest.json"
        if producer_path.is_file():
            producer = json.loads(producer_path.read_text(encoding="utf-8"))
            producer["approval"] = {
                "owner": "WP7三角色独立AI技术复核",
                "date": decided_at,
                "decision": "approved",
            }
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=producer_path.parent, delete=False
            ) as stream:
                stream.write(json.dumps(producer, ensure_ascii=False, indent=2) + "\n")
                staged = Path(stream.name)
            staged.replace(producer_path)
        path = run / "evidence-run-v2.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        if producer_path.is_file():
            for item in value["outputs"]:
                if Path(item["path"]).name == "run-manifest.json":
                    item["bytes"] = producer_path.stat().st_size
                    item["sha256"] = digest(producer_path)
        value["approval"] = {
            "identity": "WP7三角色独立AI技术复核",
            "identity_type": "ai", "decided_at": decided_at,
            "decision": "approved",
        }
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            staged = Path(stream.name)
        staged.replace(path)
        manifests[label] = {
            "path": path.as_posix(), "sha256": digest(path),
            "run_id": value["run_id"], "evidence_id": value["evidence_id"],
        }
    signoff = {
        "schema": "wp7-ai-signoff-v1", "status": "Done",
        "decided_at": decided_at, "roles": role_records,
        "manifests": manifests,
        "scope_limitations": [
            "AI技术签核，非自然人签章",
            "仅限指定小规模合成DA与DO-27现代API降阶单物理兼容",
            "不证明PGI、联合、贝叶斯、模型恢复、现场、资源量或生产能力",
            "本地证据未要求Sigstore远程证明"
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=args.output.parent, delete=False
    ) as stream:
        stream.write(json.dumps(signoff, ensure_ascii=False, indent=2) + "\n")
        staged = Path(stream.name)
    staged.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
