---
title: 'WP2：数值推断理论修正'
type: 'refactor'
created: '2026-07-17'
status: 'done'
review_loop_iteration: 6
baseline_commit: 'NO_VCS'
context:
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/修改计划03.md'
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/审查意见03.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-wp1-rewrite-joint-probability-uq-core.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 数值推断章节仍含矩形POD基行列式、不同支撑测度的直接KL、缺少维数匹配的RJMCMC接受率，以及EIG、实现后KL和LOMO混用；诊断阈值、复杂度和正则化选择也跨文冲突，无法保证目标分布正确或结果可复核。

**Approach:** 建立唯一的降阶测度、Green型RJMCMC、三类信息量、采样诊断、成本账本和正则化选择契约，并用解析toy与机器验证器检验推前分布、详细平衡、诊断失败和统计量错配。

## Boundaries & Constraints

**Always:** POD系数先验必须proper且说明推前测度；RJMCMC必须显式给出move选择概率、辅助密度、可逆映射、维数匹配和Jacobian；EIG、实现信息增益与LOMO固定目标变量、条件信息和方向；所有采样章节读取同一诊断合同；复杂度按真实算子阶段和实际高保真调用计量；正则化选择披露数据分割与不确定性遗漏。

**Ask First:** 若需改动WP1冻结的联合概率模型、真实DO-27运行、正式证据等级或引入高成本集群/GPU运行，暂停并请求批准。

**Never:** 不写`det(Φ_r)`；不比较奇异支撑上的全维Lebesgue KL；不省略RJMCMC反向move或辅助密度；不宣称IG一般可加、次可加或随“数据质量”单调；不以接受率、总ESS或旧`Rhat<1.05`单独判定收敛；不按同一训练残差选择最弱正则化并称为Bayes最优。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| POD降阶 | 正交矩形基、proper系数先验 | 在系数空间定义后验并推前；预测/功能量误差可比较 | `det(Φ_r)`或跨奇异测度KL出现即阻断 |
| RJMCMC跨维move | 状态、move、辅助变量及逆move | 正反映射可逆，接受率满足详细平衡 | 缺选择概率、密度、维数或Jacobian即失败 |
| 信息量估计 | 设计前、观测后或LOMO输入 | 输出明确类型、方向、估计器、MC误差 | 未归一化核直接作后验比值即拒绝 |
| 链诊断 | 完整链、模态、决策量与失败重复 | 输出rank split-Rhat、bulk/tail ESS、MCSE、模态访问、失败率 | 任一硬门失败则run状态Failed |

</frozen-after-approval>

## Code Map

- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/03-多方法深度融合的核心技术实现路径.md` -- POD、RJMCMC、信息量、诊断、复杂度和正则化的规范源。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/02-全方法深度融合的底层逻辑与理论总纲.md` -- 删除第二套简化RJMCMC式并引用唯一规范。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录3-算法选型与多方法组合决策树.md` -- 算法选择与诊断阈值消费者。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录4-核心算法性能基准测试计划与验收指标.md` -- 诊断、详细平衡及复杂度测试合同。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/贝叶斯三维反演测试算力需求说明.md` -- 成本分解、预算状态和运行证据边界。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp2-toy/` -- POD与RJMCMC解析toy、诊断参考数据及可复算输出。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-wp2.ps1` -- 跨文契约、toy统计与负例门禁。

## Tasks & Acceptance

**Execution:**
- [x] `03-多方法深度融合的核心技术实现路径.md`、`02-全方法深度融合的底层逻辑与理论总纲.md` -- 用系数空间推前测度和唯一Green模板替换POD/RJMCMC错误公式；删除接受率下界伪定理与重复规范。
- [x] `03-多方法深度融合的核心技术实现路径.md` -- 分离设计EIG、实现信息增益和LOMO，给出含证据项的可计算估计器；统一damping、先验精度及模型选择流程。
- [x] `03-多方法深度融合的核心技术实现路径.md`、`附录3-算法选型与多方法组合决策树.md`、`附录4-核心算法性能基准测试计划与验收指标.md` -- 建立单一诊断合同，撤销无run-id结果表和IG贡献率，并让所有消费者引用合同。
- [x] `03-多方法深度融合的核心技术实现路径.md`、`贝叶斯三维反演测试算力需求说明.md` -- 按装配、预条件、源/频点、Krylov、伴随、通信、I/O、存储和高保真调用重写成本账本。
- [x] `validation/wp2-toy/`、`validate-wp2.ps1` -- 实现解析Gaussian POD、单位/非单位Jacobian RJMCMC、双峰/重尾诊断及篡改负例；保存配置、逐重复记录、摘要和哈希。
- [x] `修改计划03-执行日志.md` -- 登记WP1 Done、WP2状态、运行ID、验证结果和独立算法/贝叶斯复核。
- [x] `02-全方法深度融合的底层逻辑与理论总纲.md`、`03-多方法深度融合的核心技术实现路径.md` -- 清除旧诊断阈值、分块/并行回火伪谱隙、错误温度阶梯、高斯互信息与条件IG上界泛化；保证公式标签唯一。
- [x] `validation/wp2-toy/` -- 从配置中的POD基和先验参数计算秩、Gram、体积与proper性；用独立重复或链ESS/批均值构造模型占比误差；增加粘滞双峰、尺度错配和尾部未探索失败链。
- [x] `validation/wp2-toy/`、`validate-wp2.ps1` -- 对三类信息量运行有限MC估计并保存outer/inner预算、逐重复估计、偏差及MCSE；严格校验manifest白名单、路径、源码/环境/命令/退出日志和所有合同字段。
- [x] `validate-wp2.ps1` -- 补齐链排序/连续性、有限值、常链、move枚举、参数状态、失败率及folded门；以文档fixture验证唯一诊断阈值和成本/正则化完整报告契约。
- [x] `02/03/05`及`附录2/3/4/9/10/11` -- 全量清除复制诊断阈值、单指标放行和运行期非递减调参；所有消费者只引用机器合同。
- [x] `validation/wp2-toy/` -- 消除POD维数/rank/proper硬编码，使用非平凡矩形基；为LOMO建立独立seed、样本路径和可区分RIG的多观测案例；移除相关链独立Wilson字段。
- [x] `validate-wp2.ps1` -- 实现严格source/path/状态白名单、链索引与状态域守卫、SPD/信息语义/失败hard-gate；新增这些真实fixture及成本/正则化字段级文档fixture。
- [x] `validation/wp2-toy/report-contract.json`、`validate-wp2.ps1` -- 用机器字段合同验证成本阶段、容差、迭代/调用数、数据分割、选择规则、状态和遗漏不确定性；禁止以关键词替代。
- [x] `validation/wp2-toy/` -- 保存并哈希真实stdout/stderr日志；为每个失败诊断夹具计算完整hard-gate状态与原因；LOMO seed/sample_path与RIG集合互斥且可重放。
- [x] `validation/wp2-toy/`、`validate-wp2.ps1` -- 拆分wrapper/worker捕获真实进程日志与退出状态；一般化任意`r`的POD Cholesky/后验/预测复算并加入`r≠2`正控。
- [x] `validate-wp2.ps1` -- 从失败链重算每个case的完整指标、hard-gate原因；重算LOMO raw evidence并锁定跨类型seed/path；强制Observed绑定manifest。
- [x] `report-contract.json`、`report.json`、`validate-wp2.ps1` -- 约束阶段—单位语义、候选有限唯一、split互斥、选择规则枚举及manifest引用；修正文档fixture临时树闭包。
- [x] `validation/wp2-toy/`、`validate-wp2.ps1` -- 完成可恢复原子发布、旧证据保护、source/output合同同一性、非法配置域和正式包Passed硬门。
- [x] `validation/wp2-toy/`、`validate-wp2.ps1` -- 逐seed重放LOMO原始证据；失败摘要列出全部触发门并明确`fault_injection`而非真实进程失败；WP2包禁止无测量的Observed洗白。
- [x] `validate-wp2.ps1` -- 成功路径显式返回exit 0，并以独立父进程断言SelfTest同时输出PASS和退出码0；补回环5真实负例。
- [x] `validation/wp2-toy/`、`validate-wp2.ps1` -- 例外回环：限制worker只能写wrapper创建的本地stage；钉死诊断合同最低schema/阈值；以不可变版本目录和原子活动指针消除并发读取缺口。

**Acceptance Criteria:**
- Given 矩形正交POD基，when 重写降阶后验，then 不出现矩形行列式或未定义全维KL，且解析预测矩与toy输出一致。
- Given 可解析两模型RJMCMC，when 运行正反move，then 逆映射、Jacobian和log详细平衡逐例通过，模型占比区间覆盖解析概率。
- Given EIG、实现后KL和LOMO案例，when 计算估计量，then 类型、条件集、方向、证据项与MC误差完整，相关数据不被归一为可加贡献率。
- Given 任一诊断消费者，when 扫描阈值，then 仅引用唯一合同，并同时检查rank-normalized split-Rhat、bulk/tail ESS、关键决策量MCSE、跨模态访问及失败率。
- Given 成本或正则化报告，when 验证，then 阶段成本、容差、迭代数、数据分割、选择规则及Planned/Synthetic-run状态均可审计。

## Spec Change Log

- 2026-07-17（审查回环1）：盲审发现旧诊断阈值与伪谱隙推导仍可绕过唯一合同，POD/信息量存在硬编码，相关RJMCMC占比误用独立Wilson区间，manifest及成本/正则化门禁不足。新增全篇公式清理、POD配置复算、有限MC信息量、相关链误差、失败型诊断夹具和生产文档fixture任务。KEEP：已通过的Green接受率、40,000步可重放链、Blom/Acklam Rhat、标准Geyer ESS、结构化logZ/Zr与16类生产入口负例必须保留。
- 2026-07-17（审查回环2）：回环1只扫描了部分消费者，导致05及附录2/9/10/11仍复制旧阈值；POD维数/rank/proper、LOMO路径、source白名单与多项链边界仍可绕过。扩大消费者闭包和生产fixture，要求LOMO独立估计路径、非平凡POD基、严格manifest/状态域及字段级成本正则化合同。KEEP：回环1已修正的MI/谱隙/温度结论、有限MC预算、相关链批均值误差、失败诊断夹具和源码环境manifest不得回退。
- 2026-07-17（审查回环3）：回环2的消费者扫描和成本/正则化门仍停留在部分文件与关键词；POD验证器固定2列，LOMO路径、日志和失败hard-gate缺防回归证据。新增全消费者fixture、一般矩阵rank/Gram、机器报告合同、真实日志及每失败夹具联合状态任务。KEEP：40,000步链重放、批均值稳定性、独立LOMO实现、非平凡3×2正控、28类生产入口负例和Hypothesis/Observed治理必须保留。
- 2026-07-17（审查回环4）：回环3的两类文档fixture因临时树不完整而假拒绝；POD后验仍固定2维，日志为进程内合成，失败reason/LOMO raw evidence/Observed报告语义未被独立重算。新增wrapper/worker真实日志、任意r矩阵正控、失败与LOMO数值重演及报告语义约束。KEEP：10消费者闭包、48类生产入口框架、一般Gram/rank、机器报告字段、source/output一致性和相关链证据不得回退。
- 2026-07-17（审查回环5）：回环4仍存在SelfTest打印PASS但exit=1、worker失败污染旧output、发布中断无恢复、正式Failed包可验收、failure reason漏门、LOMO seed未重放及Observed空引用洗白。新增原子恢复、Passed总门、逐seed重演、故障注入语义和父进程exit断言。KEEP：wrapper/worker真实日志、4×3/r=3通用矩阵、52类fixture、仓库消费者发现和硬编码最低合同骨架必须保留。
- 2026-07-17（用户批准例外回环6）：最终边界审查指出目录换名事务存在并发读取缺口、worker stage未限制、诊断合同可同步降级。用户批准追加定向回环；采用不可变版本目录+原子活动指针、受限stage capability与硬编码诊断最低门。KEEP：回环5的57类fixture、旧output保护、逐seed LOMO、失败reason全集、父进程exit 0及所有理论修订不得回退。

## Design Notes

诊断合同采用机器可读配置作为唯一阈值源；正文只解释语义并引用字段。默认硬门以`Rhat≤1.01`、bulk/tail ESS与决策MCSE联合判定，但具体数值须在实施时结合现有WP1证据治理冻结，禁止多个章节复制阈值。RJMCMC至少覆盖`M0↔M1`单位Jacobian和split/merge非单位Jacobian两个toy；故意删除反向概率或Jacobian的负例必须失败。

## Verification

**Commands:**
- `& '<research-dir>/validate-wp2.ps1' -SelfTest` -- expected: 正向toy、跨文合同和哈希通过；POD行列式、RJMCMC缺项、IG混用、旧诊断阈值、统计篡改负例均被拒绝。
- `& '<research-dir>/validation/wp2-toy/run-wp2-toy.ps1'` -- expected: 固定配置重建解析目标、逐move详细平衡记录和诊断样本，失败重复不重抽。

**Manual checks:**
- 算法专家独立复写Green接受率并核对维数/Jacobian；贝叶斯专家独立核对三类信息量测度、证据项和诊断合同。

## Suggested Review Order

**数值推断规范**

- 从唯一Green式理解跨维目标与详细平衡。
  [`03-多方法深度融合的核心技术实现路径.md:517`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/03-多方法深度融合的核心技术实现路径.md#L517)

- 区分设计EIG、实现信息增益与LOMO方向。
  [`03-多方法深度融合的核心技术实现路径.md:611`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/03-多方法深度融合的核心技术实现路径.md#L611)

- 分离数值damping、先验精度和模型选择。
  [`03-多方法深度融合的核心技术实现路径.md:1012`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/03-多方法深度融合的核心技术实现路径.md#L1012)

**证据与诊断合同**

- 钉死诊断schema与不可放宽hard gates。
  [`validate-wp2.ps1:106`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-wp2.ps1#L106)

- 从原始链重算失败指标及精确原因全集。
  [`validate-wp2.ps1:201`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-wp2.ps1#L201)

- 58类生产入口负例保护理论和报告合同。
  [`validate-wp2.ps1:223`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-wp2.ps1#L223)

**可恢复发布**

- 不可变版本与原子活动指针保持读者连续可见。
  [`run-wp2-toy.ps1:30`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp2-toy/run-wp2-toy.ps1#L30)

- Worker stage capability阻断误写正式输出。
  [`wp2-toy-worker.ps1:12`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp2-toy/wp2-toy-worker.ps1#L12)
