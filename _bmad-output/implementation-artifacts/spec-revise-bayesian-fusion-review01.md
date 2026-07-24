---
title: '按审查意见01修订正文00—07'
type: 'refactor'
created: '2026-07-16'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'NO_VCS'
context:
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/审查意见01.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 正文存在物理概念错误、概率模型未闭合、错误公式、算法边界混用和占位结果成果化，影响理论可信度与工程可实施性。

**Approach:** 依据审查意见01修订正文00—07，统一理论、算法、工程与验证口径，并检索确认关键错误不再残留。

## Boundaries & Constraints

**Always:** 仅修改正文00—07及本规格；保留现有非目标内容；无实测依据的数字标为Hypothesis或Planned；公式修改同步核查正文引用。

**Ask First:** 删除文件、改变研究目标、增加新性能结论或修改附录、参考文献、算力说明时暂停确认。

**Never:** 不伪造实验；不把近似后验称为完整后验；不覆盖无关工作区变更。

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| 可定位问题 | 审查意见对应原文 | 修正并同步相关章节 | 复核术语与引用 |
| 缺少实测 | 仅有占位指标 | 改为Planned和验证要求 | 不补造结果 |

</frozen-after-approval>

## Code Map

- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/00-摘要.md`至`07-结论与展望.md` -- 本轮全部修改范围。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/审查意见01.md` -- 修订依据。

## Tasks & Acceptance

**Execution:**
- [x] `00`—`02` -- 修正方法分类、DOI、绝对化表述、Chib公式、共享误差概率模型、可信区间术语和采样边界。
- [x] `03` -- 替换错误POD/KL命题，补matrix-free导数、代理误差、RJMCMC和复杂度口径。
- [x] `04`—`05` -- 修正先验、Bayes factor、EIG，补算子/数据契约、精度、恢复与benchmark规范。
- [x] `06`—`07` -- 改为验证方案，拆分SBC/PPC/概率校准，降级所有未验证成果。

**Acceptance Criteria:**
- Given 正文，when 检索Chib错误式、无深度衰减、POD不劣定理、完整后验和未限定成果语气，then 无未经限定残留。
- Given 性能数字，when 核查证据，then 未实测项均标明Hypothesis或Planned及验证条件。
- Given 算法和工程章节，when 复核，then 明确Jv/Jᵀv、代理误差、算法适用范围、benchmark及恢复一致性。

## Spec Change Log

## Design Notes

修改顺序：公式与物理概念→概率模型→算法近似→工程契约→验证证据。将过程性修订注融入正式正文。

## Verification

- `rg`关键错误词和公式模式 -- 无未限定残留。
- Markdown标题、围栏和公式定界符检查 -- 结构完整。

## Suggested Review Order

**理论闭合**

- 从正确Chib恒等式和适用条件开始核查。
  [`02-全方法深度融合的底层逻辑与理论总纲.md:1495`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/02-全方法深度融合的底层逻辑与理论总纲.md#L1495)

- 共享误差、SPD协方差和logdet闭合联合似然。
  [`02-全方法深度融合的底层逻辑与理论总纲.md:320`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/02-全方法深度融合的底层逻辑与理论总纲.md#L320)

- 摘要统一生成式似然与generalized Bayes边界。
  [`00-摘要.md:35`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/00-摘要.md#L35)

**算法与近似**

- 撤销POD优越性定理并改用独立留出验证。
  [`03-多方法深度融合的核心技术实现路径.md:112`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/03-多方法深度融合的核心技术实现路径.md#L112)

- matrix-free导数与代理误差校正限定可实现路径。
  [`03-多方法深度融合的核心技术实现路径.md:1005`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/03-多方法深度融合的核心技术实现路径.md#L1005)

- Bayes factor只解释为模型证据强度。
  [`04-分场景多方法融合适配方案.md:313`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/04-分场景多方法融合适配方案.md#L313)

**工程与证据**

- 数据、算子、恢复和唯一benchmark契约集中定义。
  [`05-工程化落地与效率优化方案.md:7`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/05-工程化落地与效率优化方案.md#L7)

- 合成章节改为Planned预注册验证方案。
  [`06-合成数据验证案例.md:1`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/06-合成数据验证案例.md#L1)

- SBC、PPC和靶区概率校准分别验收。
  [`06-合成数据验证案例.md:41`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/06-合成数据验证案例.md#L41)

- 结论降级为TRL 3—4研发框架与待验证目标。
  [`07-结论与展望.md:5`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/07-结论与展望.md#L5)
