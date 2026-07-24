---
title: 'WP6工程契约、CI与证据治理'
type: 'feature'
created: '2026-07-24'
status: 'done'
baseline_commit: 'NO_VCS'
review_loop_iteration: 0
context:
  - '{project-root}/CLAUDE.md'
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/修改计划03.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** WP6已有若干原型契约，但观测字段、能力证据、运行证据和CI门禁不完整；根环境未锁定，治理manifest已漂移，外部可信锚、worker权限隔离和孤儿版本治理仍缺失。

**Approach:** 建立版本化机器契约、五级能力矩阵、evidence-run v2、双平台冻结环境与fail-closed CI；以最终commit的GitHub OIDC attestation作为外部锚，并用独立OS身份、不可达版本GC和版本化治理快照闭环WP6。

## Boundaries & Constraints

**Always:** 保留WP1—WP5历史事实；缺失事实不得推测；Planned/Synthetic不得越级支持现场主张；所有必需门原样传播非零退出码；Git只纳入代码、治理元数据、小型fixture和可验证哈希；所有删除先做引用图、根路径和链接检查；对当前本地文件先清单化，不覆盖用户产物。

**Ask First:** 需要Git LFS或外部对象存储；需要删除受保护/被引用证据；需要重写历史v1运行包；需要扩大到算法、GPU、现场验证；远端权限不足时需要用户完成GitHub管理操作。

**Never:** 伪造审批、签名、运行字段或现场证据；将本地hash冒充外部真实性；把hosted runner机制测试冒充生产主机认证；自动删除active、签核、claim、manifest、迁移envelope或attestation引用版本；提交开放数据、大型work/source、历史versions副本、缓存或凭据。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| valid-contract | 方法契约字段完整 | schema和语义门通过 | 无 |
| invalid-contract | 缺单位/几何/频时/误差/适用域 | 拒绝 | 非零退出并定位字段 |
| legal-capability | 实现、测试、run与成熟度相符 | 允许登记 | 无 |
| illegal-upgrade | placeholder或低等级证据支持高等级主张 | 拒绝 | 非零退出 |
| legacy-run | v1事实不完整 | 保持Legacy-frozen | 不补写未知事实 |
| ci-failure | 测试/契约/治理/锁任一失败 | 阻断required check | 禁止证据发布/升级 |
| attestation-failure | OIDC或证明失败 | main保留但不发布证据 | WP6不得Done |
| unsafe-worker | worker与supervisor同身份或ACL越权 | 拒绝启动 | 不创建正式版本 |
| orphan-gc | 不可达且非保护版本超期/超额 | dry-run报告或显式清理 | 中断保持pointer有效 |

</frozen-after-approval>

## Code Map

- `pyproject.toml`, `.python-version`, `uv.lock` -- Python 3.11.15冻结环境与唯一安装入口。
- `.github/workflows/ci.yml` -- pull_request/merge_group/push双平台阻断门和最终attestation。
- `_bmad-output/.../contracts/` -- 观测、能力、evidence-run v2、registry、fixture和跨字段验证。
- `_bmad-output/.../validation/wp6-governance/` -- 迁移索引、可信根、权限隔离、GC策略及自测。
- `_bmad-output/.../validate-wp6.ps1` -- WP6统一门；编排锁、测试、契约、治理、安全负例。

## Tasks & Acceptance

**Execution:**
- [x] 建立安全Git allowlist与`.gitignore`，初始化空远端所需元数据，禁止大文件/凭据/绝对路径。
- [x] 升级方法观测schema与唯一诊断合同registry，提供各方法正例和逐字段负例。
- [x] 升级能力schema/矩阵，实施成熟度—证据—claim状态机。
- [x] 发布evidence-run v2及语义验证器，创建活动v1可达集和非破坏性sidecar/Legacy索引。
- [x] 固定Python、uv和跨平台锁；统一README与CI安装测试命令。
- [x] 建立Ubuntu/Windows required matrix、merge_group门、main最终evidence-root和OIDC证明。
- [x] 实施独立SID/UID stage边界、引用保护GC、30天/20GiB策略与故障注入。
- [x] 修正58/59快照记录，生成WP6签核模板、执行日志和最终根哈希。
- [x] 初始化并推送GitHub仓库；配置可用的ruleset/required checks并保存真实Actions/attestation证据。

**Acceptance Criteria:**
- Given Python 3.11.15空环境，when执行冻结安装和统一验证，then Ubuntu与Windows均通过。
- Given任何单测、契约、治理或锁失败，when运行CI，then required check非零且不发布证据。
- Given不存在实现或证据不足，when申请能力升级或高等级claim，then验证器拒绝。
- Given运行包缺WP6关键字段或字段矛盾，when验证v2，then schema/语义门拒绝。
- Given被篡改的代码、输入、配置、输出、环境或证明，when验证根，then结果失败。
- Givenworker越权或GC目标受保护/越界/为链接，when执行操作，then不修改正式版本。
- Given三个责任角色未全部批准或外部attestation未验证，when更新状态，then WP6不得标记Done。

## Spec Change Log

- 2026-07-24：GitHub Free个人私有仓库拒绝原生artifact attestation，保持私有约束不变，外部锚改为GitHub OIDC + Sigstore Fulcio/Rekor；branch protection的403平台限制登记为延后项。
- 2026-07-24：仓库公开并启用main保护；架构、工程、QA三项明确标注为AI的独立技术复审均批准提交`d417ed9d799c40eaff7b71222129f5bca94b2bf7`。签署不冒充自然人，且不外推为生产、现场、法规或资源量认证。

## Design Notes

GitHub PR/merge_group验证候选合并内容；最终`push main`为最终commit生成证明。合并后的证明失败不能回滚提交，但必须阻止证据发布、能力升级和WP6签核。Hosted runner只验证SID/UID/ACL机制；实际worker启动时必须自行验证不同身份和权限边界。

v1从不原地迁移。可恢复全部必填事实时创建绑定原根的v2 sidecar；否则写入Legacy-frozen索引。GC保护集由active pointer、manifest、claim、签核、迁移envelope及attestation的传递闭包生成。

## Verification

**Commands:**
- `uv sync --frozen --extra dev` -- 空环境安装且不改锁。
- `uv run --frozen pytest -q` -- 全量单元测试通过。
- `pwsh -NoProfile -File "<research-root>/validate-wp6.ps1" -SelfTest` -- 正例与故障注入全部通过。
- `git diff --cached --check`及提交allowlist验证 -- 无大文件、凭据、绝对路径和排除目录。
- `cosign verify-blob evidence-root.json --bundle evidence-root.sigstore.json --certificate-identity "<main-workflow-identity>" --certificate-oidc-issuer "https://token.actions.githubusercontent.com"` -- 私有个人仓库通过Fulcio/Rekor验证最终远端证明。

## Suggested Review Order

**契约与失效关闭**

- 从统一入口理解WP6的schema、语义和故障注入门。
  [`validate_contracts.py:175`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/contracts/validate_contracts.py#L175)

- 运行证据的时间、退出码、随机性、哈希和claim一致性在此收口。
  [`validate_contracts.py:71`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/contracts/validate_contracts.py#L71)

**治理与证明边界**

- 历史索引只接受研究根内、存在且哈希冻结的文件。
  [`wp6_governance.py:63`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/contracts/wp6_governance.py#L63)

- GC按引用保护、保留期和最小配额回收生成候选。
  [`wp6_governance.py:99`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/contracts/wp6_governance.py#L99)

- 最终证据根绑定受控路径、文件哈希与最终commit。
  [`wp6_governance.py:139`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/contracts/wp6_governance.py#L139)

**CI与外部锚**

- 双平台required门覆盖锁、测试、契约与身份隔离。
  [`ci.yml:20`](../../.github/workflows/ci.yml#L20)

- main提交通过后才生成并验证GitHub OIDC证明。
  [`ci.yml:75`](../../.github/workflows/ci.yml#L75)

**回归与环境**

- 配额回收与路径逃逸均有直接故障注入。
  [`test_wp6_contracts.py:131`](../../tests/governance/test_wp6_contracts.py#L131)

- Python与uv版本共同约束可复现安装边界。
  [`pyproject.toml:12`](../../pyproject.toml#L12)
