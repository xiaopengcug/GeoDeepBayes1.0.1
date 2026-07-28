---
title: 'WP8/WP9 Git 持久化与远程证明'
type: 'chore'
created: '2026-07-27'
status: 'authorized-submission-in-progress-wp5-blocked'
review_loop_iteration: 1
baseline_commit: '50e25166f8897f0fc6e82cbadbc3c4f0a98c14d5'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** WP8/WP9 关键证据和整改资产未由当前 main 提交及远程证明覆盖。

**Approach:** 先界定应跟踪资产，再经单独授权提交、推送并验证受保护 main 的双平台 CI 与证明。

## Boundaries & Constraints

**Always:** 提交前核对清单、大小、忽略策略和秘密扫描。

**Ask First:** `git add/commit/push`、PR、发布或远程配置变更。

**Never:** 强推、绕过保护、提交临时/原始大文件或伪造 Sigstore/Rekor。

</frozen-after-approval>

## Code Map

- `validation/wp8/`、`validation/wp9/`、`src/geodeepbayes/`、`tests/` -- 已界定的证据、生成器、源码和验证资产。
- `_bmad-output/.../validation/wp9/manifest-v1.json` -- 证据清单。
- `.gitignore`、`.github/workflows/ci.yml` -- 跟踪与远程门禁。

## Tasks & Acceptance

**Execution:**
- [x] 生成 tracked/ignored/required 清单并核对 manifest 闭包。
- [x] 在远程测试和 WP9 审计前确定性重生成三个 ignored supplement NPZ，并由登记哈希 fail-closed。
- [ ] 提交相关代码、文档、指针和受控证据。（用户已明确授权；精确暂存已完成，等待最终 manifest/plan 刷新）
- [ ] 推送并验证 Ubuntu/Windows required gates 及 Sigstore/Rekor 证明覆盖该提交。（用户已明确授权；WP5 仍为真实阻断，不得伪造证明成功）

**Acceptance Criteria:**
- Given 提交授权，when 核对 Git，then所有 required 资产被跟踪且无临时/秘密文件。
- Given 远程运行，when 查询目标 SHA，then双平台门和证明均成功；否则保持阻断。

## Verification

- `python -m uv run --frozen python validation/wp9/build_persistence_plan.py`
- `python -m uv run --frozen python validation/wp9/validate_wp9.py`
- `git ls-files validation/`
- `git status --short`
- 目标提交 SHA 的远程 CI 与证明核验

## Local Preparation Result

- 已生成 `validation/wp9/persistence-plan-v1.json`；绑定 WP9 manifest 的 36 个成员，全部存在且 SHA-256/字节数闭包通过。
- 另列 162 个不重复执行/源码/测试控制输入（含 WP5/WP6/WP7 直接与关键传递依赖）；合计 195 个 `required-git` 路径，其中 132 个当前内容尚未进入冻结基线 HEAD。
- 三个 supplement NPZ 被明确分类为 `required-generated-artifact`，继续受 `.gitignore` 保护；本地两次隔离重生成的文件哈希彼此一致并匹配已登记 SHA-256。未来远程流程必须执行同一重生成/哈希核验，不得强制提交二进制产物。
- `persistence-plan-v1.json` 是由受控 builder 与绑定输入生成的本地/CI 派生报告，不纳入 required Git 自哈希集合；builder、规格和输入清单本身均为 required Git。
- required 集合的仓库范围扫描未发现秘密、本机绝对路径或超过 50 MiB 的待提交文件；无 `required-but-ignored-unresolved` 项。
- 白名单暂存前本地准备状态为 `passed`；用户授权后已按 195 个 required 路径精确暂存，120 个路径相对 HEAD 形成变更，白名单外 staged 路径为 0。builder 将“已暂存但尚未提交”继续 fail-closed 报为本地阻断，这是状态观测而非授权缺失。
- 最新统一 runner 为 `433 passed、1 skipped、119 warnings`；WP7、WP8 synthetic、WP9 均通过，live blocker 精确仅为 `wp5`。`release_ready=false`、`remote_attestation_verified=false`。
- 本事实快照尚未执行 commit、push、PR、远程配置或证明发布；本轮用户已明确重新协商 Ask First 边界并授权精确提交、推送和远程双平台证明。

## Review Findings Addressed

- 持久化计划从已发布的 manifest 逐成员重算 SHA-256 和字节数，遇到漂移直接失败，不以文件存在替代闭包校验。
- tracked/ignored 分类直接调用 Git；生成资产与无分发策略的 ignored 资产分开报告。
- 使用 `tools/validate_repository_scope.py` 的同一组秘密、绝对路径和大小规则扫描 required 集合。
- 从 `final-gates-v1.json` 的 `release_acceptance.blocking_gates` 派生 live blockers，不能因本地准备成功而把远程放行写为成功。
- 生成资产在两个独立临时根中重放并逐文件比较登记哈希；临时产物不进入工作区或 manifest。
