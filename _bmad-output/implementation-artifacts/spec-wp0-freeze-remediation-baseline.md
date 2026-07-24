---
title: 'WP0：冻结整改基线与建立主张—证据治理'
type: 'chore'
created: '2026-07-17'
status: 'done'
review_loop_iteration: 2
baseline_commit: 'NO_VCS'
context:
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/审查意见03.md'
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/修改计划03.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 《审查意见03》确认当前文稿、工程能力和证据等级之间存在系统性错配，且整改尚无稳定问题ID、冻结基线或主张—证据约束，后续修改容易出现漂移、重复闭环和证据外推。

**Approach:** 完成WP0治理基线：冻结审查范围内文件哈希，建立可追踪整改台账和主张—证据映射，生成证据状态调整草案及禁用/降级主张清单，并把执行日志推进到WP0检查点。

## Boundaries & Constraints

**Always:** 仅记录当前事实；所有哈希由实际文件计算；问题必须可追溯到《审查意见03》；保留已有文件和运行包；主张允许范围不得高于证据等级；输出使用简体中文。

**Ask First:** 若需要修改00—07章、附录、源码、契约正式内容或`evidence-status.md`现行状态，必须先获得用户对下一工作包的授权；若发现基线文件不可读或同一主张无法确定唯一证据边界，应停止并报告。

**Never:** 不在WP0修改理论公式、工程代码或正式证据状态；不运行高成本实验；不把Planned升级为Synthetic-run或Field-validated；不以新修订注掩盖原错误；不伪造责任人、审批、哈希或运行结果。

## I/O & Edge-Case Matrix

| 场景 | 输入 / 状态 | 预期输出 / 行为 | 错误处理 |
|---|---|---|---|
| 正常基线 | 目标文件存在且可读 | 写入相对路径、类别、SHA-256、大小和冻结时间 | 无 |
| 文件缺失 | manifest或计划范围中的文件不存在 | 台账标记Blocked，不生成虚假哈希 | 列出缺失路径 |
| 历史主张无证据 | 成果语句找不到支持Evidence ID | 映射为禁止或仅Planned | 记录原文件和定位 |
| 证据范围冲突 | Synthetic-run被用于现场/全方法结论 | 明确允许与禁止主张 | 标记P0治理问题 |

</frozen-after-approval>

## Code Map

- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/审查意见03.md` -- 问题、等级和复审门槛来源。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/修改计划03.md` -- WP0范围、交付物和退出条件。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/evidence-status.md` -- 当前证据状态与允许升级条件。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/manifest.yaml` -- 当前发布集和既有哈希治理。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/修改计划03-执行日志.md` -- 工作包状态和交接记录。

## Tasks & Acceptance

**Execution:**
- [x] `整改台账03.md` -- 为《审查意见03》每个源问题建立稳定`source_finding_id`，明确一对多拆分依据，并记录精确来源锚点、等级、责任角色、规范化计划证据路径、验证人和状态。
- [x] `主张-证据映射03.md`与`主张扫描03.csv` -- 建立证据规则、完整Evidence ID对账、证据前提审计、禁用/降级主张以及每个扫描命中的结构化处置；正文降级明确留给WP5。
- [x] `基线冻结03-inventory.csv`与`基线冻结03.sha256` -- 从批准的递归范围和显式排除规则生成清单，记录相对路径、类别、大小、UTC冻结时间、状态和实际SHA-256；缺失项标记并阻断，禁止静默选集。
- [x] `evidence-status-03草案.md` -- 完整复制现行证据登记的全部字段和锚点，在副本上标注逐字段建议差异，不覆盖正式登记。
- [x] `validate-wp0.ps1` -- 专门验证冻结范围/哈希/路径唯一性、台账来源覆盖、Evidence ID集合、主张扫描映射、草案完整副本和正式登记未变；失败返回非零。
- [x] `修改计划03-执行日志.md` -- 按日期、责任人、交付物路径、命令和结果记录状态转换及下一工作包条件。

**Acceptance Criteria:**
- Given《审查意见03》，when检查整改台账，then每个P0/P1问题均有稳定ID、来源定位和非空责任角色。
- Given冻结范围，when重新计算SHA-256，then清单中每个已存在文件的摘要与磁盘内容一致，缺失项明确标记。
- Given现有Evidence ID，when检查主张映射，then每项允许主张均不超过证据状态，Synthetic-run不能支持现场有效性或完整五方法能力。
- GivenWP0不含正文整改，when比较目标文稿和源码，then除新增治理文件及执行日志外无内容修改。
- Given治理脚本，when执行验证，then现有release治理继续通过。
- Given WP0新增产物，when执行`validate-wp0.ps1`，then所有结构、集合、哈希和跨文件约束通过；任一遗漏或篡改均返回非零。

## Spec Change Log

- 2026-07-17 / review loop 2：三层复核发现第一轮规格允许人工选集、代表性扫描、摘要式证据草案和无关治理PASS冒充WP0验收。新增完整递归范围与显式排除、库存元数据、源问题主键交叉表、全量主张扫描、正式证据完整副本和专用验证器。KEEP：保留真实计算哈希、正式`evidence-status.md`不变、正文不在WP0修改、Synthetic-run不得外推。用户已裁决WP0为治理基线，正文全局降级移入WP5。
## Design Notes

冻结范围包括：00—07章、全部规范附录、参考文献、算力说明、正式证据与治理文件、`src/**/*.py`、`tests/**/*.py`、`contracts/**/*.{json,py}`和`validation/runs/**/*`。排除：archive、validation/do27/source与work、缓存、审查/计划/WP0新增产物。库存先生成，哈希文件由库存中`status=present`行派生；新增治理产物不纳入冻结输入，避免自引用。证据状态草案必须醒目标注“非权威、待复核”，正式`evidence-status.md`保持不变。

## Verification

**Commands:**
- `Get-FileHash -Algorithm SHA256 <path>` -- expected: 与`基线冻结03.sha256`对应摘要一致。
- `rg -n '理论框架自洽|支持5种方法联合|GPU加速已实现|可全面应用|可采资源量|周级缩短至小时级|1-3个数量级' <document-dir>` -- expected: 每个命中均出现在主张映射中。
- `& <document-dir>/validate-wp0.ps1` -- expected: PASS，且负向篡改测试返回非零。
- `& <document-dir>/validate-governance.ps1` -- expected: PASS。

**Manual checks:**
- 核对整改台账覆盖《审查意见03》全部P0/P1条目。
- 核对证据草案未覆盖正式`evidence-status.md`。

## Suggested Review Order

**验证入口与冻结边界**

- 先看必需发布文件和递归范围如何确定。
  [`validate-wp0.ps1:32`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-wp0.ps1#L32)

- 再看一次性生成、重基线保护和治理产物派生。
  [`validate-wp0.ps1:196`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-wp0.ps1#L196)

- 核对库存、哈希、台账、映射和正式证据的交叉验证。
  [`validate-wp0.ps1:352`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-wp0.ps1#L352)

- 检查五类真实产物篡改是否由子进程拒绝。
  [`validate-wp0.ps1:467`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-wp0.ps1#L467)

**问题与主张治理**

- 审阅60项源问题的稳定主键和责任字段。
  [`整改台账03.md:7`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/整改台账03.md#L7)

- 审阅15个Evidence ID的允许范围和禁止外推。
  [`主张-证据映射03.md:16`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/主张-证据映射03.md#L16)

- 检查WP5须处理的禁用主张和Observed规则。
  [`主张-证据映射03.md:35`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/主张-证据映射03.md#L35)

**正式证据隔离与审计**

- 确认草案只提出逐字段建议，不覆盖正式登记。
  [`evidence-status-03草案.md:58`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/evidence-status-03草案.md#L58)

- 最后核对第二轮实施命令、结果和可信正式哈希。
  [`修改计划03-执行日志.md:48`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/修改计划03-执行日志.md#L48)
