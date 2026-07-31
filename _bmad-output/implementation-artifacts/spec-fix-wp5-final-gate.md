---
title: '修复 WP5 最终门并重新确认活动根'
type: 'bugfix'
created: '2026-07-28'
status: 'in-review'
review_loop_iteration: 2
baseline_commit: '3335c1e1b29a5e75e38aac18218c3fe226807463'
context:
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/验收审查意见03.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-wp5-align-manuscript-and-appendices.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** WP5 活动 pointer 与 manifest 已一致，但证据根仍冻结修正前的 `ACTIVE_MANIFEST` 文件哈希，导致 Windows 正确 fail-closed；validator 另有三处 Windows 分隔符硬编码，使 Ubuntu 在合法路径上更早误报。旧六角色 PASS 绑定旧根，不能机械平移为新确认。

**Approach:** 保持已通过的 WP5 版本、scan 与科学证据不可变，修复跨平台路径门，生成新候选根；六个独立 AI 审查角色分别复核同一候选根并形成可审计记录，全部通过后才派生汇总签核。用户选择 `[A] Approve` 即明确授权本轮六角色 AI 重新审查并签署候选根，但不构成自然人、外部资质或法定签章。

## Boundaries & Constraints

**Always:** pytest/governance 前置门保证 pointer、manifest、`ACTIVE_MANIFEST`、run ID 精确一致；WP5 validator 逐成员重算候选根；六角色记录使用 exact 角色集、自动化 AI 身份、同一 run/manifest/member-root/root-file-root，并绑定本规格获批后的冻结意图块；先使 `-SkipSignoff` 通过，再允许生成汇总 PASS。

**Ask First:** 若需修改 16+1 文稿、ledger、scope/risk registry、重新发布 WP5 版本、改变签核范围/身份类型，或合并受保护 `main` 以生成最终 Sigstore/Rekor attestation，必须另行批准。

**Never:** 不使用 `rebind-*.ps1` 机械改四个哈希冒充确认；不绕过 root、anchor、signoff 或分支保护；不把 AI 审查写成人类专家；不暂存用户无关修改。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| 合法路径 | Windows 或 Linux 下 root 内成员 | 原生相对路径判定为 contained | 任一逃逸或同名前缀兄弟路径均拒绝 |
| 候选根 | 当前活动 manifest 与 29 个 exact 成员 | 确定性生成新 member/root-file hash | 成员漂移时禁止签核 |
| 六角色确认 | 六个唯一 AI 角色绑定同一候选根 | reviews manifest 与汇总签核可验证 | 缺失、重复、拒绝、陈旧或无授权均 fail-closed |
| 跨平台门 | clean checkout | Ubuntu/Windows 默认 WP5 均返回 0 | stderr 进入公开 CI annotation |

</frozen-after-approval>

<approved-scope-amendment round="2" reason="user-authorized expansion after first review">

## Round-2 Scope Amendment

首轮审查后，用户已明确回答“是”，授权修改受控16+1文稿、claim ledger、scope/risk registry并重新发布WP5；该授权也覆盖为这些修改重建候选根、七阶段证据和六角色自动化AI复核。它不授权把旧候选或旧review机械平移为新结论，不授权冒充自然人签署，也不授权绕过分支保护或提前宣称远程attestation。

### 版本迁移

任何受控成员、validator、fixture manifest或授权绑定发生变化，现有活动版本即成为历史候选。迁移必须按“修文与治理源 → 不可变新版本及manifest/scan → 活动pointer与`ACTIVE_MANIFEST` → 29成员根与anchor → 七阶段release envelope → 六角色review → reviews manifest → 派生汇总签核 → 默认门”的顺序完成；任何下游产物不得反向修改其已绑定的上游对象。

### 29成员权威枚举

成员集合为下列exact有序清单，不得用glob、目录扫描或“16+1”文字推断替代：

1. `00-摘要.md`
2. `01-引言.md`
3. `02-全方法深度融合的底层逻辑与理论总纲.md`
4. `03-多方法深度融合的核心技术实现路径.md`
5. `04-分场景多方法融合适配方案.md`
6. `05-工程化落地与效率优化方案.md`
7. `06-合成数据验证方案与验收设计.md`
8. `07-结论与展望.md`
9. `附录1-分矿种多方法融合定制化勘查模板.md`
10. `附录2-概率化反演结果应用规范与风险管控准则.md`
11. `附录3-算法选型与多方法组合决策树.md`
12. `附录4-核心算法性能基准测试计划与验收指标.md`
13. `附录5-真实矿区验证方案.md`
14. `附录11-分勘查阶段标准化操作手册.md`
15. `附录13-岩性物性参数统计数据库.md`
16. `附录14-地质先验知识库.md`
17. `贝叶斯三维反演测试算力需求说明.md`
18. `validation/wp5-consistency/consistency-contract.json`
19. `validation/wp5-consistency/claim-ledger.json`
20. `validation/wp5-consistency/previous-claim-ledger.json`
21. `WP5-upstream-allowlist.json`
22. `validation/wp5-consistency/scope-registry.json`
23. `validation/wp5-consistency/high-risk-classification.json`
24. `validation/wp5-consistency/selftest-fixture-manifest.json`
25. `validation/wp5-consistency/run-selftest-evidence.ps1`
26. `validation/wp5-consistency/finalize-selftest-stage-evidence.ps1`
27. `validation/wp5-consistency/publish-wp5-consistency.ps1`
28. `validate-wp5.ps1`
29. `ACTIVE_MANIFEST`

### 绑定与独立性操作定义

- **Binding order：** 活动pointer的run/version/manifest、磁盘manifest哈希及`ACTIVE_MANIFEST`内容先一致；随后逐项复算29成员、member root、root-file hash与anchor；七个stage runner再绑定同一run/manifest、validator与fixture manifest；envelope只收录路径、哈希和计数均已核验的stage结果。
- **Self-reference：** `final-root-reviews-v1/`、reviews manifest、release envelope及汇总签核不进入其所确认的29成员根。review绑定候选根与envelope，reviews manifest绑定六份review，汇总签核再绑定reviews manifest，禁止任何对象直接或间接把自身哈希纳入自身输入。
- **Stale：** run、version path、manifest、29个成员任一哈希、member/root-file、anchor、validator、fixture manifest、envelope、原冻结块、Round-2 amendment或review文件任一不匹配，均使相关review与汇总立即陈旧；陈旧记录只能保留为历史，不得改四个哈希后复用。
- **AI独立性：** 六个exact角色分别从同一只读候选根和envelope开始复核；每个角色仅生成自己的role/scope、至少三条非空且不重复的checks、decision与findings，不读取或复制其他角色的decision作为依据，也不在复核期间修改候选。身份统一为`automated-ai-final-root-review`，并明确不是自然人、外部资质或法定签章。
- **Runner判据：** “300项通过”表示七个stage runner各自退出0，且每个fixture的`actual_exit`符合预声明`expected_exit`：正例为0，负例按预期非零并命中预声明拒绝原因；不得把所有负例描述成子进程退出0。
- **Remote pending：** 本地门、历史PR或旧提交不能证明本次迁移后的候选。只有包含上述exact状态的提交在Ubuntu/Windows clean checkout required gates均返回0，才可记录双平台通过；Sigstore/Rekor仍须等待受保护`main`上的实际workflow签发。完成前规格保持`in-review`。

</approved-scope-amendment>

## Code Map

- `03-多方法深度融合的核心技术实现路径.md`、claim ledger及lineage/registry -- 修正thin-SVD/POD证明并使正文、主张、迁移和风险分类同版本闭合。
- `validation/wp5-consistency/publish-wp5-consistency.ps1`、活动版本`manifest.json/scan.json`、`active-output.json`与`ACTIVE_MANIFEST` -- 生成不可变新版本并按顺序迁移活动指针；旧版本只读保留。
- `WP5-consistency-input-root.sha256`、`validation/wp5-consistency/WP5-consistency-root-anchor.sha256` -- 只按Round-2块列出的29成员exact有序集合确定性重建。
- `validation/wp5-consistency/run-selftest-evidence.ps1`、`finalize-selftest-stage-evidence.ps1`、`release-evidence-v1/` -- 保存七个stage runner的整体退出状态、fixture预期/实际退出状态、拒绝原因、路径和哈希。
- `validation/wp5-consistency/final-root-reviews-v1/`、`WP5-主编技术编辑与专项交叉复核独立签核.md` -- 按无自引用单向链绑定原冻结块、Round-2 amendment、候选根、envelope、六份独立review及派生汇总。
- `validate-wp5.ps1` -- fail-closed验证版本迁移、29成员、双授权块、七阶段结果、陈旧/自引用边界及六角色操作合同。
- `.github/workflows/ci.yml`、`validation/wp9/build_persistence_plan.py`、WP9 manifest与验收文档 -- 在最终文档冻结后重建持久化闭包，远程Ubuntu/Windows结果保持pending直至新提交实跑。

## Tasks & Acceptance

**Execution:**
- [x] 用户Round-2授权与科学文稿 -- 保持原冻结块字节不变，以唯一可哈希amendment记录用户已批准的16+1/ledger/registry/重新发布范围，并修正thin-SVD/POD证明。
- [x] 正文治理源与不可变版本 -- 重算受影响claim/lineage/registry，发布新manifest/scan并原子迁移pointer与`ACTIVE_MANIFEST`；不得复用变更前候选。
- [x] 29成员根与七阶段证据 -- 按权威有序枚举重建双root/anchor；七个stage runner均须退出0，所有正负fixture须分别满足预声明退出与拒绝原因。
- [x] 六角色与默认门 -- 六个独立自动化AI角色绑定双授权块、同一新根和新envelope；reviews manifest与汇总按单向链派生，默认门随后返回0。
- [x] WP9闭包与定向回归 -- 最终文档冻结后重建WP9 manifest/persistence closure并重跑治理与WP9定向测试；旧`43 passed`仅为当时结果。
- [ ] 远程证明 -- 精确提交required资产，在Ubuntu/Windows clean checkout重跑required gates；受保护main的attestation继续pending。

**Acceptance Criteria:**
- Given原冻结块和Round-2 amendment，when按UTF-8、LF归一化和inclusive标签分别计算哈希，then两块均唯一，原冻结块SHA-256为`fa604cd725d60848582aadde023b308c117a515e4c5e9d88b6f826da68c43748`，amendment SHA-256仍为`126c5dce324f4ef6959b56291b778b10967b6f62134483b62e54b6f2b9f9b1f1`。
- Given任一受控成员已修改，when启动版本迁移，then旧run/root/envelope/review保持历史且不能平移；新pointer、manifest、`ACTIVE_MANIFEST`、29成员、双root与anchor全部精确一致后，`-SkipSignoff`才可返回0。
- Given任何root-relative输入路径，when做包含性判定，then合法子路径和解析后仍在root内的链接可接受，`..`逃逸、同名前缀兄弟目录和解析后逃逸的链接必须拒绝；`allowlist/contained-path` stage子用例与具名pytest路径逃逸用例共同覆盖该合同。
- Given七阶段fixture manifest，when分别运行stage runner，then七个runner均退出0，正例`actual_exit=0`，负例`actual_exit`按预声明非零且命中exact拒绝原因，ID集合无缺失、重复或跨stage错配。
- Given六个exact AI角色，when独立复核同一只读候选，then每条记录具有唯一role/scope、至少三条独立checks、显式decision/findings、双授权块和同一candidate/envelope绑定；缺失、复制、拒绝、陈旧、身份误标或自引用均fail-closed。
- Given最终验收文档和WP9 manifest已冻结，when运行WP9 publish/audit、manifest closure与定向回归，then均返回0且输出计数以本次实跑为准，不沿用旧`43 passed`。
- Given包含上述状态的提交，when先验证该提交的head closure并在clean checkout运行required gates，then所需路径均以当前内容持久化且Ubuntu/Windows的WP5—WP9与平台隔离全部返回0；在取得对应run前remote保持pending，attestation只按受保护main条件成立。

## Spec Change Log

- 2026-07-29：首轮六角色独立复核结果为主编/地球物理 Approved，技术编辑、贝叶斯/UQ、算法数值、工程架构 Rejected。用户明确回答“是”，授权按 Ask First 边界修改 16+1 文稿、claim ledger/血缘并重新发布 WP5；旧候选根及其复核记录不得平移，修复后重新生成候选根并执行六角色复核。
- 2026-07-30：Round-2审查发现thin-SVD/POD证明、版本迁移、29成员枚举、绑定顺序、自引用、陈旧判定、AI独立性和远程状态仍需操作化。新增唯一授权amendment；规格保持`in-review`，所有变更后证据须重新生成。
- 2026-07-30：算法数值复核拒绝了中间候选，指出thin-SVD完备正交分解和RJMCMC Green接受率虽已写入正文，但缺少覆盖完整公式段的专属语义守卫与负向变异。按“不defer”要求，复用既有fixture槽位补入两项不可变oracle，保留原POD秩亏负例，并将两个低信息ledger记录重绑定到完整多行规范；旧中间候选及其300项证据作废。
- 2026-07-30：最终新候选`20260730T200104829Z-cc929856f1df4bb28e90aa8b51703e07`已闭合29成员双根、七阶段300/300正式证据、每份review独立绑定release envelope的六个exact自动化AI角色及默认WP5门；`-SkipSignoff`与默认门均真实验证双授权、完整七阶段信封和派生签核。WP9须以本候选和最终验收文档重新发布；远程证明在提交后clean-checkout实跑前继续保持未勾选。
- 2026-07-30：WP9四专项证据已从上述最终状态重发为4/4 Approved、60/60覆盖，manifest audit与replay返回0；治理、WP9、oracle及Windows长路径head-closure回归为`61 passed`。持久化计划闭包为36个manifest成员、699个附加控制输入、732个required Git路径、3个CI确定性再生制品，`required_but_ignored_unresolved=0`；提交后的head closure必须为passed。远程项目继续等待提交后的clean-checkout实跑。

## Design Notes

29成员的纳入准则是“本轮获授权的16篇`consistency-contract.documents`正文 + 1篇算力说明 + 12个决定语义、血缘、活动版本和可重放验证行为的治理/执行控制”。附录6—10及附录12不在获授权的16篇exact文稿集合和`consistency-contract.documents`中，也不是本轮治理/执行控制，因此不纳入；review、reviews manifest、release envelope、汇总签核和验收报告是29成员根的下游证明，也因避免自引用而不纳入。

新review记录、reviews manifest、release envelope和汇总签核不得进入其所签署的29成员根，以避免自引用。validator须分别验证原冻结块与Round-2 amendment的规范化哈希，再按amendment规定的单向顺序验证candidate、envelope、reviews manifest和汇总；这些哈希证明内容完整性与绑定关系，不构成密码学用户签名。

checks判重以每份review内的规范化完整字符串为第一层，同一record内不得重复；跨角色允许因共同候选绑定而出现局部证据重叠，但六个角色的规范化完整checks集合不得全量相同。跨角色全量复制由`test_wp5_final_review_check_sets_are_role_distinct`检测；独立性仍由唯一review ID、exact role、role-specific scope、各自checks/findings及不读取其他角色decision共同定义，而不是用文字表面差异冒充独立结论。

## Verification

**Commands:**
- 独立计算`frozen-after-approval`块与`approved-scope-amendment round=2`块的UTF-8/LF/inclusive SHA-256；必须分别为`fa604cd725d60848582aadde023b308c117a515e4c5e9d88b6f826da68c43748`与`126c5dce324f4ef6959b56291b778b10967b6f62134483b62e54b6f2b9f9b1f1`。
- `pwsh -NoProfile -File ".../validate-wp5.ps1" -SemanticOnly` -- 新正文、ledger与registry闭合后验证语义核。
- `pwsh -NoProfile -File ".../validate-wp5.ps1" -SkipSignoff` -- 新版本、29成员、双root、双授权块和七阶段envelope闭合后验证根链。
- `pwsh -NoProfile -File ".../validate-wp5.ps1" -SelfTest -SelfTestStage allowlist` -- 重放具名`contained-path`子用例，覆盖合法子路径、同名前缀兄弟、`..`及解析链接边界；`pytest ...::test_fixed_point_reference_closure_fails_closed ...::test_persistence_plan_rejects_path_escape`补充仓库级逃逸拒绝。
- 分别运行七个`run-selftest-evidence.ps1 -Stage <stage>`；验收stage runner整体exit 0，并解析每个fixture的`expected_exit/actual_exit/actual_rejection/matched`，不得用“300个子进程均退出0”替代。
- `pwsh -NoProfile -File ".../validate-wp5.ps1"` -- 六角色新review及派生汇总完成后验证默认门；旧review不得复用。
- `uv run --frozen pytest -q tests/validation/test_acceptance_review03_governance.py tests/validation/test_wp9_acceptance.py` -- 最终文档与WP9 manifest冻结后重跑，记录本次实际计数和退出码。
- `uv run --frozen python validation/wp9/run_specialist_reviews.py`及`uv run --frozen python validation/wp9/validate_wp9.py --publish` -- 必须得到4/4 Approved、60/60覆盖、audit=`passed`、manifest replay=`true`。
- `uv run --frozen python validation/wp9/build_persistence_plan.py` -- 提交前manifest closure和本地准备必须通过；提交后再以`--verify-head-closure`验证最终required Git闭包返回0且未持久化项为0。
- 远程required-gates run必须同时给出绑定同一提交的Ubuntu与Windows job URL/ID、结论和完整失败输出；在实跑前只记录`pending`，不得预写PASS或attestation。
