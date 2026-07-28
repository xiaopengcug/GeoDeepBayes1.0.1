---
title: 'WP8 九类方法可行性与正式验证'
type: 'feature'
created: '2026-07-24'
status: 'done'
baseline_commit: '50e25166f8897f0fc6e82cbadbc3c4f0a98c14d5'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/wp8&wp9执行计划.md'
  - '{project-root}/_bmad-output/planning-artifacts/research/open-data/00_catalog/open_geophysics_data_manifest.json'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 当前 WP8 只有公开数据文件/格式审计以及重力、磁法两个标量算子的单元证据；九类方法尚无统一运行接口、许可与源—接收合同审计、有效 cluster/功效/维度门、合成证据和一次性现场 test 证据，不能升级为 `Field-validated`。

**Approach:** 先建立 fail-closed 的 WP8-0 可行性门并冻结数据、设计和求解路径。经 2026-07-26 人类重新协商，WP8-0 未全通过时可以风险接受方式启动 WP8-1 实现与合成开发轨，但不得解封正式现场 test、生成 `Field-validated` 或启动 WP9；正式现场预测验证仍须九类全部通过。

## Boundaries & Constraints

**Always:** 全九类通过；原始数据只读且派生物保留成员哈希和转换血缘；数据集只按许可、完整性和设计适配性选择；cluster 是功效与推断单位；正式 test 仅解封一次；MT/CSAMT/WFEM 使用保留实虚相关性的复协方差似然；`Field-validated` 必须绑定 `validation_assertion=field_prediction_verified` 及数据集、观测量、维度、范围和同信息等算力基线；许可未明确的数据仅限本地可行性检查，许可解决前不得生成可发布现场证据或绑定 `Field-validated`；失败包不可变；所有数值、状态和主张由 validator 从原始预测与配置重算。

**Ask First:** 申请澄清或补齐数据许可、新下载/替换公开数据、外部算力或改变已冻结预注册版本。

**Never:** 用 synthetic/open-data 格式检查冒充现场验证；冻结数据与 split 前查看正式 test 终点；依据测试结果选集，或结果不利后更换数据、基线、阈值、split、维度或噪声模型；以频点/时道/重复观测虚增 cluster；把复数实部/虚部当作相互独立误差或独立 cluster；从意向分析删除不利的预注册 test cluster；插值或纯数据拟合替代缺失的源—接收物理合同；让 CSAMT/WFEM 互为独立参考或使用相同 Maxwell 核生成参考；将现场观测预测外推为地下模型、资源量、矿体命中或经济价值正确；纳入地震数据。

**Completion policy:** WP8 采用 synthetic-validation completion。野外数据可得性和现场功效门不得阻断 WP8-1、WP8 completion 或 WP9 start；现场审计继续独立报告真实状态，且 synthetic completion 永远不得标注为 `Field-validated`。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| WP8-0 全通过 | 九类许可、完整性、元数据、cluster、功效、维度、求解路径均充分 | 冻结预注册版本并允许 WP8-1 正式现场轨 | 任何单项不足均不得放行正式现场轨 |
| 风险接受开发启动 | WP8-0 未全通过，但人类明确接受逐项登记的缺口 | 仅启动 WP8-1 实现、合成验证和训练区功效工作 | 保留失败判定；禁止正式 test 解封、`Field-validated`、WP8 完成和 WP9 启动 |
| 合成数据补充 | SIP/FDIP、CSAMT、WFEM 的现场数据门不足 | 生成显式标注 `synthetic-substitute` 的合同完整 cohort，用于接口、算子、规模、维度和统计流程验证 | `field_validation_eligible=false`；不得关闭现场数据、现场功效或 `Field-validated` 缺口 |
| 数据合同不足 | SIP/FDIP、CSAMT 或 WFEM 缺源—接收元数据 | 方法及 WP8-0 标记 Failed/Blocked | 不生成现场证据，不静默补值 |
| 维度升级 | 诊断指示当前求解维度不足 | 升级到诊断要求的维度并重新验证 | 无可行高维路径则该类 WP8-0 Failed |
| 正式验证通过 | 九类 test 指标和所有治理门均通过 | 九条限定范围的 Field-validated capability | validator 重算不一致即失败 |
| 正式验证失败 | 任一求解失败、统计门失败或证据被篡改 | WP8 保持 In progress，保留失败包 | 新版本必须使用未查看 test 或独立数据 |

</frozen-after-approval>

## Code Map

- `src/geodeepbayes/forward/` -- 统一算子协议及九类物理实现；现有 gravity/magnetic 需兼容升级。
- `src/geodeepbayes/data/` -- `ObservationSet`、只读 adapter、单位/CRS/复数协方差与血缘。
- `src/geodeepbayes/validation/` -- scenario/result、cluster split、功效、指标及复算逻辑。
- `_bmad-output/.../validation/wp8/` -- 数据登记、冻结根、预注册、运行包、validator 与 SelfTest。
- `_bmad-output/.../contracts/` -- 数据、能力及 evidence-run schema/registry。
- `tests/{forward,data,validation}/` -- 接口、物理、统计、泄漏与篡改负测。

## Tasks & Acceptance

**Execution:**
- [x] `validation/wp8/contracts/`、`validation/wp8/synthetic/` -- 冻结九类 synthetic generator、参数范围、单位、几何、频时、误差、随机种子、成员 SHA-256 与用途边界；现场数据目录继续作为非阻断审计轨，禁止依据 test 结果换生成器、种子或阈值。
- [x] `src/geodeepbayes/data/`、`validation/wp8/synthetic/` -- 实现不可变 ObservationSet 与合成补充规范化工件；NaN、坏道、异常点、复数堆叠和协方差均显式验证；SIP/FDIP、CSAMT、WFEM 各冻结 500 cluster 的合同完整补充。
- [x] `src/geodeepbayes/validation/feasibility.py`、`validation/wp8/synthetic/` -- 合成 train/calibration/test 固定为 100/100/300；冻结依赖、独立参考、维度、资源预算、SBC 与方法对抗，中央 validator 逐项语义重放并 fail-closed。
- [x] `src/geodeepbayes/forward/` -- 新增 `ForwardOperator` 元数据/`predict`/`jvp`/`jtp` 合同及磁矢量、DC、TDIP、SIP/FDIP、TEM、MT/AMT、CSAMT、WFEM 路径；CSAMT/WFEM 共享 Maxwell 核但 survey、源型、分量、视电阻率合同独立。
- [x] `tests/forward/`、`validation/wp8/synthetic/` -- 九类完成独立正向参考、可预测、错设失败、伴随/Taylor/有限差分、三级收敛、方法特定对抗、≥400 SBC 与类内 5×5 性能验证；中央证据拒绝方法身份串线和语义篡改。
- [x] `validation/wp8/synthetic/supplements-v1/` -- 为 SIP/FDIP、CSAMT、WFEM 生成首版合同完整合成补充；每类 500 个独立 clusters、16 个频率和 100/100/300 train/calibration/test split，包含源、接收、电流、复响应、误差、哈希与血缘，并强制 `field_validation_eligible=false`。
- [x] `src/geodeepbayes/validation/metrics.py`、`validation/wp8/synthetic/` -- 实现 cluster-level CRPS、覆盖 TOST、paired improvement、Brier、锐度与 PIT；冻结同信息等算力规则、阈值、种子和一次性 synthetic test，全部预注册 cluster 进入分析。
- [x] `validation/wp8/build_synthetic_completion.py`、`validation/wp8/validate_wp8.py` -- 九类 capability 绑定 unit/synthetic run；完成配置、生成器、预测语义、split、状态、成员根和篡改负例独立复算；completion artifact 原子写入并明确 `Synthetic-validated`、`field_validated=false`、`wp9_start_allowed=true`。

**Acceptance Criteria:**
- Given 九类候选数据，when 运行 WP8-0 validator，then 每类必须在单侧 α=0.05、功效≥80% 下可检测 CRPS≥10% 相对改善并支持覆盖率±5pp 等效性，且许可、合同、cluster、所需维度与求解路径全部充分；任一项不足即该类 Failed、正式现场轨不启动、原因机器可读且失败证据保留。人类风险接受只可启动实现/合成开发轨，且必须保留失败判定和缺口记录。
- Given 九类 WP8-0 全通过，when 运行合成套件，then 每类独立参考、导数、收敛、错设、SBC、对抗与类内性能证据全部通过。
- Given 冻结的九类现场 test，when 正式运行一次，then 每类 CRPS 相对同信息等算力基线改善至少 10% 且单侧 95% 界支持改善，90%/95% 覆盖均通过 ±5pp 等效性，所有预注册 cluster 进入意向分析且无未处理求解失败。
- Given 完整 WP8 包，when 独立 validator 与 SelfTest 运行，then 九类限定范围 capability 可复算通过，成功包和失败包的任一受保护成员或签核变更均被拒绝。

## Spec Change Log

- 2026-07-24：依据 Claude CLI 独立审查修订 6 项 Major 与 7 项 Minor；补齐 WP8-0 统计功效阈值、同信息等算力基线、复协方差、许可硬门、维度升级、CSAMT/WFEM 独立参考，以及 test 泄漏、ITT、bootstrap、失败包篡改和性能比较边界，避免错误放行与统计伪重复。
- 2026-07-26：用户明确重新协商启动门；登记三类正式缺口并以风险接受方式启动 WP8-1 实现/合成开发轨。WP8-0 的 6/9 失败结果保持不变，正式现场 test、`Field-validated`、WP8 完成和 WP9 继续阻断。
- 2026-07-26：用户授权使用合成数据补充缺项；新增 SIP/FDIP、CSAMT、WFEM 合成 cohort 与隔离约束。合成数据补齐开发/合成覆盖，不替代现场证据。
- 2026-07-26：完成九方法 development-only 合成验证与四轮对抗审查；加入算子身份、导数、收敛、方法特定 sanity、27 重检校正的标量参考 rank test、环境限定性能 smoke、证据重放及敌意载荷 fail-closed 检查。全量测试 246 passed、1 skipped；synthetic 轨通过，正式可行性仍为 6/9，field 轨继续阻断。
- 2026-07-26：完成首批 field-validation scaffold：扩充不可变 ObservationSet/adapter 合同，加入精确 cluster 随机化、bootstrap 稳定门、强制维度升级决策、九类似然登记、ITT cluster 指标复算、冻结 field 预注册 schema/blocked 工件及篡改负测。全量测试 255 passed、1 skipped；field CLI 以 `WP8_0_NOT_ALL_NINE_PASSED` 退出 4，未创建现场声明。
- 2026-07-26：完成 scaffold 对抗审查整改：收紧非有限值、PSD 协方差、受控源退化几何、资源/维度诊断、确定性缓冲分割与 bootstrap 边界；通过 producer/hash/measurements/thresholds 绑定 feasibility gate，独立锚定 field schema/payload，并把现场预注册绑定至受保护的实际 WP8-0 决策。全量测试 263 passed、1 skipped；synthetic CLI passed；field CLI 仍以 `WP8_0_NOT_ALL_NINE_PASSED` 阻断且未创建现场声明。
- 2026-07-26：完成第二轮安全边界整改：feasibility gate 绑定受信 producer 与预期 method/gate/dataset，递归拒绝非有限证据并校验三类顶层资产锚；adapter 与 field audit 均改为一次读取、同字节哈希和解析，阻断 ABA/TOCTOU；bootstrap 改用递增 B 的点估计、SE 与区间分位数收敛门；缓冲分割增加非空目标和搜索资源上限。全量测试 271 passed、1 skipped；synthetic exit 0；field 以 `WP8_0_NOT_ALL_NINE_PASSED` exit 4。
- 2026-07-26：最终授权边界明确区分结构评估与权威重放：SHA-256 只证明完整性、不证明 producer 身份；field audit 在同一进程由受保护原始资产 live 重建 feasibility，并要求完整 decision bytes 与冻结决定一致。完整自签 9/9 与同步脚手架仍被 live replay 阻断；snapshot、相关分析和距离矩阵增加前置资源上限。全量测试 276 passed、1 skipped；synthetic exit 0；field live replay 后以 `WP8_0_NOT_ALL_NINE_PASSED` exit 4。
- 2026-07-26：live replay 不再信任派生 field-contract audit：从原始成员现场重算并仅将冻结派生文件用于一致性比对；权威重放移入可终止子进程，设置 180 秒硬超时、512 MiB 输入/峰值预算。adapter snapshot 改为逐块累计预算，split 改用 `pdist` 并在分配前检查预计内存。全量测试 276 passed、1 skipped；真实 field replay exit 4。
- 2026-07-26：权威 worker 增加 OS 级 512 MiB 内存硬限制：Windows 使用 Job Object 的 process-memory 与 kill-on-close，非 Windows 使用 `RLIMIT_AS`；父进程以 Popen 强制 180 秒 timeout/kill，OOM 与非零退出统一阻断。原始 field audit 输入预算覆盖文件字节与 ZIP 展开成员；新增 timeout、exit 137 和资源等值边界负测。全量测试 278 passed、1 skipped；真实 field 仍以 WP8-0 6/9 阻断。
- 2026-07-26：READY 握手纳入同一 180 秒总 deadline，并用后台线程/queue 防止 pre-READY 阻塞；Windows Job API 全部声明 64 位安全 argtypes/restype，成功 handle 在失败与完成路径均关闭。距离预算补齐 condensed、square float64、adjacency bool 与开销；增加 Popen timeout/kill/reap、非零退出和直接输入预算测试。全量测试 285 passed、1 skipped；真实 worker 135.9 秒。
- 2026-07-26：权威输入预算改为共享总额：先扣除 manifest、dataset selection、preregistration、冻结 field audit 与 schema，再将剩余额度传入原始 field-contract 重算；原始审计先枚举全部文件及 ZIP 展开元数据并完成预算验证，之后才读取 TDIP/header 内容。Job stdin 缺失及 write/flush 失败路径均 kill、reap 并关闭 handle。全量测试 285 passed、1 skipped；真实 field 93.9 秒。
- 2026-07-26：Windows Job 安装器抽为可注入单元；Create、Set、Assign 三阶段失败分别以专用错误 fail-closed，并验证 kill/reap、64 位 handle CloseHandle。stdin None/write/flush 与 POSIX `RLIMIT_AS` preexec 均有直接测试。全量测试 292 passed、1 skipped；真实 field 92 秒。
- 2026-07-26：field 输入预算改为严格两阶段：先仅 stat 汇总全部 raw bytes，超限时零 ZIP 探测；通过后才读取 central directory 并逐成员累计展开量，超限前不读 member/header 内容。Job cleanup 改为 kill、reap、CloseHandle 相互独立的 best-effort，清理异常不覆盖原始安装错误。全量测试 296 passed、1 skipped；真实 field 91.1 秒。
- 2026-07-26：获取并冻结 Mendeley heavy-metal SIP v2 公开场地包（185,002,317 bytes；84 members；provider SHA-256 一致），仅登记为 `permanently-training-only`。结构审计确认 3 个采集组、每组 3 频率×9 通道，但独立现场 cluster 上界仍为 1，故 `formal_status=blocked`、`field_validation_eligible=false`，不改变 WP8-0 6/9。两轮对抗审查后加入独立 provider anchors、完整 ZIP 安全重算、永久训练边界、不可变工件漂移保护和中央 validator 拒绝计入 Field 的断言；聚焦测试 22 passed。
- 2026-07-26：获取并冻结 OEDI Cymric FDEM 六成员（submission HTML、3 份现场 Ex 表、2 张配置图），作为 `permanently-training-only` 的 WFEM 合同映射候选。严格重算确认 Part 1 5 Hz 为 16×2 且无相位，Part 2 的 1/5 Hz 各为 63×3 且含相位；仍缺源电流、完整复响应、绝对源/接收几何与 geometric factor，且独立现场 cluster 上界为 1，因此明确 FDEM≠WFEM、`formal_status=blocked`、`field_validation_eligible=false`。对抗审查后固定六成员 URL/大小/SHA-256、精确结构与有限数值门、测试目录隔离和不可变漂移负测；Cymric+SIP 聚焦测试 38 passed。
- 2026-07-26：完成 Big Chino CSAMT 训练功效 readiness 权威协调。342 个训练站仅为 observations，响应按整线打包不构成独立性证据，21 条线同属一个现场，因此正式已证明独立 cluster 上界为 1；原 257 个 200 m station packing 声明标记为 `superseded_for_formal_gate`，15 仅为 sealed 打包线数量。审计固定 design/training/raw/inversion 四 SHA、完整 21-line 分区和零响应内容读取行为；paired evidence 仅接受显式受控 registry，当前不存在，故不计算 CRPS 且 cluster/power 均 blocked。中央 validator 绑定 readiness SHA 并逐字段拒绝矛盾/篡改状态；聚焦测试 46 passed、73 deselected，WP8-0 仍为 6/9。

## Dev Agent Record

### Debug Log

- 审计 Tasks & Acceptance、执行计划、公开数据 manifest 与当前实现，确认正演/合成切片已覆盖；本批选择无需新增下载或许可的公共数据合同、统计设计和 field fail-closed scaffold。
- MT EDI/XML 原始频率顺序可升可降，因此 ObservationSet 对频时轴执行“与数据对齐、有限、正值”验证，不擅自重排原始顺序。
- 正式现场 test 仍未解封；field scaffold 只验证冻结前置条件和机器可读阻断原因。

### Completion Notes

- ObservationSet 新增标准误差、dataset/license 状态及频时轴合同；DatasetAdapter 继续在读取前后复核原始成员 SHA-256，并保留 NaN/坏道。
- feasibility 新增小 cluster 精确配对符号随机化、bootstrap Monte Carlo 稳定门和方法维度升级 fail-closed 决策。
- field scaffold 登记九类误差结构，按预注册 cluster 重算 CRPS 与 90%/95% 覆盖，并强制全部 cluster 进入 ITT。
- 新增 observation/field preregistration JSON Schema、冻结 blocked 工件和 validator 篡改门。
- 对抗审查后，ObservationSet 递归冻结元数据并拒绝 Inf、非 PSD 协方差和标准误差冲突；受控源拒绝退化线段及非有限合同值；adapter 加入错误哈希和读中变更攻击测试。
- feasibility passed gate 现在必须绑定方法、数据集、producer/hash、measurements、thresholds 与可复算 evidence ID；field scaffold 独立锚定 schema/payload，绑定实际 decision/protected manifest，并验证恰好九种方法。
- gate producer 进一步改为由评估入口提供受信哈希锚，调用者无法自签；registration 顶层 manifest、dataset selection、preregistration 哈希均须匹配受信值。
- DatasetAdapter 和 field scaffold audit 对一次读取的 immutable bytes 同时执行哈希与解析，覆盖 ABA/TOCTOU；bootstrap 以 B/2、3B/4、B 的估计量、标准误及区间端点收敛决定稳定性。
- 最终全量测试 271 passed、1 skipped；synthetic CLI exit 0；field CLI exit 4，阻断原因保持 `WP8_0_NOT_ALL_NINE_PASSED`。
- `evaluate_feasibility` 明确只生成结构决策，digest 是完整性校验而非身份签名；正式 field 授权额外要求同进程权威 live replay 与冻结 decision 逐字节一致，外部身份签名不作为当前解封依赖。
- DatasetAdapter 增加单成员 128 MiB、总计 256 MiB snapshot 上限；相关长度在 O(n²) 工作前限制五百万 pairs，buffer split 在距离矩阵前限制 5,000 points。
- 最终全量测试 276 passed、1 skipped；validator/feasibility/data 定向复测 92 passed；synthetic CLI exit 0；field live replay 后 exit 4，原因 `WP8_0_NOT_ALL_NINE_PASSED`。
- field-contract 原始审计核心现为可调用纯函数；live 结果驱动 registration，冻结派生结果只作一致性比对。重放在独立 Python 子进程中执行，180 秒到期由父进程强制终止，任何超时、非对象或类型异常均 fail-closed。
- Snapshot 预算不再依赖预先 `stat`：逐块累计成员/总字节并在首次越界时拒绝；等于预算边界可通过。split 在分配前校验维数与预计距离内存，并以 condensed `pdist` 避免 `(n,n,d)` 张量。
- 最终全量测试 276 passed、1 skipped（包含真实伪 9/9 live replay 攻击）；真实 field CLI 经子进程重放后 exit 4，原因保持 `WP8_0_NOT_ALL_NINE_PASSED`。
- Windows authoritative worker 在科学依赖装载后进入 READY 握手，随后由父进程绑定 512 MiB Job Object，再开始受限重放；非 Windows 在 exec 前设置 512 MiB `RLIMIT_AS`。180 秒硬超时、OOM、非零退出均不能降级为授权。
- field-contract 输入预算同时累计所有实际文件大小和 ZIP 中各成员展开大小；真实伪 9/9 测试确认 worker 正常返回 failed decision，并以专用 `LIVE_REPLAY_MISMATCH` 阻断。
- 最终全量测试 278 passed、1 skipped；validator 定向 58 passed；真实 field CLI 在 OS 资源限制下 exit 4，原因 `WP8_0_NOT_ALL_NINE_PASSED`。
- READY 与 replay 共用单一单调时钟 deadline；pre-READY 和 communicate 任一阶段超时均 kill + reap。生产依赖 OS 级硬内存限制，tracemalloc 仅保留为显式可选二级诊断，不再称为硬预算。
- Job Object API 使用 `c_void_p` HANDLE 及显式 BOOL/DWORD 签名，避免 64 位句柄截断；所有创建成功的 Job handle 均在安装失败或 worker 完成后关闭。
- 最终 validator 定向 62 passed；全量 285 passed、1 skipped；真实 field worker 135.9 秒并 exit 4，阻断原因保持 `WP8_0_NOT_ALL_NINE_PASSED`。
- 权威 512 MiB 输入额度在 core 与 raw/expanded field members 间共享，杜绝两个独立预算相加超限；field-contract 在任何 header/content 读取前完成全量路径与 ZIP metadata 预算。
- Job 安装后 stdin None/write/flush、运行超时和普通完成均进入确定的 kill/reap/CloseHandle 路径。最终全量 285 passed、1 skipped；真实 field worker 93.9 秒，exit 4。
- 可注入 Job installer 直接覆盖 `WINDOWS_JOB_CREATE_FAILED`、`WINDOWS_JOB_SET_LIMIT_FAILED`、`WINDOWS_JOB_ASSIGN_FAILED`；POSIX 测试实际执行捕获的 preexec 并复核 `RLIMIT_AS=(512 MiB, 512 MiB)`。
- 最终全量 292 passed、1 skipped；真实 field worker 92 秒，exit 4，原因 `WP8_0_NOT_ALL_NINE_PASSED`。
- 两阶段预算测试证明 raw stat 超限时 `is_zipfile`/`ZipFile` 零调用，expanded 超限只读取 central directory；kill 或 reap 抛错时仍恰好关闭一次 Job handle，并保留原始 Set-limit 错误。
- 最终全量 296 passed、1 skipped；真实 field worker 91.1 秒，exit 4，原因 `WP8_0_NOT_ALL_NINE_PASSED`。
- 定向复测 83 passed，field/validator 复测 59 passed；全量测试 263 passed、1 skipped；synthetic CLI passed；feasibility CLI 诚实报告 6/9；field CLI 以 `WP8_0_NOT_ALL_NINE_PASSED` 阻断且未创建 `Field-validated`。
- Hualapai CSAMT v2 冻结 7 个 ScienceBase provider 文件与 2 个 API 元数据快照，严格复算 9 条原始/站点/MTM 线和 543 个站点；官方锚不足以证明独立 site 映射，因此全包永久限定为 training-only，正式功效贡献为 0。
- 历史 `csamt-line-split-v2.json` 保留不改以维持审计链；新增角色协调证据将其中已打开响应的 6 条旧 test 线标记为 `contaminated_and_superseded`，中央验证器拒绝把它们重新计为 sealed。
- Hualapai 三层敌意审查后的定向组合测试 152 passed；synthetic CLI exit 0；feasibility self-test 维持预期 exit 3（6/9）；protected manifest 与 active pointer 均完整。
- 2026-07-26：用户将 WP8 完成策略改为 synthetic-validation completion，明确禁止因缺少野外数据阻断。现场 6/9 继续作为非阻断审计事实；九类合成门通过后允许 WP8 completion 与 WP9 start，同时永久禁止把该结果标注为 `Field-validated`。
- 2026-07-26：生成并语义重放 `wp8-synthetic-completion-v1.json`，九类全部登记 `Synthetic-validated`，`wp8_complete=true`、`wp9_start_allowed=true`、`field_validated=false`；全量测试 398 passed、1 skipped，completion exit 0，protected manifest 与 active pointer 完整。WP8 完成并进入 WP9。

## File List

- `src/geodeepbayes/data/__init__.py`
- `src/geodeepbayes/data/observation.py`
- `src/geodeepbayes/validation/feasibility.py`
- `src/geodeepbayes/validation/field_scaffold.py`
- `validation/wp8/contracts/observation-set.schema.json`
- `validation/wp8/contracts/wp8-feasibility.schema.json`
- `validation/wp8/contracts/field-preregistration-scaffold.schema.json`
- `validation/wp8/field/preregistration-scaffold-v1.json`
- `validation/wp8/audit_field_contracts.py`
- `validation/wp8/validate_wp8.py`
- `validation/wp8/build_synthetic_completion.py`
- `validation/wp8/acquire_usgs_hualapai_csamt.py`
- `validation/wp8/audit_usgs_hualapai_csamt_contract.py`
- `validation/wp8/data/usgs-hualapai-csamt-v1/raw-manifest.json`
- `validation/wp8/evidence/feasibility-v1/usgs-hualapai-csamt-contract.json`
- `validation/wp8/evidence/feasibility-v1/hualapai-csamt-role-reconciliation-v1.json`
- `validation/wp8/evidence/feasibility-v1/wp8-1-method-synthetic-validation-v1.json`
- `validation/wp8/evidence/feasibility-v1/wp8-synthetic-completion-v1.json`
- `tests/data/test_observation.py`
- `tests/validation/test_feasibility.py`
- `tests/validation/test_field_scaffold.py`
- `tests/validation/test_wp8_resource_abort.py`
- `tests/validation/test_wp8_validator.py`
- `tests/validation/test_wp8_synthetic_completion.py`
- `tests/validation/test_usgs_hualapai_csamt_contract_v2.py`

## Design Notes

WP8-0 现场审计与 WP8-1 合成完成使用不同状态机：现场 `blocked/failed` 是诚实的声明范围限制，但不是 WP8 执行门。合成审计通过即可登记 WP8 synthetic completion 并启动 WP9；只有独立现场门通过后才可能产生 `Field-validated`。

## Verification

**Commands:**
- `uv run --frozen pytest -q` -- 全量测试通过。
- `uv run --frozen python validation/wp8/validate_wp8.py --phase feasibility --self-test` -- 从项目根运行；九类可行性门与负测一致。当前 WP8-0 诚实失败时预期退出码为 `3`。
- `uv run --frozen python validation/wp8/validate_wp8.py --phase synthetic` -- 从项目根运行；九类合成门通过时允许 WP8 completion 与 WP9 start，预期退出码为 `0`，不依赖现场 6/9 结果。
- `uv run --frozen python validation/wp8/validate_wp8.py --phase field --self-test` -- 从项目根运行；WP8-0 未通过时必须拒绝解封，预期退出码为 `4`。
- `pwsh -NoProfile -File validate-governance.ps1` -- 从项目根运行；既有治理契约无回归。

## Suggested Review Order

**正式门禁与权威重放**

- Field 入口只接受原始资产重放一致的冻结 decision。
  [`validate_wp8.py:4756`](../../validation/wp8/validate_wp8.py#L4756)

- 独立 worker 统一执行总时限与 OS 内存限制。
  [`validate_wp8.py:4668`](../../validation/wp8/validate_wp8.py#L4668)

- Windows Job Object 安装采用 64 位安全句柄和清理。
  [`validate_wp8.py:4598`](../../validation/wp8/validate_wp8.py#L4598)

**数据、统计与现场合同**

- Observation 容器冻结缺失、协方差、血缘和原始快照。
  [`observation.py:31`](../../src/geodeepbayes/data/observation.py#L31)

- Feasibility 结构决策绑定方法、数据集、gate 与资产锚。
  [`feasibility.py:143`](../../src/geodeepbayes/validation/feasibility.py#L143)

- Field 指标强制所有预注册 cluster 进入 ITT。
  [`field_scaffold.py:25`](../../src/geodeepbayes/validation/field_scaffold.py#L25)

- 原始合同审计先完成共享输入预算再读取内容。
  [`audit_field_contracts.py:112`](../../validation/wp8/audit_field_contracts.py#L112)

**敌意验证**

- 自签 9/9 必须被成功 live replay 明确否决。
  [`test_wp8_validator.py:333`](../../tests/validation/test_wp8_validator.py#L333)

- Job 安装各阶段失败均终止、回收并关闭句柄。
  [`test_wp8_validator.py:470`](../../tests/validation/test_wp8_validator.py#L470)

**SIP 永久训练候选**

- 入口冻结 provider 锚、ZIP 成员哈希及永久训练边界。
  [`acquire_mendeley_heavy_metal_sip.py:263`](../../validation/wp8/acquire_mendeley_heavy_metal_sip.py#L263)

- 合同审计严格重算 84/81/3 与 3×3×9 结构。
  [`audit_mendeley_heavy_metal_sip_training.py:63`](../../validation/wp8/audit_mendeley_heavy_metal_sip_training.py#L63)

- 中央门禁强制该训练包保持 Field-ineligible 与 blocked。
  [`validate_wp8.py:2094`](../../validation/wp8/validate_wp8.py#L2094)

- 负测覆盖边界冲突、来源漂移、双采集映射与不可变写入。
  [`test_acquire_mendeley_heavy_metal_sip.py:316`](../../tests/validation/test_acquire_mendeley_heavy_metal_sip.py#L316)

**WFEM 映射候选**

- 获取入口固定 Cymric 六成员 provider 身份与永久训练边界。
  [`acquire_oedi_cymric_wfem_mapping.py:1`](../../validation/wp8/acquire_oedi_cymric_wfem_mapping.py#L1)

- 审计严格解析三张数值表并拒绝 FDEM 冒充 WFEM。
  [`audit_oedi_cymric_wfem_mapping.py:1`](../../validation/wp8/audit_oedi_cymric_wfem_mapping.py#L1)

- 负测覆盖同步替换、缺成员、NaN、错列和不可变漂移。
  [`test_oedi_cymric_wfem_mapping.py:1`](../../tests/validation/test_oedi_cymric_wfem_mapping.py#L1)

**CSAMT 功效 readiness**

- 权威审计区分 observation、打包线与已证明 site-level cluster。
  [`audit_usgs_big_chino_csamt_training_power_readiness_v1.py:1`](../../validation/wp8/audit_usgs_big_chino_csamt_training_power_readiness_v1.py#L1)

- 中央门禁绑定 readiness 摘要并逐字段保持 cluster/power 阻断。
  [`validate_wp8.py:2663`](../../validation/wp8/validate_wp8.py#L2663)

- 测试验证生产 ZIP reader 零内容读取及 registry 正负路径。
  [`test_usgs_big_chino_csamt_power_readiness.py:1`](../../tests/validation/test_usgs_big_chino_csamt_power_readiness.py#L1)

**Hualapai CSAMT 训练合同与污染隔离**

- 获取入口固定全部 7 个 provider 文件和 2 个 API 快照，并在临时文件校验后原子落盘。
  [`acquire_usgs_hualapai_csamt.py:1`](../../validation/wp8/acquire_usgs_hualapai_csamt.py#L1)

- 合同审计逐线复算 9 条线、543 个站点和 MTM 几何字段，同时拒绝把 line 当作独立 site。
  [`audit_usgs_hualapai_csamt_contract.py:1`](../../validation/wp8/audit_usgs_hualapai_csamt_contract.py#L1)

- 角色协调证据隔离历史已开封 test 响应，中央门禁绑定合同、旧 split 与 reconciliation 哈希。
  [`hualapai-csamt-role-reconciliation-v1.json:1`](../../validation/wp8/evidence/feasibility-v1/hualapai-csamt-role-reconciliation-v1.json#L1)

- 负测覆盖 provider 漂移、ZIP 路径、MTM token/range、原子获取、旧 split 污染与中央篡改。
  [`test_usgs_hualapai_csamt_contract_v2.py:1`](../../tests/validation/test_usgs_hualapai_csamt_contract_v2.py#L1)
