---
title: 'WP3：地球物理公式与物性模型修正'
type: 'refactor'
created: '2026-07-18'
status: 'done'
review_loop_iteration: 5
baseline_commit: 'NO_VCS'
context:
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/修改计划03.md'
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/审查意见03.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-wp1-rewrite-joint-probability-uq-core.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-wp2-correct-numerical-inference-theory.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** TEM频—时域变换、CSAMT近区校正、WFEM装置定义和扩散近似仍不构成自洽观测算子；物性温压模型、固定深度/阈值及RTP/二维MT默认流程又违反适用条件，无法支撑可复算的联合反演。

**Approach:** 冻结复数、坐标、源—接收和单位约定，按“观测合同—物理算子—适用域—参考回归”重写电磁与岩石物理内容，并以独立解析/高精度oracle和故障夹具验证。

## Boundaries & Constraints

**Always:** 内部量统一SI；冻结时间因子、Fourier/Laplace、相位、坐标和极性约定；TEM从发射波形定义唯一接收量；CSAMT近/过渡区使用有限源全场；WFEM冻结一种规范装置且主反演使用复响应；扩散近似声明`σ/(ωε)`、`μ`、空气和边界条件；深度只作设计假设并由灵敏度/分辨率/后验DOI验收；物性模型标明校准域和不确定性。

**Ask First:** 若需改变WP1联合概率根、WP2诊断合同，选用另一WFEM规范装置，下载/引入外部闭源oracle，或开展真实矿区/高成本三维运行，暂停并请求批准。

**Never:** 不保留通用复数乘法近区校正；不把趋肤深度当严格探测深度或DOI；不把`T>T_C`的Curie–Weiss外推到`T<T_C`；不允许无界IP充电率或MPa/GPa混算；不默认RTP/二维MT；不把固定异常阈值直接映射矿体、品位或概率；不把解析toy标为Field-validated。

## I/O & Edge-Case Matrix

| 场景 | 输入/状态 | 预期行为 | 错误处理 |
|---|---|---|---|
| TEM | 阶跃/有限斜坡关断、冻结线圈与时窗 | 波形卷积后`B`或`dB/dt`/电压的极性、单位、渐近与参考一致 | 混用波形、接收量或`iω`符号时失败 |
| CSAMT/WFEM | 有限接地电偶极、复`E/H`或`ΔU/I` | 近—远区复响应可复算，派生视电阻率/相位一致 | 缺源几何、分量、频率或场区时拒绝 |
| 物性温压 | K、Pa、矿物/IP制式和校准域 | 有界参数、有效应力和磁性分支合法 | 单位缩放、越界或错误相态时失败 |
| 条件流程 | 剩磁/低磁纬/三维MT或区外阈值 | 切换替代解释、3D或校准分支 | 不满足诊断门不得发布默认结果 |

</frozen-after-approval>

## Code Map

- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/01-引言.md` -- 趋肤深度、场区与有效深度总口径。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/02-全方法深度融合的底层逻辑与理论总纲.md` -- Maxwell、TEM、CSAMT、WFEM算子与观测合同。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/06-合成数据验证方案与验收设计.md` -- 几何、噪声、DOI及物理回归场景。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录1-分矿种多方法融合定制化勘查模板.md` -- 深度/网格假设和概率阈值。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录11-分勘查阶段标准化操作手册.md` -- RTP、MT维性及采集质控分支。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录13-岩性物性参数统计数据库.md` -- 温度、磁性、有效应力和统计元数据。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录14-地质先验知识库.md` -- 区内标定、竞争解释和先验治理。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp3-physics/` -- 独立参考、合同、fixture和版本化结果。
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-wp3.ps1` -- 默认验证与SelfTest入口。

## Tasks & Acceptance

**Execution:**
- [x] `01-引言.md`、`02-...理论总纲.md` -- 删除被新合同取代的旧Maxwell/TEM/CSAMT/WFEM公式、经验百分比、`Π_near/Π_static`、未冻结装置系数及趋肤深度似然权重；验证器扫描全部禁式。
- [x] `附录13-...md` -- 所有机器温度仅用K（°C只可括注展示），Curie阈值与公式显式用绝对温度；以有界IP、Biot有效应力和分相磁性模型重写温压段，补LogNormal变换、样本条件和SPD相关要求。
- [x] `06-...md`、`附录1-...md`、`附录11-...md`、`附录14-...md` -- 逐表/逐流程标注Design assumption与发布门，不以文件末尾免责声明代替；加入噪声地板、竞争解释、RTP/MT诊断分支。
- [x] `validation/wp3-physics/` -- 用锁定的`empymod==2.6.0`建立第三方参考锚并保存版本、许可证、环境与源码/安装记录哈希；CSAMT/WFEM使用有限bipole直接计算复E/H或复电压，覆盖近/过渡/远区，远区必须趋近平面波半空间极限；当前未推导的手写E/H Green不得作为oracle。
- [x] `validation/wp3-physics/` -- TEM小环尺度不得独立配置：发射与接收尺度由冻结几何派生；仅有等效面积时唯一取`L=sqrt(A_eq/π)`（等效圆半径），适用门使用Tx/Rx两者最大值。若保留冗余尺度字段，必须与派生值一致，否则在任何empymod调用前非0拒绝；`ratio_max`必须有限正值。合法敏感性用电流/匝数改变矩，不通过面积与长度解耦。
- [x] `validation/wp3-physics/` -- 完整拒绝非有限/非正频率、电阻率、距离、时间、积分层级、退化/奇异几何、非法Biot/温度/布尔/维性枚举；journal恢复路径只允许受限version模式。为Curie–Weiss、RTP、2D MT和区内校准同时运行正/反分支。
- [x] `validate-wp3.ps1` -- 在启动第三方oracle前独立重算面积—尺度一致性、`δ_diff`和小环比值；直接OutputOverride超限/NaN阈值/面积长度错配均拒绝。补DC/MT有限正值及CSAMT/TEM/WFEM完整输入域门；继续覆盖逐case容差和全部发布故障。
- [x] `validation/wp3-physics/run-wp3-physics.ps1` -- journal恢复仅接受固定schema与安全version-id，解析后必须位于`versions/`根下才可清理；绝对路径、`..`、分隔符、未知字段或当前active目标均不得删除，并纳入SelfTest。
- [x] `validate-wp3.ps1` -- 删除公开`SignoffOverride`；只解析仓库内固定签核文件的唯一顶层状态，精确冻结有序13成员名，拒绝替换成员/重复状态/错root/version/manifest；状态标记必须与相关表/流程局部绑定而非只计数。
- [x] `validation/wp3-physics/` -- 复用WP2同级发布结构，且上述发布故障测试必须作为`-SelfTest`注册执行，而非手工旁证。
- [x] `修改计划03-执行日志.md`及签核产物 -- 重建13成员根；签核文件必须记录并由validator重算“成员清单内容根”和“根清单文件SHA-256”两个不同字段，PASS签核的root不匹配必须失败。

**Acceptance Criteria:**
- Given 冻结的时间/坐标约定，when 运行TEM、CSAMT、WFEM回归，then 复响应、派生量、极性、单位和收敛均在预注册容差内。
- Given `σ/(ωε)`不足、空气域或边界异常，when 请求扩散算子，then 验证器拒绝或强制全Maxwell分支。
- Given 温压、磁性和IP边界fixture，when 执行模型，then `0<m<1`、`τ>0`、压力同量纲且Curie–Weiss不跨域。
- Given 剩磁、低磁纬、3D/各向异性或竞争岩性，when 执行流程门，then RTP、二维MT和固定阈值不得无条件发布。
- Given 默认验证与SelfTest，when 从干净入口独立运行，then 均返回0且任一合同漂移、单位缩放、符号反转或oracle篡改均返回非0。

## Spec Change Log

- 回环1：三层复审证明初版runner使用手填幂律/常数与硬编码收敛数组，未实现TEM波形、有限源CSAMT或ABMN-WFEM；validator相信runner自报误差，发布/签核根亦不闭合。任务现明确要求全输入驱动物理核、独立可运行oracle、逐点raw复响应、真实离散、数值域/决策分支、WP2同级发布故障测试及完整签核输入根，避免“字段夹具自洽即PASS”。KEEP：保留已正确写入的唯一`e^{+iωt}`约定、全Maxwell/扩散门、有界IP、分相磁性、Biot有效应力、RTP/MT条件分支与`Synthetic-run/Reference-regression`证据边界。
- 回环2：独立复签发现CSAMT用平面波阻抗从E反推H、近远距派生量恒定，TEM/CSAMT/WFEM的runner与oracle仍共享Green路径，低导电比仅改标签，发布故障也未注册进SelfTest；附录13仍混用°C/K，签核根字段语义含混。规格现钉死E/H直接有限源积分、不同数值算法的oracle、TEM不同路径、WFEM有符号ABMN因子、扩散核调用前拒绝、故障测试注册及双root字段，避免“同源双方同错”和标签式分支。KEEP：保留回环1完成的旧式删除、28个段内状态门、全raw结构、数值物性/决策分支及不可变发布骨架。
- 回环3：最终闭包审查证明回环2的手写CSAMT/WFEM E/H核仍无独立物理锚、远区结果严重偏离100 Ωm半空间，TEM未门平均且oracle仅等价改写同一幂律；同时存在签核override、宽松状态匹配、正分支/合法参数敏感性未执行及多项非有限输入缺口。现以锁定开源`empymod==2.6.0`作为第三方有限bipole/时域参考，要求远区极限、门平均、两套合法配置、全域拒绝、固定签核入口和精确成员集，避免继续以自写双方一致代替物理正确性。KEEP：保留回环2已通过的K/Pa物性合同、低导电比核前拒绝、有符号ABMN、隔离发布故障fixture、双root与pre/post pointer自洽语义。
- 回环4：独立地球物理签核发现TEM的`msrc='b'/mrec='b'`实现是面积/匝数缩放的磁偶极，而非此前声称的有限真实线环；逐case容差来源仍残留旧oracle描述。规格现明确小环磁偶极近似及`L_loop/δ_diff(t_min)`适用门，超限拒绝，并硬门当前empymod DLF/QWE、Gauss门平均与极限/不变量容差来源，避免装置过度声明和过期证据解释。KEEP：保留第三方CSAMT远区/WFEM交叉、TEM门平均/晚时斜率、合法敏感性、全edge、固定签核入口和发布故障闭包。
- 回环5：最终验证缺口审查复现面积与独立特征长度解耦可绕过小环门（30000 m²面积仍用56.42 m尺度而错误通过）；同时发现validator在域门前启动oracle、非有限阈值/DC/MT输入及journal越界路径缺口。规格现唯一定义`L=sqrt(A_eq/π)`并取Tx/Rx最大值，禁止不一致冗余覆盖，要求validator前置门、全数值域拒绝和受限journal清理，避免越域大环被当作小磁偶极以及恢复路径越界。KEEP：保留回环4的近似命名、0.15门、第三方参考、逐case容差、固定签核和全部既有物理/发布证据。

## Design Notes

规范WFEM首选：沿`+x`的有限长接地水平电偶极源，`z`向下；地表轴向电偶极接收`ΔU/I`（或等价`E_x/I`），记录复响应，装置端点、源矩、接收偶极、源中距、频率和相位基准全部进入manifest。视电阻率与相位仅作为可复算派生量。

参考回归只声明`Synthetic-run/Reference-regression`。DC/MT闭式继续独立复算；TEM、CSAMT、WFEM的权威交叉参考固定为`empymod==2.6.0`，至少使用两种官方支持的变换/精度设置进行内部一致性检查，并与独立极限/不变量联合验收。第三方参考不等于现场验证或生产三维求解器。

## Verification

**Commands:**
- `pwsh -NoProfile -File ".../validate-wp3.ps1"` -- 默认合同、文档和正式版本通过。
- `pwsh -NoProfile -File ".../validate-wp3.ps1" -SelfTest` -- 正例及单位、符号、边界、合同漂移和发布故障负例全部通过。

## Suggested Review Order

**物理合同**

- 先看唯一电磁约定、TEM小环边界和有限源装置。
  [`02-全方法深度融合的底层逻辑与理论总纲.md:820`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/02-全方法深度融合的底层逻辑与理论总纲.md#L820)

- 再看温度、IP与Biot有效应力的SI合同。
  [`附录13-岩性物性参数统计数据库.md:184`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录13-岩性物性参数统计数据库.md#L184)

- 检查RTP和MT维性条件分支。
  [`附录11-分勘查阶段标准化操作手册.md:440`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/附录11-分勘查阶段标准化操作手册.md#L440)

**参考实现与门禁**

- 第三方有限bipole和TEM门平均参考从这里进入。
  [`empymod-frequency-oracle.py:19`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp3-physics/oracle/empymod-frequency-oracle.py#L19)

- runner在调用第三方求解器前执行物理域门。
  [`run-wp3-physics.ps1:29`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/wp3-physics/run-wp3-physics.ps1#L29)

- validator重算面积、扩散长度、复响应和签核根。
  [`validate-wp3.ps1:33`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-wp3.ps1#L33)

**证据与交付**

- 最终独立双签绑定固定版本和双root。
  [`WP3-地球物理与岩石物理独立签核.md:3`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/WP3-地球物理与岩石物理独立签核.md#L3)

- 执行日志记录五轮回环和最终门状态。
  [`修改计划03-执行日志.md:250`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/修改计划03-执行日志.md#L250)
