---
title: 'WP7运行证据重建'
type: 'feature'
created: '2026-07-24T08:02:00-06:00'
status: 'done'
baseline_commit: '9e2c2e9ca53b6c20eb5cb3f3f1f7ae348a9ac6bc'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/修改计划03.md'
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/contracts/evidence-run.schema.json'
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp2-toy/diagnostic-contract.json'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 现有 `synthetic-block` 与 DO-27 运行仅能证明局部链路，缺少可独立复算的原始链、预注册选参、代理误差、正确 delayed acceptance 和 evidence-run v2 治理，不能关闭 WP7。

**Approach:** 建立 `synthetic-block-v2`、`DO-27-v2`、统一 WP7 validator 和三角色 AI 技术签核；正式结果不满足冻结门槛时保持 Failed，不通过改阈值或挑种子升级。

## Boundaries & Constraints

**Always:** 使用 Python 3.11.15、uv 0.11.29 和冻结锁文件；保存代码/输入/配置/输出哈希、随机种子、原始数值数组和完整退出状态；DA 链在完整参数空间探索且第二阶段使用代理比率校正；DO-27 分离 solver/data-fit/model-recovery；所有正向 claim 与实际运行范围一致。

**Ask First:** 使用外部高算力、改变 DO-27 归档、发布外部证明、要求自然人或现场签核。

**Never:** 把 DO-27 称为 PGI、联合反演、贝叶斯反演或原 notebook 复现；把子空间 DA 称为全维后验；在看到结果后改变阈值、种子、链长、alpha 候选或误差模型；修改无关未跟踪资产。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| synthetic success | 冻结配置、完整链和解析基线 | 原子发布 v2 包，validator 独立重算全部指标 | 不适用 |
| DO-27 success | 归档哈希匹配且两方法三门通过 | 发布“降阶单物理兼容验证”包 | 不适用 |
| threshold failure | 任一冻结门失败 | 保存产物，状态 Failed，claims 为空 | 非零退出，不更新 active output |
| input drift | DO-27 归档哈希变化 | 不启动数值运行 | Blocked 并记录原因 |
| tampering | 原始链、alpha 路径、配置或签核根改变 | validator 拒绝 | 非零退出 |

</frozen-after-approval>

## Code Map

- `src/geodeepbayes/sampling/` -- 全维 delayed acceptance 与 POD 子空间边界。
- `src/geodeepbayes/benchmarks/` -- synthetic-block-v2 解析基线、POD 比较和正式运行。
- `tests/` -- 数学正确性、选参、失败关闭和治理回归。
- `_bmad-output/.../validation/wp7/` -- 预注册合同、runner、validator、发布版本和签核。
- `_bmad-output/.../{evidence-status.md,主张-证据映射03.md,修改计划03-执行日志.md}` -- 通过后治理回写。

## Tasks & Acceptance

**Execution:**
- [x] `src/geodeepbayes/sampling/delayed_acceptance.py` -- 实现支持一般提议密度比的全维两阶段 MH，并输出完整 trace。
- [x] `src/geodeepbayes/sampling/pod.py` -- 修正现有子空间 DA 公式并明确能力边界。
- [x] `src/geodeepbayes/benchmarks/synthetic_block_v2.py` -- 构建48维解析混合高斯基线、冻结快照/POD、三方法链和400次解析覆盖率。
- [x] `_bmad-output/.../validation/wp7/` -- 实现两个预注册配置、DO-27 GCV runner、原子发布和独立复算 validator。
- [x] `tests/` -- 覆盖 DA detailed balance、POD隔离、诊断门、GCV和篡改负例。
- [x] `evidence-status.md` 等治理文件 -- 仅在两个运行包和签核通过后回写 WP7 Done。

**Acceptance Criteria:**
- Given 解析双模态目标, when 运行全维 DA, then 所有链通过 WP2 诊断门且后验均值、模态概率和预测区间满足预注册偏差门。
- Given 400个冻结复制, when 重算解析覆盖率, then 报告 Wilson 区间且执行失败率与覆盖率分开登记。
- Given DO-27 alpha 路径, when 选参, then 数据空间 SVD GCV 和 1% 强正则 tie-break 决定唯一 alpha，训练 RMS 与真值不参与。
- Given 任一证据文件被篡改, when 运行 SelfTest, then 成员根、语义重算或 claim 门拒绝该包。
- Given 两包通过, when 三个隔离 AI 角色签核同一根, then 默认 WP7 门通过并允许治理回写。

## Spec Change Log

- 2026-07-24：DO-27-v2按冻结门失败后，用户指示继续。归档生成脚本证明重磁数据均以`std=0`生成，故新增v3预注册：数据拟合只设RMS上界，低RMS登记为overfit warning；模型恢复继续独立报告但不作为“现代API降阶单物理兼容”硬门，避免把欠定降阶模型恢复偷换为运行兼容性。v2保持不可变Failed。

## Design Notes

全维 DA 使用 `πs` 只做第一阶段预筛：第一阶段包含 `q(x|y)/q(y|x)`，第二阶段使用 `π(y)πs(x)/[π(x)πs(y)]`。naive/error-inflated POD 明确是受限近似，只与解析全维目标比较误差，不冒充同一目标。DO-27 白化 RMS 为 `sqrt(mean(((dobs-dpred)/σ)^2))`，接受区间固定为 `[0.5,1.2]`。

## Verification

**Commands:**
- `uv run --frozen pytest tests/` -- 全量测试通过。
- `pwsh -NoProfile -File ".../validate-wp6.ps1" -SelfTest` -- WP6 无回归。
- `pwsh -NoProfile -File ".../validate-wp7.ps1" -SelfTest` -- 两包、篡改负例和签核闭包通过。

## Suggested Review Order

**采样正确性**

- 全维两阶段校正确保代理只影响效率。
  [`delayed_acceptance.py:41`](../../src/geodeepbayes/sampling/delayed_acceptance.py#L41)

- POD子空间明确边界并支持非对称提议。
  [`pod.py:86`](../../src/geodeepbayes/sampling/pod.py#L86)

**正式数值运行**

- 合成入口统一48维采样、冻结POD与覆盖复制。
  [`synthetic_block_v2.py:120`](../../src/geodeepbayes/benchmarks/synthetic_block_v2.py#L120)

- DO-27入口强制预注册配置与归档哈希。
  [`run_do27_validation.py:227`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/do27/run_do27_validation.py#L227)

**独立验证与治理**

- 合成验证从快照、种子与原始链重建指标。
  [`validate_wp7.py:30`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp7/validate_wp7.py#L30)

- DO-27验证独立重跑完整LSQR与GCV路径。
  [`validate_wp7.py:247`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp7/validate_wp7.py#L247)

- 三角色签核绑定唯一审查内容和成员根。
  [`finalize_signoff.py:16`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp7/finalize_signoff.py#L16)

**回归测试**

- POD测试锁定提议比与阶段校正行为。
  [`test_pod.py:45`](../../tests/sampling/test_pod.py#L45)

- GCV测试锁定真值隔离与强正则tie-break。
  [`test_wp7_rules.py:8`](../../tests/benchmarks/test_wp7_rules.py#L8)
