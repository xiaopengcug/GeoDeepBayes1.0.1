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
- [x] 提交相关代码、文档、指针和受控证据；初始目标提交为 `707f4aab48d38523e396ee6793f698c3a4615bc9`。
- [x] 直接推送受保护 `main` 被 2/2 required checks 正确拒绝；改推 `codex/acceptance-review03-remediation` 并创建 PR #6。
- [ ] 修复首轮 Ubuntu/Windows clean-checkout 同时发现的 WP8 脚本传递闭包缺口，推送后重跑双平台门。（WP5 仍为真实阻断，不得伪造证明成功）

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
- 首轮另列 162 个不重复执行/源码/测试控制输入，但远程 clean checkout 证明该集合漏掉 pytest 直接导入的 WP8 顶层脚本和 synthetic gate 校验的完整受保护 JSON 包。计划现以浅层 glob 纳入 `validation/wp8/*.py` 全部 204 个脚本及 `feasibility-v1/*.json` 全部 185 个成员，共列 546 个控制输入；合计 579 个 `required-git` 路径，其中 220 个当前内容尚未进入 `707f4aab…` 基线。
- 三个 supplement NPZ 被明确分类为 `required-generated-artifact`，继续受 `.gitignore` 保护；本地两次隔离重生成的文件哈希彼此一致并匹配已登记 SHA-256。未来远程流程必须执行同一重生成/哈希核验，不得强制提交二进制产物。
- `persistence-plan-v1.json` 是由受控 builder 与绑定输入生成的本地/CI 派生报告，不纳入 required Git 自哈希集合；builder、规格和输入清单本身均为 required Git。
- required 集合的仓库范围扫描未发现秘密、本机绝对路径或超过 50 MiB 的待提交文件；无 `required-but-ignored-unresolved` 项。
- 首轮白名单暂存按 195 个 required 路径执行，119 个路径相对 HEAD 形成变更，白名单外 staged 路径为 0。远程失败后，builder 的基线更新为 `707f4aab…`，扩大后的 579 路径全部通过扫描且无 unresolved ignored 项；下一提交必须按新集合重新精确暂存。
- 最新统一 runner 为 `433 passed、1 skipped、119 warnings`；WP7、WP8 synthetic、WP9 均通过，live blocker 精确仅为 `wp5`。`release_ready=false`、`remote_attestation_verified=false`。
- PR #6 首轮远程运行 `30326446841` 已提供双平台失败证明：Ubuntu job `90172773622` 与 Windows job `90172773641` 都在 pytest collection 因同一组缺失 WP8 脚本失败；attestation job `90172874282` 因依赖门失败正确 `skipped`。该失败被用于扩大传递闭包，不被改写为通过。

## Review Findings Addressed

- 持久化计划从已发布的 manifest 逐成员重算 SHA-256 和字节数，遇到漂移直接失败，不以文件存在替代闭包校验。
- tracked/ignored 分类直接调用 Git；生成资产与无分发策略的 ignored 资产分开报告。
- 使用 `tools/validate_repository_scope.py` 的同一组秘密、绝对路径和大小规则扫描 required 集合。
- 从 `final-gates-v1.json` 的 `release_acceptance.blocking_gates` 派生 live blockers，不能因本地准备成功而把远程放行写为成功。
- 生成资产在两个独立临时根中重放并逐文件比较登记哈希；临时产物不进入工作区或 manifest。
