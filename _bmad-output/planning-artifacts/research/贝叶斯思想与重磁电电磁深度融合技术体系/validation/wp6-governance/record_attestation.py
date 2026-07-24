"""在gh验证成功后记录不含凭据的证明定位信息。"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--certificate-identity", required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--verification-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bundle_bytes = args.bundle.read_bytes()
    bundle = json.loads(bundle_bytes)
    verification_log = args.verification_log.read_bytes()
    if not verification_log.strip():
        raise ValueError("cosign验证日志为空")
    tlog_entries = bundle.get("verificationMaterial", {}).get("tlogEntries", [])
    if not tlog_entries:
        raise ValueError("Sigstore bundle缺少透明日志包含证明")
    record = {
        "schema_version": "1.0.0",
        "verified": True,
        "provider": args.provider,
        "commit_sha": args.commit_sha,
        "repository": args.repository,
        "run_url": args.run_url,
        "certificate_identity": args.certificate_identity,
        "certificate_oidc_issuer": "https://token.actions.githubusercontent.com",
        "bundle_sha256": sha256(bundle_bytes).hexdigest(),
        "verification_log_sha256": sha256(verification_log).hexdigest(),
        "rekor_log_indexes": [entry["logIndex"] for entry in tlog_entries],
    }
    args.output.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
