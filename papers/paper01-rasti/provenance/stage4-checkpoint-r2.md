# Stage 4 修订检查点（r2，完整性修订后）

## 结论

Stage 4 可在本地完成的 Major Revision 流程已闭合：第一轮 reviewer-roadmap 修订、第二轮 serious integrity correction、结构变更确认、最终稿锚定、清洁编辑视图、E6 语义复核、两轮连续 revision-evidence bundle、诊断回归和三条只读重放均已完成。完整性修订撤回了残留的文献元素评分及其依赖的最接近工作、空组合、缺失、优先性和差异性推论；Table 5 与 Appendix A 现在只承担 identity-verified discovery inventory 与 location-specific full-text recoding protocol 的角色。

当前状态为：**Stage 4 本地修订闭合，但投稿仍未就绪**。未从项目活动推断 Funding 或 CRediT，本文专用材料尚未推送到公共仓库，也没有 immutable release 或独立 clean-environment replay。

16 个 roadmap 项中：

- 13 项已完成；
- 2 项部分完成并依赖外部发布/独立重放：`REV-EIC-3`、`REV-R3-4`；
- 1 项等待作者事实：`REV-EIC-4`。

## 权威链

| 工件 | SHA-256 / 状态 |
|---|---|
| Integrity-PASS 基稿 | `f927ad43821883e18412aa31df1a30969935b3c1120557921499423fad4251ca` |
| Reviewer roadmap | `79fc5b93bdd61104269cb91ad0de4f59ca18540fc3a32e7bf40ae7e9f9445217` |
| Author adjudication r1 | `5635a831a02729bd4fc6c76ac07009b2ff9e01e7af9bac93761c4425b52d3689` |
| Review patch r1 | `093e497f894b7e29821b7712458e1ac7c371fe68419457da21b8476219ec656a` |
| 第一轮修订稿 | `31d3c02c53f2bb5b25e8139cda07ca36ad36a0018457766d512926efce8f1c81` |
| Integrity issue list r2 | `52220d86a6e93a9476bf140993ef42dc6320502e8c306bc30aaa6c88c1136064` |
| Integrity authorization r2 | `c60544f3f43c2c233ac210d3cc1d5b193c1487c78fff54aeb4f8e7f1ea4d2c33` |
| Integrity patch r2 | `c4ec555ec3203657a97aab62c25c06b0720623e52d898cc7735a5420d54a7e92` |
| Integrity apply report r2 | `2b69f61e51abe2b742318f3c4df4725d4e1d44806b5aba8c2d7e36d446515d69` |
| 最终锚定稿 | `59d8475d7e57506e0bb3756748a6c9ad3324684988b8d634294241a9935e3df9` |
| 最终 block manifest | `a936b3b7870200539f06677f12d53c99680317b09fa30209f3fe79e2907e8f64` |
| 清洁编辑视图 | `69c46a156109b41f1df8cbd8145932519007f3cc313d34796d06ec84bc7e8604` |
| Revision Evidence Bundle r2 | `85a0ee8695f37be4d6661c9f3c9be144449dec1e9efa807cf4c3bceac349a6fb`；WSL 回放 `revision evidence bundle ok` |

第一轮补丁应用 41 个操作，610 个基稿块中 571 个逐字节保持不变。第二轮完整性补丁应用 36 个 `replace_block` 操作，614 个块中 578 个逐字节保持不变；章节数变化为 0，触及比例为 0.0586，7 个标题操作已获独立结构确认。第二轮未登记任何 `claim_strength_changes`，也未触及注册定量主张表面。

## 最终验证结果

| 验证 | 结果 |
|---|---|
| Diagnostics / joint-block 回归 | `24 passed, 1 deselected in 15.90s` |
| EVD-JOINT-001 最终只读重放 | 65 个源文件哈希保持；`Failed -> Failed = 65`；`nonfinite_diagnostic = 65` |
| 退化通道分布 | 1 个通道：57 文件；2 个：3 文件；6 个：5 文件 |
| EVD-ALGO-002 最终只读重放 | 四项阈值通过；保守稿件值保持为 `1.00374 / 2496 / 1963 / 0.0202` |
| M2 reconstruction lineage | 42/42 行精确重建；无未绑定 run id |
| E6 语义复核 | C-001、C-007 均为 `pass_no_semantic_drift`，并绑定最终稿与 r2 apply report |
| 旧评分主张扫描 | `≈1.5`、`No row reaches`、`Elements covered`、`coverage matrix is unchanged`、`no full text was read` 及旧 Bosch 评分行均无匹配 |
| Table 5 / Appendix A | 两张表各 11 行 × 4 个元素字段均为 `unknown`；无元素计数、排序或 novelty 决策角色 |
| 清洁编辑视图 | 移除 614 个 block marker 与 212 个证据注记跨度；语义编辑为 0；无残留 `<!--block:`、`⟦` 或 `⟧` |
| Revision Evidence Bundle | 两轮连续链、自包含 15 个绑定工件；ARS 回放通过 |

最终新鲜重放输出位于 `stage4-revision/verification-final/`。其哈希分别为：joint `ab0a60fa8e1125076488cff913fed80650c337b51e32c12524b1d9ef9ab6b90b`、algorithm `7bf3aa2592815760c61e2e9688821f6b4eb5ca3c97eabfce2b8b5302e3e0fff3`、M2 `6245267e29fc6c53a59e3b59a4276bd2abfbb3699cad9ab24d17d12e452db123`。

## Roadmap 状态

| ID | 状态 | 说明 |
|---|---|---|
| REV-EIC-1 | 完成 | §8.4 压缩；最终清洁视图移除内部生产注记 |
| REV-EIC-2 | 完成 | 统一为 formulation/protocol + component-level evidence |
| REV-EIC-3 | 部分完成 | 公共 GitHub 事实已纠正；本文材料尚未推送，无 immutable release |
| REV-EIC-4 | 等待作者 | Funding 与 CRediT 不从项目记录推断 |
| REV-R1-2 | 完成 | 选择主张窄化；未新增 validation arm |
| REV-R1-3 | 完成 | Eq. (3.9) 为唯一规范；历史 additive-floor 仅作 provenance |
| REV-R1-4 | 完成 | 公式、fail-closed、回归测试及历史重放闭环 |
| REV-R1-5 | 完成 | 42/42 reconstruction lineage，明确非 runtime-generated |
| REV-R1-6 | 完成 | nominal、计数、Wilson 方法与区间齐全 |
| REV-R2-1 | 完成 | 36-block integrity correction 已获精确授权并应用；旧评分及依赖推论撤回 |
| REV-R2-2 | 完成 | 定向中文核查、元数据纠错、未解析记录边界齐全 |
| REV-R2-4 | 完成 | 九方法 method-to-latent 保守映射已加入 |
| REV-R3-1 | 完成 | specification-only decision workflow 已加入 |
| REV-R3-2 | 完成 | 环境基线与无 compute/scaling 主张边界已加入 |
| REV-R3-4 | 部分完成 | 可执行 adopter checklist 与本机 replay 已完成；独立 clean-environment replay 未完成 |
| REV-R3-5 | 完成 | 四域 field-transfer risk register 已加入 |

## 投稿阻塞项

1. 对应作者提供并确认真实 Funding 声明。
2. 作者提供并确认 CRediT taxonomy。
3. 作者决定并执行本文专用材料的公共发布，或确认与许可证和仓库事实一致的最终受限可用性声明。
4. 若要声明 external reproducibility，须针对 immutable release 完成独立 clean-environment replay；当前不得作该声明。

未执行 `git push`，也未把本文 Stage 4 材料表述为已公开、已独立复现或可直接投稿。
