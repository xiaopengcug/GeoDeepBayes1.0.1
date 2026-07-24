---
title: 'WP4：决策、风险与资源量模型重写'
type: 'refactor'
created: '2026-07-18'
status: 'done'
review_loop_iteration: 13
baseline_commit: 'NO_VCS'
context:
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/修改计划03.md'
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/审查意见03.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-wp1-rewrite-joint-probability-uq-core.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-wp2-correct-numerical-inference-theory.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 当前逐体素分位数相加、`Risk×钻探成本`式ENPV和无界`R_total`会破坏空间相关、重复计费并把score冒充概率；“可采资源量”措辞又超出物探后验和合规证据。

**Approach:** 以联合后验draw逐样本构造靶体潜力情景，以唯一的状态—行动—现金流—效用合同计算ENPV/EVPI/EVSI，并用隔离回放toy校准风险概率及验证决策净收益。

## Boundaries & Constraints

**Always:** 同一draw内保留体素、品位、密度、回收率、稀释/损失和经济变量依赖；分位数只对逐draw总量求取；明确`q0.10/q0.50/q0.90`及P90/P50/P10超越概率语义；货币、价格时点、名义/实际、折现率和时间单位唯一；行动、状态、损失、实施成本与失败损失分列；概率模型train/calibration/test按时间/空间cluster隔离。

**Ask First:** 若需改变WP1联合概率根、声称正式资源量/储量、引入真实矿区或商业敏感数据、进行外部合规分类/合资格人员签署，或开展高成本历史回放，暂停并请求批准。

**Never:** 不逐格相加分位数；不从边际概率独立Bernoulli重建空间draw；不把缺品位/密度/回收率/修正因素/签署的输出称资源量；不以裁剪`R_total`制造概率；不在test/盲孔上校准、选阈值或定义事件；不重复扣调查/钻探成本；不把Synthetic toy升级为Field-validated。

## I/O & Edge-Case Matrix

| 场景 | 输入/状态 | 预期行为 | 错误处理 |
|---|---|---|---|
| 联合样本 | 完整冷链draw、体素与情景变量 | 逐draw输出体积、吨位、含量、回收金属量及整体分位数 | draw拼接、缺体素、非法单位/权重时拒绝 |
| 决策 | 同一状态分布、行动集与现金流口径 | 输出每行动ENPV、最优行动、EVPI/EVSI/net-EVSI与MCSE | 非归一概率、错币种、重复成本或`r≤-1`时拒绝 |
| 风险校准 | 冻结train/calibration/test与cluster | test-only输出概率、proper scores、可靠性和净收益 | 泄漏、盲孔参与拟合或test调阈值时拒绝 |
| 合规命名 | 无完整合规输入/签署 | 仅发布“物探约束靶体潜力情景” | 正式资源量/储量命名阻断发布 |

</frozen-after-approval>

## Code Map

- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/00-摘要.md` -- 删除直接输出可采资源量的越界主张。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/03-多方法深度融合的核心技术实现路径.md` -- 资源draw、ENPV与信息价值主公式。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/04-分场景多方法融合适配方案.md` -- `R_total`降级与校准概率/决策门。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录2-概率化反演结果应用规范与风险管控准则.md` -- 样本、分位数、资源合规和行动规范。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录5-真实矿区验证方案.md` -- 时间截断、盲孔、cluster校准与净收益。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录10-项目实施进度计划与经费概算模板.md`、`附录11-分勘查阶段标准化操作手册.md`、`附录12-全深度概率立方体可视化工具.md` -- 成本口径、阶段输出和可视化命名。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp4-decision/` -- 联合样本、精确枚举oracle、回放校准与不可变证据包。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-wp4.ps1` -- 文档、合同、raw、独立oracle、签核和SelfTest生产门。

## Tasks & Acceptance

**Execution:**
- [x] `00-摘要.md`、`03-...md`、`04-...md` -- 删除全部“可采资源量/达标概率”、逐格分位数、静态`Risk×成本`和score伪概率冲突段；validator扫描禁式而非只检查免责声明存在。
- [x] `附录2-...md`、`附录11-...md` -- 删除包括“推断资源升级为控制资源”逆序表达在内的全部升级指令，并扩展明确禁式。
- [x] `附录5-...md` -- 冻结时间/空间cluster、条件孔/盲孔、事件和解封记录；用Brier、log score、可靠性、cluster-bootstrap与decision curve验收。
- [x] `附录10-...md`、`附录11-...md`、`附录12-...md` -- 统一币种/基准年/折现/成本和非正式情景命名，删除孔数/概率自动升级资源类别。
- [x] `validation/wp4-decision/` -- 身份字段严格要求非空canonical `draw_id/chain_id/sample_id/ancestor_id`；`chain_id+sample_id`必须唯一（ancestor不能掩盖重复样本）；voxel ID非空且禁止signature分隔符，身份数组逐元素比较。保留回环2的lineage/voxel/比例防护。
- [x] `validation/wp4-decision/` -- `cashflow_contract`必须具有精确action/state集合且每组至少一行现金流；基准价格/CAPEX/OPEX乘数必须被消费或限定为1；敏感性数值归一后不得重复；tie tolerance须finite且`>=0`。保留唯一经济真值、逐期折现和ordinal tie。
- [x] `validation/wp4-decision/` -- 删除基于test标签OLS生成的`calibration_intercept/calibration_slope`及一切同义字段；只发布train raw logistic模型与calibration logistic MLE，test仅计算冻结预测的proper score/可靠性/净收益。若保留描述诊断，必须明确test-only命名、可估计性并由oracle独立复算。
- [x] `validation/wp4-decision/` -- cluster bootstrap改为真正使用冻结seed的256次确定性可复现伪随机cluster重采样，保存每次索引；禁止`N^N`全枚举冒充seeded bootstrap，并为N/样本量设可行上限。oracle从seed/算法独立再生索引并逐replicate复算CI。
- [x] `validation/wp4-decision/` -- manifest冻结精确顶层schema、精确文件集合`{config.json,decision-contract.json,raw.json}`及精确四项source集合，拒绝缺失/新增/未知字段；publisher journal也使用temp+flush+atomic replace。
- [x] `validate-wp4.ps1 -SelfTest` -- 语义负例必须在隔离toy副本修改source config并直接调用生产runner，构造完整隔离root或显式跳过生产root但绝不跳语义验证；每例捕获stderr并匹配专属失败码。lineage-only使用仍唯一的替换身份；train-only应成功发布且模型系数/lineage改变。
- [x] `validate-wp4.ps1 -SelfTest` -- 精确/近似tie与反转属性顺序必须各自走生产runner并比较raw；manifest删/增成员和未知字段必须失败；原子故障注入覆盖temp flush后/replace前及replace路径，pointer只能是完整旧或完整新JSON；另保留独立root-drift测试。
- [x] `validation/wp4-decision/`、执行日志和签核 -- 重建完整manifest/双root；签核保持Pending直至UQ/资源地质/决策独立复核。
- [x] `validation/wp4-decision/` -- 以publisher私有持久事务登记/仅stage目录创建记录证明发布授权；journal公开字段哈希不得作为capability。恢复只能清理登记为本次未提交stage的目录，任何历史inactive版本即便伪造journal并按公开公式算出正确hash也不得删除。
- [x] `validation/wp4-decision/` -- 冻结raw完整递归exact schema：`draw_totals`行、四类summary、decision及其行动/敏感性、threshold_selection、reliability行、cluster_bootstrap及索引、decision_curve等所有嵌套对象均拒绝缺失/未知字段，validator与Python oracle双重检查。
- [x] `validation/wp4-decision/` -- 实现冻结nested-MC诊断：固定seed、同一行动集与common random numbers，输出每行动ENPV估计及MCSE；预算`N`与`2N`复用前N样本，报告有限MCSE、误差预算和best-action稳定性，并与精确枚举oracle比较。
- [x] `validation/wp4-decision/` -- AtomicJson失败路径清理tmp；备份只在确认replace成功后删除，失败时保留可恢复备份；生产端中间/最终经济量finite、敏感性InvariantCulture、replay ID门必须由直接负例确认。
- [x] `validate-wp4.ps1 -SelfTest` -- 增加正确重算公开hash的伪journal指向历史inactive仍拒绝且目录保留；为每类raw嵌套对象注入代表性unknown/missing字段；变异MCSE、CRN前缀、N/2N稳定性和精确枚举误差预算必须失败。
- [x] `validation/wp4-decision/`、执行日志和签核 -- 重建完整manifest/双root；签核保持Pending直至独立复核。
- [x] `validation/wp4-decision/` -- 将伪nested-MC替换为真正EVSI嵌套MC：外层从状态先验与`p(y|state)`共同抽取状态/调查观测，内层基于观测形成条件后验并在相同行动集上最大化条件ENPV；输出gross/net EVSI估计、MCSE及每观测行动选择。
- [x] `validation/wp4-decision/` -- 固定seed并在行动、N/2N预算间使用common random numbers；`2N`前缀严格复用`N`。预算须`2≤N≤上限`且`2N`不溢出；均值、离差、平方和、MCSE逐步finite；误差预算或N/2N/exact最优决策不稳定时在发布前拒绝。
- [x] `validation/wp4-decision/` -- 事务恢复覆盖stage移动到candidate后、pointer提交前崩溃：未提交candidate须安全清理；无有效journal的孤儿auth须清理。授权登记使用原子写并绑定仅由当前publisher创建的`.stage-*`，不得删除历史versions。
- [x] `validation/wp4-decision/` -- 补齐raw递归exact schema的`decision.sensitivity`完整键集和值；生产runner对replay `id/cluster_id`执行CanonicalId；Atomic测试断言tmp清理和replace失败backup保留/可恢复。
- [x] `validate-wp4.ps1`与Python oracle -- 独立复算真正EVSI nested-MC、CRN前缀、N/2N、gross/net EVSI MCSE与精确枚举误差；SelfTest变异外层观测、条件后验、行动最大化、敏感性字段、replay ID、MC预算/finite/publish gate、move后崩溃与孤儿auth。
- [x] `validation/wp4-decision/`、执行日志和签核 -- 重建完整manifest/双root；签核保持Pending直至第6轮独立复核。
- [x] `validation/wp4-decision/` -- 恢复路径对`versions/`永久只读，任何journal/auth内容均不得触发删除或改写历史/候选版本；未提交candidate保留为不可变孤儿并记录供人工清理，自动清理仅限专用staging根下严格命名的`.stage-*`与无主auth。
- [x] `validation/wp4-decision/` -- validator与Python oracle从config逐项重算全部折现率/价格/CAPEX/OPEX敏感性键和值；runner、validator、oracle共同要求replay row ID全局唯一且`id/cluster_id` canonical，增加有限值篡改与重复/空白/控制字符ID负例。
- [x] `validation/wp4-decision/` -- exact EVSI以容差检查并规范化`[0,EVPI]`边界；误差倍数冻结且乘积finite；MC预算降低至可行上限并预分配数组，发布前拒绝MCSE/误差预算/稳定性异常。
- [x] `validation/wp4-decision/` -- 启动时验证active pointer；损坏时仅从唯一匹配且完整可验证的backup原子恢复。SelfTest断言tmp清理、backup保留/恢复、move后孤儿版本不删除、公开字段可重算的journal/auth也不能影响`versions/`。
- [x] `validation/wp4-decision/`、执行日志和签核 -- 重建完整manifest/双root；签核保持Pending直至第7轮独立复核。
- [x] `validation/wp4-decision/` -- `stable`必须由N、2N与精确枚举的实际决策比较生成，禁止常量；发布前要求N/2N/exact最优行动一致，并由PS/Python分别复算。seed、基础预算、最大预算和误差倍数必须逐项绑定decision-contract；明确max约束基础预算N且同时要求`2N`不溢出/不超过独立总预算上限。
- [x] `validate-wp4.ps1 -SelfTest` -- 增加schema正确的v3 journal与匹配auth指向历史inactive版本，断言versions全成员哈希不变；增加N>max、2N上界、NaN/Infinity/乘积溢出误差倍数、row/cluster控制字符及稳定性计算变异。
- [x] `validation/wp4-decision/` -- CanonicalId拒绝前后空白并统一Unicode Form C；恢复顺序先依据有效journal和candidate判断提交状态，再考虑旧backup，防止已提交新版本被回滚；active有效后清理已确认无用的旧backup。
- [x] `validation/wp4-decision/` -- Python oracle从decision-contract读取并严格验证预算/seed/max/multiplier，不得硬编码漂移；PS/Python逐项复算敏感性与全局replay ID唯一性继续保持。
- [x] `validation/wp4-decision/`、执行日志和签核 -- 重建完整manifest/双root；签核保持Pending直至第8轮独立复核。
- [x] `validation/wp4-decision/` -- active无效时，必须先完成v3 journal exact schema、路径、auth、candidate manifest及全成员/source哈希验证，之后才能重建pointer；`ReadValidPointer`逐项核验manifest files/sources并要求pointer与manifest `run_instance_id`一致。
- [x] `validation/wp4-decision/` -- CanonicalId除trim/NFC外拒绝全部Unicode `Cc/Cf`类别（含U+0085、零宽和双向格式控制）；MC budget/max/total必须是精确整数类型/值，禁止隐式取整。
- [x] `validation/wp4-decision/` -- Python oracle显式要求MC multiplier、MCSE及其乘积finite；乘积溢出夹具只触发专属`nonfinite mc error budget`并精确匹配，不得以宽泛`mc`或其他稳定性失败计数。
- [x] `validate-wp4.ps1 -SelfTest` -- 构造active损坏+有效v3 journal/auth/candidate+唯一有效旧backup组合并断言candidate优先；增加前后空白、NFD、U+0085、零宽、双向控制row/cluster ID，以及非整数预算的生产负例。
- [x] `validation/wp4-decision/`、执行日志和签核 -- 重建完整manifest/双root；签核保持Pending直至第9轮独立复核。
- [x] `validation/wp4-decision/` -- `ReadValidPointer/ValidManifest`在active、backup和journal candidate路径均重算manifest所列全部files与当前sources实际哈希；要求`status=Passed`、evidence_class为合同值，并严格绑定`pointer.run_instance_id == manifest.run_instance_id == version_path basename`。
- [x] `validation/wp4-decision/` -- CanonicalId按Unicode scalar而非UTF-16单char遍历，拒绝BMP及补充平面的全部`Cc/Cf`；PS validator与Python oracle使用等价规则。
- [x] `validate-wp4.ps1 -SelfTest` -- 增加pointer run ID、manifest run ID/目录、status/evidence_class、active source实际哈希变异；增加U+E0001等astral Cf的row/cluster生产负例。
- [x] `validate-wp4.ps1 -SelfTest` -- 对预恢复分别变异v3 journal exact schema、auth绑定、candidate成员hash、source hash、manifest run ID，断言不得选candidate且仅在唯一完整backup存在时恢复backup。
- [x] `validation/wp4-decision/`、执行日志和签核 -- 重建完整manifest/双root；签核保持Pending直至第10轮独立复核。
- [x] `validate-wp4.ps1` -- 默认active路径对pointer执行exact schema，并在读取manifest后强制`pointer.run_instance_id == manifest.run_instance_id == version_path basename`；增加只篡改active pointer run ID后直接调用默认validator的负例。
- [x] `validate-wp4.ps1`与Python oracle -- 分别构造绕过runner的隔离输出/输入变异，使astral `Cf` row/cluster ID直接进入VCanonical与Python canonical检查，并匹配专属失败；证明三条实现路径独立覆盖Unicode scalar规则。
- [x] `validation/wp4-decision/`、执行日志和签核 -- 重建完整manifest/双root；签核保持Pending直至第11轮独立复核。
- [x] `validation/wp4-decision/` -- runner、PS validator和Python oracle对所有身份字段统一执行canonical：draw/chain/sample/ancestor/voxel/replay row/cluster均要求非空、trim不变、NFC、拒绝Unicode `Cc/Cf/Cs`；Python捕获normalization/编码异常。
- [x] `validation/wp4-decision/` -- pointer、journal、auth、manifest等恢复控制JSON在任何`ConvertFrom-Json`前用原始JSON枚举拒绝重复成员，并执行exact schema与scalar类型检查，避免解析器折叠差异。
- [x] `validate-wp4.ps1 -SelfTest` -- 绕过runner分别向PS validator/Python oracle注入draw/lineage/voxel的空白、NFD、astral Cf与孤立surrogate；对pointer/journal/auth/manifest各加重复键恢复负例并匹配专属错误。
- [x] `validation/wp4-decision/`、执行日志和签核 -- 重建完整manifest/双root；签核保持Pending直至第12轮独立复核。
- [x] `validation/wp4-decision/run-wp4-decision.ps1` -- 移除依赖JSON内最后一个`schema`值猜测kind的包装分派；每个pointer/journal/auth/manifest调用点显式传入固定kind，且在任何kind/schema判断前无条件递归WalkJson拒绝重复键。
- [x] `validate-wp4.ps1 -SelfTest` -- journal与auth分别增加重复`schema`且末值未知/非法的生产恢复负例，精确匹配duplicate错误并证明不会进入原生折叠解析。
- [x] `validation/wp4-decision/`、执行日志和签核 -- 重建完整manifest/双root；签核保持Pending直至第13轮独立复核。
- [x] `validation/wp4-decision/` -- lineage/replay ID采用结构化比较或禁止全部控制分隔符；每draw至少一个voxel。所有中间乘加与最终NPV/ENPV/EVPI/EVSI须finite，敏感性键使用InvariantCulture。
- [x] `validation/wp4-decision/` -- 每条cashflow冻结精确8字段`{t,revenue,implementation_cost,failure_loss,capex,opex,tax,salvage}`、类型及重复时点规则，拒绝缺失/未知字段；`time_unit`精确限定`year`。raw及`raw.replay`冻结exact schema，拒绝任何未声明test-label拟合诊断。
- [x] `validation/wp4-decision/` -- replay row/cluster ID非空canonical；阈值保存calibration候选、选择准则和最优值并由oracle复算，不能仅凭`threshold_selected_on`声明。
- [x] `validation/wp4-decision/` -- journal绑定事务nonce/capability、目标manifest与本次新建staging身份；恢复不得删除任何历史inactive版本。active已成功指向同一目标时验证完整性后仅清journal；临时/备份只在确认提交后清理。
- [x] `validate-wp4.ps1 -SelfTest` -- 增加cashflow缺/增字段、重复时点、time_unit、空voxel、分隔符ID、溢出、raw replay未知字段、阈值血缘负例，均走生产runner并匹配专属错误。
- [x] `validate-wp4.ps1 -SelfTest` -- 覆盖pointer真实替换完成后/journal删除前崩溃并恢复、伪journal指向历史inactive不得删、最小可注入RootEvidence成员漂移；验证旧或新pointer均为完整JSON。
- [x] `validation/wp4-decision/`、执行日志和签核 -- 重建完整manifest/双root；签核保持Pending直至UQ/资源地质/决策独立复核。

**Acceptance Criteria:**
- Given 相关体素的联合draw, when 计算情景, then 逐draw直接复算一致且`q0.10≤q0.50≤q0.90`，打乱draw关联必须被拒绝。
- Given 同一状态/行动/货币时点, when 精确枚举, then `0≤EVSI≤EVPI`、净EVSI只扣一次调查成本且MC实现落入误差预算。
- Given 冻结回放split, when test评估, then 概率严格在`[0,1]`并输出proper scores、可靠性与treat-all/none对照净收益。
- Given 缺少合规资源输入或签署, when 发布结果, then 正式资源量/储量名称被阻断且仅保留靶体潜力情景。
- Given 默认验证与SelfTest, when 从生产入口运行, then 签核后均返回0，任一合同、raw、split、成本或发布证据漂移返回非0。

## Spec Change Log

- 回环1：三层复审证明初版只检查分位数顺序、合法行动枚举和bootstrap元数据，未复算具体值；校准斜率误用OLS，决策toy未执行逐期现金流，空间draw也未冻结共同voxel集合/lineage，文档仍残留可采资源量和孔数升级措辞。任务现钉死12个加权分位数、argmax tie规则、逐期NPV、logistic MLE、固定cluster重采样、association-shuffle与禁式扫描，避免静态摘要自洽即PASS。KEEP：保留已正确建立的四类情景量、P90=q0.10语义、R_total降级、train/calibration/test隔离及不可变发布骨架。
- 回环2：三层复审证明共同sample lineage仍未落盘，声明的ordinal平局规则未执行，旧静态行动收益表与逐期现金流形成双重经济真值，且train数据没有参与raw概率模型训练；同时发现比例上界、调查成本、敏感性、阈值/bin、可重复cluster、非4-cluster bootstrap及原子指针的边界缺口，文档仍有储量/自动升级残句。任务现冻结显式链/样本/祖先身份、唯一现金流合同、容差内ordinal平局、严格train→calibration→test派生链及完整边界负例，避免“字段存在但未消费”和双实现共同自洽即PASS。KEEP：保留回环1已正确实现的12个分位数独立复算、逐期折现与四类敏感性、状态/似然归一、MLE可估计性、固定256组bootstrap索引与CI独立复算，以及安全发布双root框架。
- 回环3：复审发现语义SelfTest会先被生产root漂移拦截且只检查非零退出，未证明生产runner对应门生效；残留test-OLS“校准”字段、非精确manifest和未消费seed的`N^N`全枚举也形成伪证据。任务现要求隔离调用生产runner并匹配专属错误、删除test拟合字段、冻结manifest exact schema、实施真正seeded 256次cluster bootstrap，并补齐身份、现金流集合与原子窗口边界。避免validator镜像自证、任意错误算caught及同步漏成员后重算root仍PASS。KEEP：保留回环2已正确的显式lineage、唯一经济合同、train→calibration→test主链、容差ordinal tie、12分位数/现金流/EVSI复算、同split重复cluster与动态N支持。
- 回环4：复审发现cashflow行与raw replay仍非exact schema，缺失经济字段可静默当零、同义test-OLS可回流；active提交后journal未删会永久阻塞，伪journal还能删除历史inactive版本，原子夹具也未覆盖提交后窗口。任务现冻结逐行schema/阈值选择血缘与数值边界，引入事务capability和提交后恢复，并以生产runner及最小RootEvidence负例覆盖。避免“安全路径即删除授权”、前置注入冒充真实提交窗口及未知字段逃逸。KEEP：保留回环3正确的生产runner专属错误测试、exact manifest、seeded256独立bootstrap、删除test-OLS、train/calibration/test、tie与双root。
- 回环5：最终复审证明公开journal字段的SHA256可被攻击者重算，仍能删除历史inactive；raw exact仅覆盖部分对象；冻结设计要求的nested-MC、MCSE、CRN与N/2N稳定性完全缺失。任务现改用可持久验证的私有stage授权，冻结raw全递归schema，并实现与精确枚举对照的MC诊断及变异测试。避免公开摘要冒充capability、局部schema冒充完整合同、精确枚举掩盖MC实现缺席。KEEP：保留回环4正确的cashflow exact行、阈值独立oracle、seeded bootstrap、post-pointer恢复、RootEvidence最小漂移及文档禁式。
- 回环6（用户明确批准突破五轮上限）：终审证明回环5的`nested_mc`只估计各行动先验ENPV，没有外层调查观测、条件后验行动最大化或EVSI MCSE；另有move后未提交candidate、孤儿auth、sensitivity schema、replay canonical ID和Atomic证据缺口。任务现实现真正双层EVSI MC及发布前稳定性门，并补齐事务和验证。避免把普通prior Monte Carlo冒充nested EVSI、验证后才发现不稳定结果，以及未提交版本/授权垃圾累积。KEEP：保留回环5正确的v3不删除历史versions、raw大部分递归schema、MC CRN基础设施、exact oracle、阈值/资源/双root证据链。
- 回环7（用户再次明确批准）：终审确认真正EVSI MC已正确，但普通JSON授权仍可被构造并诱导恢复删除历史非active版本；敏感性值未独立复算、replay ID唯一性及若干边界证据不足。任务现将恢复对`versions/`改为绝对只读，以不可变孤儿换取零误删，并补齐双端数值重算、ID、MC与backup恢复门。避免继续追求伪“不可伪造”本地JSON授权，以及schema存在即冒充数值正确。KEEP：保留回环6正确的state+y联合抽样、条件后验行动最大化、gross/net EVSI MCSE、N/2N CRN、exact误差对照及主要事务故障夹具。
- 回环8（用户批准）：终审发现`stable`仍为常量、Python oracle的MC上限硬编码为100000而合同为10000，且v3历史保护、MC极值和控制字符ID负例不完整；恢复顺序还可能把已提交新指针回滚到旧backup。任务现要求真实决策稳定性、所有MC参数合同绑定、有效v3不变性夹具、canonical Unicode及journal优先恢复。避免静态PASS字段、独立oracle合同漂移与旧备份错误回滚。KEEP：保留回环7正确的versions绝对只读、敏感性全值双端复算、replay基础门、EVSI边界/预分配及唯一backup恢复。
- 回环9（用户批准）：终审分歧中验证层确认恢复优先级缺组合证据、乘积溢出断言过宽、Python finite门不足；边界层发现journal在完整授权前即可重建pointer、pointer未核目标成员/run identity、Unicode不可见字符及非整数预算仍可漏过。任务现冻结完整预恢复验证、精确finite错误、Unicode Cc/Cf与整数合同，并补组合夹具。避免先写后验、宽泛失败冒充目标分支和隐式取整。KEEP：保留回环8真实stable、MC合同主绑定、v3历史哈希不变、versions只读与敏感性/EVSI主链。
- 回环10（用户批准）：终审证明普通active路径仍未重算source实际哈希，pointer/manifest/版本目录run identity未三方绑定，逐UTF-16 char的类别检查漏过astral Cf，预恢复也缺candidate损坏时回退backup的反向夹具。任务现统一所有pointer路径的完整manifest/source/run绑定，改用Unicode scalar分类并补逐类反向恢复测试。避免格式正确冒充内容正确、身份三元组分裂和代理对绕过。KEEP：保留回环9正确的完整v3正向恢复、整数/finite MC门、专属溢出错误、BMP Unicode与组合优先级。
- 回环11（用户批准）：终审确认生产runner已正确，但默认validator未绑定active/manifest/目录run ID，astral Cf夹具也只命中runner而未证明PS validator/Python oracle的独立scalar门。任务现只补默认validator身份断言及双独立Unicode负例。避免生产门正确掩盖独立验证回归。KEEP：保留回环10完整source/run生产绑定、Unicode scalar生产实现、预恢复反向矩阵与全部数值主链。
- 回环12（用户批准）：算法与验证层PASS后，Edge Hunter发现归档复验未对draw/lineage/voxel全面执行canonical，Python未拒绝孤立surrogate `Cs`，恢复控制JSON重复键仍可能被PowerShell折叠。任务现统一三实现全部身份字段规则，并在所有恢复JSON解析前拒绝重复键。避免生产拒绝但归档复验接受，以及解析器差异改变恢复语义。KEEP：保留回环11严格active pointer原始JSON矩阵、run三方绑定、astral Cf replay三路径证据及所有决策主链。
- 回环13（用户批准）：验证层复现journal/auth重复`schema`且末值非法时，包装器先按折叠后的schema猜kind，kind未知便跳过WalkJson并退回原生解析。任务现要求调用点显式kind、无条件先扫描重复键，并补两类专属负例。避免由不可信字段决定是否校验自身。KEEP：保留回环12统一身份canonical、其他控制JSON exact/scalar、完整SelfTest与全部决策/发布主链。

## Design Notes

资源情景至少分四类：体积`m³`、吨位`t`、原位含量（注明品位基准）、回收金属量`t`；禁止用同一`Q`名称掩盖量纲。若沿用矿业P90/P50/P10，必须同时发布明确分位点字段，固定`P90=q0.10`、`P50=q0.50`、`P10=q0.90`。

最小决策toy采用二状态、三行动和二值调查。精确枚举是oracle；嵌套MC只作为被测实现，使用同一行动集和common random numbers，并报告MCSE与预算加倍决策稳定性。

## Verification

**Commands:**
- `pwsh -NoProfile -File ".../validate-wp4.ps1"` -- 默认合同、正式版本和独立签核通过。
- `pwsh -NoProfile -File ".../validate-wp4.ps1" -SelfTest` -- 联合样本、决策、校准、合规命名和发布故障正负例全部通过。

## Suggested Review Order

**决策与不确定性主线**

- 从生产入口理解联合情景、现金流、EVSI与nested-MC输出。
  [`run-wp4-decision.ps1:37`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp4-decision/run-wp4-decision.ps1#L37)

- 独立oracle复算身份、分位数、校准及决策合同。
  [`wp4-oracle.py:3`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp4-decision/oracle/wp4-oracle.py#L3)

**证据发布与恢复**

- 固定kind解析确保控制JSON先验拒绝重复与错型。
  [`run-wp4-decision.ps1:15`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp4-decision/run-wp4-decision.ps1#L15)

- Unicode scalar身份门统一所有draw、lineage、voxel与replay标识。
  [`run-wp4-decision.ps1:6`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp4-decision/run-wp4-decision.ps1#L6)

**验证与回归证据**

- 默认pointer入口绑定exact schema、版本身份与manifest证据。
  [`validate-wp4.ps1:7`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-wp4.ps1#L7)

- 完整SelfTest覆盖数值漂移、隔离、恢复与发布故障。
  [`validate-wp4.ps1:34`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-wp4.ps1#L34)
