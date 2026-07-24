---
title: '逐项整改验收审查意见01'
type: 'refactor'
created: '2026-07-17'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'NO_VCS'
context:
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/验收审查意见01.md'
  - '{project-root}/_bmad-output/planning-artifacts/research/open-data/README.md'
  - '{project-root}/_bmad-output/planning-artifacts/research/open-data/00_catalog/open_geophysics_data_manifest.json'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-revise-bayesian-fusion-review01.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-revise-appendices-version-governance.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 首轮文档整改完成了关键纠错和证据降级，但验收仍发现概率模型表达不一致、耦合不可明确关闭、契约不可执行、历史版本未物理归档、残留成果化语气及治理脚本覆盖不足；实现与实测证据仍为空。

**Approach:** 对14项发现逐一闭环：修正文稿与命名，建立机器可读契约、能力矩阵和增强治理校验；利用`research/open-data`中的公开重力、磁法、DC/IP、TEM、CSAMT、MT、WFEM及DO-27合成联合反演数据执行完整性、格式、契约和可复算验证。只有实际运行且满足证据契约的项目才升级状态；没有真值或钻孔留出的公开现场数据不冒充Field-validated。

## Boundaries & Constraints

**Always:** 逐项记录整改状态与证据位置；保持canonical唯一；修改文件后同步manifest哈希和引用；契约使用SI单位和明确CRS/维度；验证直接使用`open-data`原始文件并核对来源清单SHA-256；每次运行冻结数据选择、配置、脚本、环境、时间和输出哈希；未运行项目保持`source/run: none`。

**Ask First:** 需要下载清单之外的新外部数据、产生云/GPU费用、接受登录许可条款、改变研究范围或删除历史材料时暂停确认。

**Never:** 不伪造算子实现、测试日志、Synthetic-run或Field-validated证据；不把schema/测试骨架冒充已通过工程验收；不修改原《审查意见01.md》和《验收审查意见01.md》的历史结论。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 文档可直接整改 | 残留公式、强制耦合或成果语气 | 修正为一致模型、可关闭软先验和Planned表达 | 治理脚本阻止回归 |
| 证据尚未生成 | 无代码、运行或现场数据 | 生成schema、manifest模板、测试入口和阻断状态 | 禁止证据升级 |
| 开放数据可运行 | 本地原始文件与来源manifest一致 | 执行格式/契约/统计验证并生成带哈希run包 | 缺字段、损坏或不适用时记录失败，不补值 |
| 开放现场数据无真值 | 重磁电磁观测但无钻孔留出 | 仅验证摄取、坐标、单位、质量和重采样一致性 | 不升级为Field-validated |
| 开放合成数据有真值 | DO-27合成重磁联合数据可复算 | 运行预注册恢复/校准验证并按证据决定Synthetic-run | 无可运行代码或真值契约时保持Planned |
| 历史版本并存 | archived文件位于发布目录 | 移入独立archive并更新manifest | canonical缺失或哈希不符即失败 |

</frozen-after-approval>

## Code Map

- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/00-摘要.md`至`07-结论与展望.md` -- 模型、耦合、证据语气整改。
- `_bmad-output/planning-artifacts/research/open-data/` -- 公开数据原件、来源元数据和SHA-256清单；保持只读。
- `.../contracts/` -- 概率模型、数据、算子能力及证据包机器可读契约。
- `.../validation/` -- 开放数据审计、格式/契约验证、DO-27合成验证、场数据质量验证及其运行包。
- `.../archive/`、`manifest.yaml`、`evidence-status.md` -- 物理归档和发布治理。
- `.../validate-governance.ps1` -- canonical引用、禁用语、证据/run、Observed和参考文献重复校验。

## Tasks & Acceptance

**Execution:**
- [x] 正文和附录 -- 统一首次联合后验、明确`\lambda=0`关闭与空间掩膜、补三模型消融，并清理成果化残留。
- [x] 三个误导性文件 -- 重命名为方案/计划并更新全目录引用、manifest与哈希。
- [x] `contracts/` -- 增加可机器解析的模型、数据和算子能力schema及有效/无效样例。
- [x] `open-data`完整性审计 -- 校验两个来源manifest所列本地文件、大小和SHA-256，分类完整、部分镜像、metadata-only和不可用数据集。
- [x] `validation/` -- 实现Python可运行的开放数据验证入口；覆盖重磁CSV/GXF、MT EDI、DC/IP压缩包、TEM、CSAMT、WFEM文本的存在性、可读性、元数据和数值有限性检查。
- [x] DO-27合成数据 -- 解包并识别真值、观测与配置；当前环境缺少SimPEG/discretize，形成可复现阻断报告并保持Planned。
- [x] 公开现场数据 -- 对同源Mountain Pass重力/磁法及可用电磁数据执行摄取与数据质量验证；仅形成`Open-data-run`支撑证据，不升级为Field-validated。
- [x] `archive/` -- 移入历史版本，确保发布根目录只保留canonical。
- [x] `validate-governance.ps1` -- 扩展验收规则并运行回归。
- [x] `整改落实报告01.md` -- 将14项发现逐项映射为已完成、待运行或待现场验证及证据路径。

**Acceptance Criteria:**
- Given canonical文稿，when 运行治理校验，then 无首次模型矛盾、强制耦合和未限定成果语气。
- Given契约和样例，when 执行校验，then 合法样例通过、缺字段或非法证据升级失败。
- Given`open-data`来源清单，when运行完整性审计，then逐文件报告存在性、字节数和SHA-256，任何不一致均阻止相应数据进入验证。
- Given至少五类可用地球物理数据，when运行验证入口，then产生机器可读结果、异常计数、输入/脚本/输出哈希和明确的数据适用边界。
- GivenDO-27合成数据，when具备真值与可运行反演入口，then报告恢复误差、预测残差、重复种子和校准指标；否则输出可复现阻断原因而非伪结果。
- Given公开现场数据缺少钻孔留出，when写回证据状态，then不得标记`Field-validated`或发布命中率。
- Given发布目录，when 核查manifest与文件树，then archived文件物理隔离且所有canonical哈希一致。
- Given无实际运行数据，when检查证据登记，then所有需实测项仍为Planned/Hypothesis且不产生伪Observed结果。

## Spec Change Log

## Design Notes

“逐一整改”区分三种闭环：文档/治理缺陷立即修复；本地开放数据可支持的完整性、摄取、质量和合成真值验证实际运行并形成证据；仍需专用反演代码、算力或钻孔留出的条件保持未完成并硬阻断证据升级。公开场数据验证不等于真实矿区钻孔留出验证。

## Verification

**Commands:**
- `& .\validate-governance.ps1` -- canonical、哈希、引用、术语、证据和契约校验全部通过。
- `py .\validation\validate_open_data.py --open-data-root ..\open-data --output-root .\validation --run-id <run-id>` -- 来源清单完整性和多格式数据检查通过或生成逐项失败报告。
- PowerShell解析contracts与validation样例 -- 合法样例通过，预设非法样例被拒绝。
- `rg`审计残留表达和旧文件名 -- 仅允许在历史审查记录或archive中出现。

## Suggested Review Order

**整改总览**

- 先核对14项发现的完成、阻断与证据边界。
  [`整改落实报告01.md:5`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/整改落实报告01.md#L5)

**开放数据验证**

- 主入口冻结605个清单文件及八类选定输入。
  [`validate_open_data.py:177`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/validate_open_data.py#L177)

- ZIP成员执行非空、格式标记和样本数值检查。
  [`validate_open_data.py:110`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/validate_open_data.py#L110)

- DO-27区分资产通过与反演运行阻断。
  [`validate_open_data.py:137`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/validate_open_data.py#L137)

**证据升级门禁**

- Synthetic与Field状态要求审批、全检查和真值/钻孔条件。
  [`evidence-run.schema.json:29`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/contracts/evidence-run.schema.json#L29)

- 治理脚本复核归档、run哈希、DO-27阻断和契约反例。
  [`validate-governance.ps1:117`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-governance.ps1#L117)

**理论与验证设计**

- 首次联合后验直接纳入共享误差与模型差异。
  [`02-全方法深度融合的底层逻辑与理论总纲.md:304`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/02-全方法深度融合的底层逻辑与理论总纲.md#L304)

- 软耦合通过lambda或空间掩膜明确关闭。
  [`02-全方法深度融合的底层逻辑与理论总纲.md:453`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/02-全方法深度融合的底层逻辑与理论总纲.md#L453)

- 合成方案预注册独立、结构和岩石物理三模型比较。
  [`06-合成数据验证方案与验收设计.md:90`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/06-合成数据验证方案与验收设计.md#L90)

