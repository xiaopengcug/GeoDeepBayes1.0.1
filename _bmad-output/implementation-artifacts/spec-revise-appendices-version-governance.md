---
title: '整改附录并建立文档版本治理'
type: 'refactor'
created: '2026-07-16'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'NO_VCS'
context:
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/审查意见01.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-revise-bayesian-fusion-review01.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 附录1—14仍存在物性、资源量、统计术语、算法配置、物理公式和占位成果问题；附录7、参考文献及算力说明多版本并存，发布入口不唯一。

**Approach:** 先按已修正文统一附录内容和证据状态，再用manifest声明canonical/archived关系，建立证据登记并重建引用派生索引。

## Boundaries & Constraints

**Always:** 仅修改目标技术体系目录及本规格；附录术语与正文00—07一致；未实测数字标Hypothesis/Planned；canonical选择为附录7专家评审完善版、参考文献更新版、无后缀算力说明。

**Ask First:** 需要移动、删除、重命名文件，或发现canonical候选无法修复时暂停确认。

**Never:** 不伪造实验、矿区、财务或引用证据；不把物探概率直接称资源量；不让archived文件进入发布集合。

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| 历史版本并存 | 同一逻辑文档多文件 | manifest唯一canonical并保留归档 | 不移动或删除 |
| 主张无证据 | 性能、收益或案例数字 | 登记Planned及回写条件 | 不补造结果 |

</frozen-after-approval>

## Code Map

- `../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录*.md` -- 附录整改范围。
- `../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/参考文献*.md`、`贝叶斯三维反演测试算力需求说明*.md` -- 版本治理对象。
- `../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/manifest.yaml`、`evidence-status.md`、`cited_refs.txt` -- 发布与证据治理。

## Tasks & Acceptance

**Execution:**
- [x] `附录1`—`附录5` -- 修正硫化物/卤水/LogN、资源量边界、KL/EIG、算法配置、基准和矿区验证状态。
- [x] `附录6`—`附录14` -- 降级申报商业主张，修正重力/TEM、CRS/PPC、资源分类、LogN和先验更新。
- [x] `贝叶斯三维反演测试算力需求说明.md` -- 改为Planned benchmark矩阵，补可复算任务字段。
- [x] `manifest.yaml`、`evidence-status.md`、`cited_refs.txt` -- 声明发布集合、登记主张、重建有效引用索引。

**Acceptance Criteria:**
- Given 附录全集，when 检索资源量、LogN、置信区间、性能和成果语气，then 每项均符合正文术语、证据状态及合规边界。
- Given 文档族，when 解析manifest，then 每族恰有一个canonical，所有路径存在、哈希完整且archived不在发布集合。
- Given 引用索引，when 与canonical参考文献核对，then 无0、2700、3300等代码误捕且编号均存在。
- Given evidence-status，when 抽查性能、案例、经济和成果主张，then 均有位置、状态、验证条件和回写目标。

## Spec Change Log

## Design Notes

不移动历史文件；发布状态由manifest控制。先完成内容整改，最后计算SHA-256，避免治理元数据失效。

## Verification

- `rg`术语与证据状态审计 -- 无未限定残留。
- PowerShell解析manifest路径、唯一性和SHA-256 -- 全部通过。
- Markdown围栏与公式定界符检查 -- 全部成对。

## Suggested Review Order

**发布与版本治理**

- 从唯一发布入口理解canonical、archived及派生文件边界。
  [`manifest.yaml:58`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/manifest.yaml#L58)

- 证据状态与字段级锚点约束数值主张升级。
  [`evidence-status.md:24`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/evidence-status.md#L24)

**关键理论与数据契约**

- 完整CRS和PPC结构保证概率立方体可复现。
  [`附录12-全深度概率立方体可视化工具.md:165`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录12-全深度概率立方体可视化工具.md#L165)

**持久验证**

- 自动核验哈希、发布互斥、引用、证据字段和Markdown结构。
  [`validate-governance.ps1:1`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-governance.ps1#L1)
