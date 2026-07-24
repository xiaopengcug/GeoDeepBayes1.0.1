---
title: 'WP1：联合概率模型与UQ内核重写'
type: 'refactor'
created: '2026-07-17'
status: 'done'
review_loop_iteration: 5
baseline_commit: 'NO_VCS'
context:
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/修改计划03.md'
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/审查意见03.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 现有理论总纲对极化率与共享nuisance复用`η`，概率图不能唯一确定联合分布，相关误差与iid Student-t、Full Bayes与经验贝叶斯、PPC与覆盖率等概念互相冲突；多源先验还存在重复计数风险。

**Approach:** 以单一生成式DAG为规范源，统一变量字典、联合分解、相关误差、先验数据入口、后验适定条件和五类UQ/校准术语，并用两个最小生成模型做prior predictive与SBC概念验证。

## Boundaries & Constraints

**Always:** `η_IP`只表示极化率、`ξ`只表示共享nuisance；DAG节点、联合分布因子和变量字典双向一致；钻孔、物性库、解释成果以唯一source-id进入一次；相关误差保留方法内/跨方法协方差且整体SPD；Full Bayes与Empirical Bayes分别陈述；所有数值结果遵守WP0证据等级。

**Ask First:** 若必须改变WP1以外的物理正演定义、决策效用模型或正式`evidence-status.md`，先暂停并请求批准；若只能以依赖超参数的PoE表达先验，须先说明`Z(θ)`及其对模型证据比较的限制。

**Never:** 不把`ν≥1`单独称为后验proper保证；不保留“EM确保收敛/通常5—10次”保证；不将PPC当作参数或现场覆盖率；不把五类不确定性无正交依据地直接相加；不把toy验证写成现场或完整体系证据。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 统一生成模型 | 多方法数据、先验源和相关误差 | 从DAG可唯一重写与正文相同的联合分布 | 节点、父边或因子不匹配即阻断验收 |
| 重复先验源 | 同一钻孔/物性/解释经多个因子消费 | 仅保留一个生成入口，其余改为派生量 | 无法判定独立性时登记冲突并停止重复使用 |
| 校准输出 | PPC、留出、SBC、参数/现场覆盖 | 分类型、名义水平、抽样单元和适用范围保存 | 禁止裸`coverage`字段或跨类型解释 |

</frozen-after-approval>

## Code Map

- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/02-全方法深度融合的底层逻辑与理论总纲.md` -- 生成模型、似然、先验与proper性规范源。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/03-多方法深度融合的核心技术实现路径.md` -- 五类UQ与可靠性验证定义。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录2-概率化反演结果应用规范与风险管控准则.md` -- UQ披露与决策使用检查表。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录4-核心算法性能基准测试计划与验收指标.md` -- prior predictive、SBC及对抗组测试规范。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录5-真实矿区验证方案.md` -- 合成参数覆盖与现场留出预测覆盖边界。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录12-全深度概率立方体可视化工具.md` -- 校准输出schema。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录14-地质先验知识库.md` -- 先验精度、超先验及序贯更新治理。

## Tasks & Acceptance

**Execution:**
- [x] `02-全方法深度融合的底层逻辑与理论总纲.md` -- 重写2.3.1—2.3.3：变量字典、生成DAG、唯一联合分解、多元Student-t或局地尺度混合高斯、Full/Empirical Bayes边界、有限维proper充分条件和先验唯一入口。
- [x] `03-多方法深度融合的核心技术实现路径.md` -- 重写3.4：观测、参数、模型差异、代理、场景五类UQ，并严格区分PPC、留出预测校准、SBC、参数覆盖和现场预测覆盖。
- [x] `附录2-概率化反演结果应用规范与风险管控准则.md`、`附录5-真实矿区验证方案.md`、`附录12-全深度概率立方体可视化工具.md` -- 统一校准统计契约、抽样单元和输出字段。
- [x] `附录4-核心算法性能基准测试计划与验收指标.md` -- 增加两个固定种子的最小生成模型：相关厚尾模型、两方法共享`ξ`模型；每个含prior predictive、SBC及错协方差/漏`ξ`对抗组。
- [x] `附录14-地质先验知识库.md` -- 将0.1—0.9“先验权重”改为参数尺度上的标准差/精度或proper超先验范围，删除同数据事后增强约束。
- [x] `validate-wp1.ps1`与`修改计划03-执行日志.md` -- 已加入符号、禁语、DAG/因子、source-id、校准schema、运行包哈希、签核绑定及故障恢复门禁；最终双签均为PASS并绑定16成员输入根。

**Acceptance Criteria:**
- Given 修订后的DAG和变量字典，when 贝叶斯专家独立写出联合分布，then 节点、父边、支持集、数据入口及边缘化/采样状态与正文逐项一致。
- Given 任一钻孔、物性库或解释source-id，when 检查所有先验和似然消费点，then 恰有一个生成入口且无隐性重复计数。
- Given 相关误差模型，when 检查协方差，then 对称、Cholesky可分解且最小特征值门禁明确。
- Given 两个toy模型及固定运行清单，when 执行prior predictive和SBC概念验证，then 保存rank/覆盖不确定性及对抗组诊断，且只标记为Synthetic-run或Planned。
- Given 全部WP1文件，when 运行专用验证器并完成贝叶斯/UQ书面复核，then 无一符多义、禁语、裸`coverage`或校准类型混用。

## Spec Change Log

- 2026-07-17：完成WP1规范源、附录统计契约、Planned toy清单和专用验证器；`validate-wp1.ps1 -SelfTest`通过。WP0冻结哈希按设计检测到本次已批准正文变更，须由主代理决定是否生成派生基线；独立专家签核尚未完成。
- 2026-07-17：首轮复审不通过后，直接改写2.3.1—2.3.3与3.4冲突旧式；验证器改为截取目标章节全文执行真实残留规则，状态恢复`in-progress`。
- 2026-07-17：经六轮专项返修，贝叶斯/UQ与地球物理独立复审均PASS；两个toy各完成400次prior-predictive/SBC运行，Run ID为`WP1-TOY-20260717-R400-v1`，限定状态为Synthetic-run。
- 2026-07-17（对抗复审回环1）：运行实现与附录声称的4链/warmup/draw、逐重复种子和10,000份prior predictive不一致，配置字段被硬编码绕过，汇总与逐重复记录不可重算，机器输出未落实统一校准schema；同时发现旧逐方法厚尾公式、条件独立注释与PoE参数化仍可能绕开唯一DAG。规格补充机器证据合同并重新派生。KEEP：已通过的唯一DAG、标量尺度混合、互斥source-id、方法观测表、五类UQ/校准定义、现场整群留出及两位专项复审结论必须保留。
- 2026-07-17（对抗复审回环2）：重建toy证据链。每个SBC重复使用`seed=root+r`和1000个真实后验draw形成整数rank；prior predictive独立N=10,000；CSV可重算rank bins、覆盖、Wilson区间与失败率。runner采用worker/stage/原子发布，manifest记录真实进程证据、环境、配置快照和全哈希，运行目录外根锚生效；`validate-wp1.ps1 -SelfTest`通过同步伪造、CSV截断、run_id错配、配置扰动和病态Sigma五类生产入口负例。状态保持`in-progress`，等待主审最终闭环。
- 2026-07-17（回环2主审补修）：删除与主模型冲突的逐方法iid Student-t/EM/梯度更新式；联合协方差下不再声称逐方法条件独立；PoE明确为$p(m\mid z,\Theta)$内部参数化并绑定互斥来源；补$\epsilon$节点；清理附录4和执行日志的过时全称状态。
- 2026-07-17（对抗复审回环3）：静态包可由SBC CSV重算，但生产runner未原子更新外置锚，prior-predictive缺原始样本，统一校准记录未与重算统计绑定，签核未绑定当前输入根，DAG/source-id缺生产负例。KEEP：回环2的配置驱动runner、逐重复seed、整数rank、CSV汇总重算、原子stage、环境/exit清单和理论主干。
- 2026-07-17（对抗复审回环3实施，后续已纠正）：runner增加独占锁、stage隔离和output/anchor事务；新增20,000行`prior-predictive.csv`及逐行SBC观测。该阶段曾把`prior_predictive_simulation`误列为校准类型，后续已撤销；prior predictive现仅为生成模型诊断。旧Pending根已失效。
- 2026-07-17（对抗复审回环4）：清除03章逐方法自由度、独立方差Gibbs、链内调参、PPC选参、事后固定参数及经验先验权重冲突；增加不可变来源谱系与现场相关簇留出；验证器加入签核根门禁、锁冲突、worker失败及发布回滚自测。
- 2026-07-17（对抗复审回环5）：删除逐方法Huber噪声估计与短窗伪收敛接口；校准验证升级为5个split×3类记录的精确矩阵并重算rank卡方；发布journal采用`Flush(true)`与原子替换，覆盖四阶段中断及截断journal恢复。最终16成员输入根为`a773824fd0b18afe8ddb8c7bb4e55f3886c9c137b9651536e6c5fef7a5027335`，贝叶斯/UQ与地球物理AI独立复审均PASS，默认验证与`-SelfTest`均PASS。

## Design Notes

主路径采用有限维条件生成模型：`z→m`，`ξ→F^h`，方法差异`δ`与相关观测误差`ε`分别进入`d`；`Σ=BBᵀ+blockdiag(Σ_k)+εI`作为可保证SPD的示例。代理误差独立记为`δ_surr`。若选尺度混合形式，局地尺度仅控制厚尾，不能抹去`Σ`的相关结构。

toy概念验证采用可审查的参考后验，不伪装为MCMC：相关t模型使用有网格截断质量门禁的数值归一化后验，共享`ξ`模型使用解析高斯后验；SBC以每重复独立种子生成posterior draws并形成随机化rank。附录、配置、脚本和结果必须声明同一算法与预算。prior predictive独立生成10,000份；SBC保持400次。所有模型参数只从机器配置读取，配置是唯一运行规范源。

运行包须原子写入，记录真实尝试/成功/失败数、环境、stdout/stderr、退出状态及文件哈希；逐重复记录必须能重算rank bins、覆盖、Wilson区间与失败率。机器校准输出使用统一`calibration_record`字段，禁止只有裸coverage。独立签核须落为含审查范围、输入根哈希、结论和发现处置的文件。外部数字签名/可信时间戳留给WP6，但WP1需在运行目录外保存根哈希锚并由验证器核对。

runner发布事务必须同时更新output与外置锚，使用独占锁并隔离陈旧stage。保存prior-predictive逐样本文件以重算摘要；SBC逐行保存生成观测和seed，验证器抽样重演posterior rank。`calibration_records`至少包含参数覆盖与`sbc_rank`诊断，并逐项绑定CSV重算值。相关t网格须检查边界质量或扩大网格稳定性。签核输入根须声明文件集合、排序与哈希算法，并由门禁重算；代码或正文变化后旧签核自动失效。

## Verification

**Commands:**
- `& '<research-dir>/validate-wp1.ps1' -SelfTest` -- expected: 正向检查通过，符号冲突、重复source-id、非SPD、禁语和裸coverage负例均被拒绝。
- `& '<research-dir>/validation/wp1-toy/run-wp1-toy.ps1'` -- expected: 使用配置中的全部参数，独立生成10,000份prior predictive和400次SBC；原子生成可由逐重复记录重算的Synthetic-run包。
- `& '<research-dir>/validate-wp0.ps1' -SelfTest` -- expected: 对WP1批准后的正文变化返回非零并定位漂移；正式`evidence-status.md`哈希仍为WP0冻结值，禁止以重新生成基线掩盖变更。

**Manual checks:**
- 贝叶斯/UQ专家从DAG独立复写联合分布并签核；地球物理专家核对观测节点单位、几何、共享nuisance及误差来源。

## Suggested Review Order

**联合概率模型与推断边界**

- 从唯一联合残差与共享厚尾尺度理解核心模型。
  [`03-多方法深度融合的核心技术实现路径.md:1246`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/03-多方法深度融合的核心技术实现路径.md#L1246)

- 用不可变来源谱系阻断复制改名后的重复消费。
  [`02-全方法深度融合的底层逻辑与理论总纲.md:370`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/02-全方法深度融合的底层逻辑与理论总纲.md#L370)

**现场校准与证据边界**

- 相关钻孔合并为独立评价簇，避免伪重复。
  [`附录5-真实矿区验证方案.md:39`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录5-真实矿区验证方案.md#L39)

- 明确Synthetic-run、SBC与prior predictive的证据边界。
  [`附录4-核心算法性能基准测试计划与验收指标.md:40`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录4-核心算法性能基准测试计划与验收指标.md#L40)

**验证与可恢复发布**

- 原子journal确保output与外置锚可跨中断恢复。
  [`run-wp1-toy.ps1:19`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp1-toy/run-wp1-toy.ps1#L19)

- 精确校准矩阵与卡方重算阻断统计错配。
  [`validate-wp1.ps1:54`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-wp1.ps1#L54)

- 独立签核绑定最终16成员输入根。
  [`WP1-贝叶斯UQ独立代理签核.md:3`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/WP1-贝叶斯UQ独立代理签核.md#L3)
