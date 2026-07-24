---
title: 'WP5：文稿一致性与附录整改'
type: 'refactor'
created: '2026-07-19'
status: 'in-review'
review_loop_iteration: 28
baseline_commit: 'NO_VCS'
context:
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/修改计划03.md'
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/审查意见03.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-wp1-rewrite-joint-probability-uq-core.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-wp2-correct-numerical-inference-theory.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-wp3-correct-geophysical-rock-physics.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-wp4-rewrite-resource-risk-decision.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** WP1—WP4虽已分别冻结理论、物理、数值和决策合同，但00—07章及相关附录仍存在成果语气、PPC/覆盖率、资源命名、固定深度、诊断阈值、性能数字和占位代码的跨文档冲突，局部摘录可绕过篇首免责声明。

**Approach:** 按02→03→04→附录→05/06→00/01/07顺序直接整改正文，以机器合同统一状态、证据、术语、阈值来源和表结构，并建立独立validator及变异SelfTest阻断回归。

## Boundaries & Constraints

**Always:** WP1—WP4已签核公式与证据边界是规范源；量化主张就地绑定状态和Evidence/Run/manifest；区分PPC、SBC、参数覆盖、留出预测覆盖和代码覆盖；固定深度/分辨率注明装置、频时参数、物性、噪声、目标尺度及DOI条件；占位代码明确不可执行。

**Ask First:** 若需改变WP1—WP4冻结公式/机器合同、升级Field-validated或正式资源分类、引入新运行结果、删除整章/附录或改变项目定位，暂停并请求批准。

**Never:** 不用后置统一免责声明掩盖局部强主张；不把PPC包络命中率称校准覆盖；不把Planned数字写成Observed；不硬编码第二套Rhat/ESS/MCSE门；不把`pass/TODO`伪代码称已实现/已测试/生产；不恢复GPU、百万网格、五方法闭环、固定加速/收益或可采资源量主张。

## I/O & Edge-Case Matrix

| 场景 | 输入/状态 | 预期行为 | 错误处理 |
|---|---|---|---|
| 文稿主张 | 定量性能、经济、精度或深度句/表 | 就地声明状态、口径与证据引用 | 缺状态或证据时拒绝 |
| 统计术语 | PPC/SBC/coverage/diagnostic | 使用唯一分类与WP2诊断合同 | 混称或复制阈值时拒绝 |
| 代码能力 | 代码块含pass/TODO/未定义依赖 | 标为接口草案/不可执行伪代码 | 同段声称实现或测试时拒绝 |
| 合法模板 | 场景阈值或Design-assumption | 带scope/source ID且不冒充全局门 | 无作用域/来源时拒绝 |

</frozen-after-approval>

## Code Map

- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/00-摘要.md`、`01-引言.md`、`07-结论与展望.md` -- 最终能力边界与成果语气。
- `.../02-全方法深度融合的底层逻辑与理论总纲.md`、`03-多方法深度融合的核心技术实现路径.md`、`04-分场景多方法融合适配方案.md` -- 理论、统计和场景规范源。
- `.../05-工程化落地与效率优化方案.md`、`06-合成数据验证方案与验收设计.md` -- 工程能力、PPC/覆盖和伪代码高风险区。
- `.../附录1-...md`、`附录2-...md`、`附录3-...md`、`附录4-...md`、`附录5-...md`、`附录11-...md`、`附录13-...md`、`附录14-...md` -- 模板、性能、资源、物性与先验一致性。
- `.../validation/wp5-consistency/`、`.../validate-wp5.ps1` -- 机器合同、扫描结果、不可变证据与生产门。

## Tasks & Acceptance

**Execution:**
- [x] `02/03/04` -- 统一三类信息量、诊断合同、PPC/SBC/覆盖、联合draw、资源/风险和场景阈值语义；保留WP1—WP4规范段。
- [x] `附录1/2/3/4/5/11/13/14` -- 将固定阈值/深度/性能表改为带scope的Planned/Design-assumption；Observed必须绑定Evidence ID、Run ID与manifest。
- [x] `05/06`与算力说明 -- 删除无证据生产/加速/收益措辞；所有占位代码标不可执行；PPC不再承担覆盖率验收。
- [x] `00/01/07` -- 最后回写统一定位，仅声明理论草案、局部重磁原型、WP3参考回归与WP4 synthetic决策toy，不外推五方法/现场/资源分类能力。
- [x] `validation/wp5-consistency/` -- 建立16文档精确清单、状态枚举、section ID、主张字段、校准11字段、阈值source和规范公式ID机器合同。
- [x] `validate-wp5.ps1` -- 检查UTF-8、结构合同、证据绑定、禁式、哈希、active/manifest/双root与独立签核；SelfTest覆盖缺/增/重复字段、非法状态、Observed洗白、裸阈值、PPC混称、伪代码成果化和合法换序。
- [x] `修改计划03-执行日志.md`与WP5独立签核 -- 记录变更，签核在主编/技术编辑及四专项交叉复核前保持Pending。
- [x] 16篇目标文稿与算力说明 -- 每条定量/Observed/阈值主张使用结构化`WP5-CLAIM`就地记录；每个含pass/TODO/未定义依赖的代码块使用`WP5-CODE-BLOCK`记录，不得以篇首marker替代逐记录绑定。
- [x] `validation/wp5-consistency/consistency-contract.json` -- 冻结每个section ID的目标文档与gate、claim/code/calibration exact schema、五类校准术语、公式ID、阈值scope/source及禁止升级状态；逐字段被生产validator消费。
- [x] `validation/wp5-consistency/` publisher/scanner -- 逐句/逐段解析正式文稿中的主张、PPC/SBC/coverage、第二套Rhat/ESS/MCSE门和伪代码上下文；只有语义扫描成功后才能生成scan/manifest并原子发布active版本。
- [x] `validate-wp5.ps1` -- 对正式16篇逐记录调用语义门；manifest/scan/doc/source集合exact、路径受限、schema/section归属/root separator及签核字段结构化绑定，不允许一个合法绑定掩盖同文其它未绑定主张。
- [x] `validate-wp5.ps1 -SelfTest` -- 全部变异走隔离生产入口并匹配专属错误；覆盖逐主张洗白、反序/跨行统计混称、复制诊断门、场景阈值scope、跨行伪代码成果化、section迁移、scan/manifest/pointer/root/hash漂移及合法换序。
- [x] `validation/wp5-consistency/`与WP5签核 -- 加入锁、stage、temp+flush+atomic pointer、恢复与不可变版本；六角色签核使用exact结构逐项绑定最终version/manifest/双root。
- [x] 16篇文稿与算力说明 -- 移除统一治理占位的机械claim；直接修正`Coverage_PPC`/PPC passed阈值、三级/可采资源量输出、固定5000m能力、POD维缩=采样加速、正式资源升级和无证据收益/生产措辞；历史引用使用citation-specific Reference状态，明确撤销句不生成正向claim。
- [x] `validation/wp5-consistency/claim-ledger.json` -- 冻结每条有效主张/代码块的exact ID集与逐文档计数、doc、line span、规范化文本hash、claim_type、metric/formula/status、scope、source contract hash、evidence/run/manifest；禁止一条记录覆盖多段、无正文记录或成对删除。
- [x] `validation/wp5-consistency/consistency-contract.json` -- 读取并绑定WP1—WP4 active manifest、WP2 diagnostic/report合同实际hash；为diagnostics、三类IG、POD误差/留出、Green RJMCMC能力、五类校准及深度/资源语义定义专用规则，不以路径字符串自证。
- [x] scanner/validator -- 独立重算ledger文本hash、记录全集与语义规则；逐阈值验证真实scope/source，逐代码块解析fence跨度及相邻成果语气；scan状态只能由扫描结果派生，publisher不得硬编码Passed。
- [x] `validate-wp5.ps1 -SelfTest` -- 隔离生产入口覆盖错误Rhat-only/复制阈值、LOMO贡献率、POD维缩冒充加速、缺Jacobian/RJMCMC伪实现、PPC反序跨行、正式资源升级、深度无条件、claim/code成对删除、calibration/ledger/contract字段、所有control/hash/root/原子发布故障及六角色签核正负例。
- [x] `validation/wp5-consistency/`、日志和签核 -- 重建不可变版本/双root；完整签核正例必须使default可达PASS，六角色缺一/重复/错角色/陈旧绑定均失败。
- [x] 目标文稿 -- 直接删除/改写残留`Coverage_PPC`理想区间、PPC passed接口、PPC与名义覆盖混列、三级/类别资源升级、资源量工程输出、极限5000m及POD/IG/RJMCMC成果化；资源否定/合规引用保留并显式分类。
- [x] `claim-ledger.json`与合同 -- 每条记录exact 15字段名，ID与span全局唯一且不重叠；冻结逐文档exact ID集和上一版ledger tombstone规则。`claim_type`枚举决定允许status、metric/formula、scope、source/evidence/run/manifest及正文语气模板，禁止治理占位源支持历史/科学事实。
- [x] validator -- 对每条ledger按claim_type执行专用语义映射而非黑名单：diagnostic必须引用完整WP2组合；design EIG/realized IG/LOMO分别绑定方向/估计器/预算/MCSE；POD绑定训练/留出/误差；RJMCMC绑定Green move/Jacobian/正反密度；calibration五类、depth/resource各自绑定规范字段。
- [x] 上游证据 -- 解引用WP2/3/4 active pointer，验证目标manifest Passed、run/目录、manifest hash、成员/source hash；WP1及WP2 diagnostic/report合同同样进入不可变source root。
- [x] 代码块合同 -- 每个fence冻结语言、接口/伪代码/可执行类型、imports/symbols、capability_status、test_evidence；非可执行块禁止相邻成果语气，可执行/测试块必须绑定真实artifact与manifest，增加语法/未定义依赖/伪测试变异。
- [x] publisher/validator/SelfTest -- 从锁定snapshot完成语义扫描和发布，scan.status由结构化结果派生；AfterReplace失败回滚旧pointer；补IG/POD/RJMCMC/calibration/diagnostic/ledger tombstone、control exact/path/root separator、四标识陈旧及全部发布故障专属负例。
- [x] 正文语义清障 -- 重写`05`的PPC包络命中率`passed`接口及附录2/11的PPC/名义覆盖/PIT混列；删除或限定`01/04/05`正向资源量计算与分类升级、`06`极限5000m+及附录4无证据RJMCMC“表现优异”，并使每个coverage显式声明calibration_type、每个深度主张邻接绑定DOI条件。
- [x] ledger作用域与引用 -- 将历史钻探统计改为citation-specific `Reference-regression`，阈值使用section/scenario scope而非仅doc scope；重算exact spans/hash/ID集并阻断漏记的资源、深度、RJMCMC与校准主张。
- [x] snapshot/tombstone证明 -- 为语义扫描窗口内文档漂移加入确定性故障注入，断言专属`WP5 snapshot drift`、pointer不变及恢复后PASS；解引用上一版ledger，验证删除ID必须进入合法tombstone且ID/old hash/span唯一。
- [x] 专用规则与代码合同变异 -- 逐项消费并变异diagnostic/design_eig/realized_ig/lomo/pod/rjmcmc/calibration/depth/resource的source/metric/status/required_terms；分别变异代码块language/type/imports/symbols/capability/test_evidence并验证imports/symbols与真实artifact/manifest约束。
- [x] 上游与签核绑定矩阵 -- 对WP2/WP3/WP4分别覆盖pointer逃逸、manifest hash、Passed/exit、run、member/source hash专属负例；对version/manifest/member-root/root-file四种陈旧签核值分别建立隔离负例。
- [x] 回环4冻结与验证 -- 重建不可变发布版本和双root，保持六角色Pending；`-SkipSignoff`与扩充后的`-SelfTest`必须PASS，默认门只能因Pending失败，执行日志记录全部专属变异证据。
- [x] PPC与资源逐句收口 -- 统一`04`的`Coverage_PPC`为`PPC_envelope_hit_rate`；删除`05`无用途`coverage_threshold=0.90`；将`02`的“90%落入95%区间”明确归为留出预测校准而非PPC；逐句改写`00:119`、`01:276`、`04:477`、`05:27,1814,2345-2354`的资源量计算/分类升级正向表述。
- [x] ledger真实语义 -- 将历史钻探统计绑定citation-specific `Reference-regression`，阈值/校准/深度记录使用section/scenario scope；从正文独立分类并要求claim_type与文本类别一致，design_eig/realized_ig/lomo逐类精确绑定唯一formula/metric/status/source。
- [x] 合同字段与代码真实性 -- 九类semantic_rules的required_terms/source/metric/status/calibration types/depth/resource字段均逐记录消费并配同义表达负例；imports/symbols解析并与代码块实际标识符比对，或对不可执行接口明确冻结为空且禁止将其当执行证据；上游WP2—4允许run/manifest哈希固定于独立签核输入。
- [x] tombstone完整证明 -- 增加“删除一个前版ID并写入正确exact 5字段墓碑”的生产正例，以及duplicate ID、old_text_sha256、document、span_start/span_end逐字段专属负例；验证前版锚不可由同一次发布同步改写。
- [x] 回环5冻结与验证 -- 重算ledger/contract/source roots，重建不可变版本和双root；全套专项变异、`-SkipSignoff`、`-SelfTest`通过，默认仅Pending；更新执行日志并保持六角色不代签。
- [x] 终审残句精确清除 -- 将`04:596`的`Coverage_PPC`统一为`PPC_envelope_hit_rate`并验证公式/定义一致；逐字改写`04:477`、`05:1814`、`05:2354`及全库同义资源量控制、分位数和类别升级正向表述，发布前以精确搜索证明残句消失。
- [x] ledger分类与作用域重建 -- 将自然资源部历史钻探统计登记为带文献来源的`Reference-regression`；为阈值、校准、深度等记录建立真实section/scenario scope；为正文中的design_eig、realized_ig、lomo分别建立独立记录且逐类型绑定唯一formula/metric/status/source。
- [x] 独立语义与代码核对 -- 从正文特征独立推导高风险claim_type并与ledger比对，覆盖R-hat门、LOMO贡献率、POD加速、RJMCMC部署等同义变体；解析代码块中的import/定义/调用/测试标识符，与空或非空imports/symbols及不可执行声明一致。
- [x] 上游独立冻结锚 -- 在WP5独立签核输入中冻结允许的WP2/WP3/WP4 run、manifest和必要source/member根；validator拒绝任何仅靠同步重发active上游形成的新自洽包，并加入逐上游替换负例。
- [x] 回环6冻结与验证 -- 重算ledger/contract/source roots，重建不可变版本和双root；运行精确残句扫描、专项变异、`-SkipSignoff`、`-SelfTest`，默认仅Pending；更新日志，保持六角色Pending等待独立终审。
- [x] 实值整改与证据 -- 直接修改当前工作树中已确认仍存在的`04:477`资源量控制、`05:1814`P10/P50/P90资源量、`05:2354`资源类别升级；修正`CLM-DOC-01-0001`为citation-specific Reference-regression。提交整改前后精确`rg`输出，不以publisher报告代替文件实值。
- [x] 真实scope注册表 -- 建立可解引用section/scenario registry；每个非文档级scope必须指向真实标题行或scenario ID，同文档不同阈值不得共享`DOC-*#SCENARIO`占位；生产门验证目标存在、类型匹配和唯一归属，并加入伪scope/错section负例。
- [x] 正文类型与多语言代码解析 -- 对已冻结高风险语义建立结构化正例/禁例分类表并逐条映射正文记录；扩展代码解析至Python多导入/别名/调用/测试及text/json/yaml/toml语法，或明确这些非Python块没有可执行import/symbol/test语义并验证内容类型。
- [x] 外部冻结锚与替换矩阵 -- 将WP2/3/4 allowlist锚移出WP5同次可重写发布集合，绑定至已签核WP2–WP4规格/签核哈希或validator冻结常量；对每个上游的run、manifest、source-root分别实施同步替换负例，证明重发WP5不能更新锚。
- [x] 回环7冻结与验证 -- 逐项展示实值搜索和ledger抽样证据，重建版本/双root，运行全量矩阵及三门，更新规格/日志，保持Pending等待独立终审。
- [x] 最终科学残句 -- 直接将`04:596`公式变量改为已定义`PPC_envelope_hit_rate`；重写`05:2345-2351`资源量估算精度收益、`B_accuracy`与资源量价值接口为靶体行动效用/统一现金流合同下的合规评估，并以当前工作树精确行证据验收。
- [x] 细粒度scope -- 将`#GENERAL-DESIGN`记录映射至真实章节标题或明确scenario/action ID，不允许同文档异质阈值共享泛化scope；冻结scope registry exact 19字段集合或更新后的exact ID集合、source与ledger使用关系，拒绝未使用/删除/错source/错owner。
- [x] 冻结risk与代码内容类型 -- 冻结risk registry exact规则ID/document/pattern/claim_type集合并覆盖diagnostic/design/realized/lomo/POD/RJMCMC/calibration/depth/resource；把ledger language与原文fence标签逐块比较，对JSON/YAML/TOML做解析，对text验证无执行语义，对Python补多导入/别名及测试标识符；加入规则删除/替换、合法language错标负例。
- [x] 回环8冻结与验证 -- 重发不可变版本/双root，运行新增registry/code变异及既有全矩阵、三门，展示残句零命中与scope抽样，更新日志并保持Pending。
- [x] YAML/TOML结构解析 -- 使用项目可用的真实解析库，或实现确定性结构解析器，拒绝YAML未闭合flow、重复mapping key、非法缩进/块结构，以及TOML非法value、未闭合字符串、重复key/table；解析成功后规范化键路径进入代码内容合同。
- [x] 解析器专项变异 -- 增加“外形合法但结构非法”的YAML未闭合flow/重复key与TOML非法value/未闭合字符串/重复key-table负例，均走生产入口并匹配专属错误；保留合法嵌套YAML/TOML正例。
- [x] 回环9冻结与验证 -- 重发版本/双root，运行解析器专项与既有全矩阵、三门，更新日志和Pending绑定后再进行独立终审。
- [x] 科学正文逐句清障 -- 修正`03:122`POD维缩冒充采样效率；将`03:683-689`性能/IG/期权/ENPV/行动数值改为带状态、来源与行动合同的Design-assumption或删除；重写附录2三类IG/LOMO贡献、通用nat分级、加权EIG、复制Rhat门、PPC/coverage/PIT混列与“贡献度合理”；修正`02:257/269/275`成果化、PPC过度解释和直接预算排序；修正`00:93-97`为条件靶体事件概率；限定01 CSAMT远场判据。
- [x] 成果语气与性能表 -- 重写`00:109-117`、`01:330/334`局部成果语气；删除`02:1159-1163`第二套/放宽Rhat门；将附录4:559-564、784-806性能与结论逐项标为Design-assumption/Planned或删除并逐条入ledger；将算力说明:198-202“钻孔命中率>80%”改为合成任务可观测的留出预测/定位指标。
- [x] 附录结构与状态 -- 修正附录11第五、六节下的4.x/5.x错位编号；将679-682 RJMCMC/并行回火/自适应提议明确为Planned接口并引用WP2生产draw冻结合同；验收口径统一为“16篇目标文稿+1算力说明”。
- [x] ledger/risk全覆盖 -- 对上述每条高风险句/表建立准确ledger记录；扩risk registry覆盖POD加速、经济数字、诊断放宽、PPC覆盖混称、贡献率、无证据性能和现场命中率，并加入漏记/同义变体生产负例。
- [x] 回环10冻结与六角色终审 -- 重发版本/双root，完整SelfTest超时至少900s，运行三门和科学残句扫描；更新日志/Pending后由新独立专家完成六角色终审。
- [x] 全文Bayes/UQ清扫 -- 删除附录11旧Gelman-Rubin与钻孔符合率门；全文重写KL/IG“方法贡献”同义表达；删除04无理论依据的信息线性插值；撤销附录2通用IG/概率/ENPV评分与立即钻探门；为03行动排序和风险惩罚补齐状态—行动—损失、成本、校准、货币量纲合同。
- [x] 全文地球物理/性能清扫 -- 将01固定方法—深度“精准解决”、03阶段最优组合、附录1固定测网/精度/识别率模板改为条件化Design-assumption；逐项处理05全部裸性能/内存/人工/经济/ROI/实际钻探符合率与04收益成本比；附录4每个性能表/ASCII图就地加状态列或删除。
- [x] 概念与结构编辑 -- 修正附录2单峰/偏态/均值解释及credible region译名，撤销无证据补测降不确定性效果；彻底修正附录11各节全部子编号；清除“GPU已实现”等与证据状态冲突的成果语气。
- [x] 全文ledger/risk覆盖 -- 独立扫描17个输入的诊断门、贡献率、性能百分比/倍数/时长、经济数字、行动门、现场符合/命中率和固定精度；每个保留项必须有准确ledger记录和真实scope，risk registry冻结同义类别全集而非单点样句，并补全文漏记负例。
- [x] 回环11冻结与六角色终审 -- 重发/双root，SelfTest≥1200s、三门和全文高风险零漏记扫描通过；更新日志/Pending，重新六角色终审。
- [x] 固定模板与行动门清除 -- 重写附录2固定成矿概率/CV/IG分级、综合风险分数和钻探行动门；将04固定500m/2000m切换、附录1与附录11固定测网/点距/精度/深度模板逐表绑定Design-assumption、真实scenario scope及装置/物性/噪声/DOI条件。
- [x] 结论与实现状态清除 -- 重写07“打破/解决/完整系统/全面应用”及GPU/24h强主张；核实或撤销02“全链路已打通”、05 KSG/预处理“已实现/开发了”；将00 Frobenius权重改为generalized-Bayes敏感性选择而非量纲/稳定性保证。
- [x] 性能经济数字彻底治理 -- 对05 CPU/内存/异常覆盖/GPU、周期/孔数/落空率/回本/NPV/敏感性/经济收益等全部删除或逐项改为明确Hypothesis且禁止成果结论；对附录4全部性能表/ASCII图、附录1/3/5性能与“稳健/显著降低”结论就地加状态、定义、scope和证据边界。
- [x] 治理边界与全文覆盖 -- 明确WP5扫描范围为8章+附录1-5/11/13/14+算力说明，附录6-10/12为不在本工作包的未治理材料且不得引用为已整改证据；扩ledger/risk对固定阈值、性能经济占位、成果化动词与局部表格逐项覆盖。
- [x] 回环12冻结与六角色终审 -- 已完成重发/双root、SelfTest（1800秒调用上限，实际733.1秒）、三门与全文残句/未治理引用扫描；日志和Pending根绑定已更新，等待六角色独立终审，未代签。
- [x] 通用门与能力结论删除 -- 删除04收益成本比/概率面积/阶段升级/钻探风险通用门、MT保证深度与精准定位/高精度/直接钻孔依据；删除附录2固定CI宽度、撤销后仍展示的γ/Score排序并修正68.3%分位数。
- [x] 05/07成果与经济清空 -- 删除或结构化Hypothesis化05全部裸性能表、自动放宽先验规则、float64保证、GPU/CPU<1%门、多保真成果、采购/人工/能耗/回收期/收益/TRL/合成通过/原型完成语句；重写07革命性/完整产业链/国际领先/超越软件等成果化句。
- [x] 附录逐表就地状态化 -- 对附录1/3/4/5/11每张保留表和ASCII图在相邻标题或表内加入`Status`、真实scenario scope、指标定义和证据边界；无法逐表闭合者删除。固定测网/工期/费用/噪声/精度/深度均不得作为通用标准。
- [x] ledger/risk重建 -- 删除误标diagnostic记录并只登记真实采样诊断；补齐所有RJMCMC正文记录并逐项绑定Green/Jacobian/q_forward/q_reverse及真实scope；扩独立分类覆盖无数字成果化动词、经济/性能/行动语义，冻结exact类别与全文漏记变异。
- [x] 回环13冻结与六角色终审 -- 重发/双root、SelfTest≥1800s、三门及逐表状态覆盖审计通过；更新日志/Pending并重新六角色终审。
- [x] 恢复04最小完整方案 -- 在不恢复通用阈值/成果数字的前提下，重建场景输入合同、方法候选生成、装置/物性/噪声/DOI筛选、联合反演配置、行动输出与WP4决策移交的完整流程；每个示例均为Design-assumption并带scenario scope。
- [x] 恢复05最小完整工程骨架 -- 重建数据验证、配置、执行、诊断、故障恢复、资源预算接口、证据发布和验收流程；仅引用真实原型/合同，不恢复无证据性能、经济、TRL或“已实现”结论。
- [x] 附录修复而非删空 -- 删除附录3空标题/空表引用；修复附录11全编号、费用/最优方案残句；附录4成本/GPU硬门与失效交叉引用；附录1固定深度/全覆盖/概率/算法/成果化；附录3能力词；附录5“反演结果”语气；附录14固定距离先验/静态优先级逐项条件化并登记。
- [x] 理论与ledger修正 -- 将01“边界条件保证适定性/本体系实现”改为约束与Planned流程；补附录4唯一诊断合同record，重命名陈旧scope ID；重建所有保留项ledger/risk并加入章节完整性、空标题/失效交叉引用、未条件化强句变异。
- [x] 回环14冻结与六角色终审 -- 已完成章节结构/交叉引用/可读性机器审计，重发/双root、SelfTest及三门通过；日志与Pending根绑定已更新，等待六角色独立终审，未代签。
- [x] 附录1科学边界 -- 删除“全深度覆盖”、固定概率/物性阈值、品位预测、优先钻探和“确保”承诺；将案例发现/扩储/储量因果句改为带引用的历史案例描述或删除，明确竞争解释与不可归因边界。
- [x] 附录13/14先验边界 -- 统一Planned/候选知识库语气；删除静态数据源优先级矛盾与“让数据说话/根据反演调整先验”诱导；将σp分级限定为标准化参数候选并要求prior predictive逐项目校准。
- [x] 附录结构与xref -- 将附录1/2/13/14独立文档标题层级提升为H1/H2体系，内部编号与附录身份一致；修复附录13/14错号；清理附录11修订注和待顺延文字；修复附录5断裂定理xref及1,3列表编号。
- [x] 局部成熟度语气 -- 改写附录11“完整体系/确保应用”、附录13“系统数据库/可靠先验”、附录14“系统化知识库/可靠输入”等成果化局部句；加入结构/xref/修订痕迹/条件词生产变异。
- [x] 回环15冻结与六角色终审 -- 保持04/05冻结不变，重建受影响ledger/scope，重发/双root、SelfTest≥1800s、三门与附录结构审计通过；更新日志/Pending并重新六角色终审。
- [x] 附录1残句收口 -- 将全部“圈定/验证矿体、硫化物、锂矿化、卤水层、固定探矿深度”改为Planned候选响应或带引用历史线索，统一要求独立钻孔/地质核验、留出校准与竞争解释；高不确定性补勘绑定目标功能量和决策损失。
- [x] 附录14先验参数化 -- 删除“让数据说话”；将深度先验明确为正值支持的截断正态或对数正态，写清均值/标准差参数化、source-id、适用域和prior predictive校准。
- [x] 清除过程痕迹 -- 从17篇正文删除“修订注/同行评审/审查意见/原式/已撤销”等整改过程文字，审计历史仅保留在执行日志；摘要恢复为当前有效结论，不展示撤销史。
- [x] xref与宣传语 -- 删除01失效命中率/第7章xref，改第6章为预注册验证设计；将03“核心突破/从根本规避”和00“不可替代性”等改为候选路径/拟检验场景；新增过程痕迹、失效xref和成果化同义扫描变异。
- [x] 回环16冻结与六角色终审 -- 保持04/05冻结，重建受影响ledger/risk，重发/双root、SelfTest≥1800s、三门和成稿洁净度审计通过；更新日志/Pending并重新六角色终审。
- [x] 附录1/14精确替换 -- 逐行替换附录1:87/153/209/279/414/421/557的固定深度、控制矿体、矿体/矿化带定位；替换附录14:8成果化知识库和:425“让数据说话”，以精确搜索零命中验收。
- [x] 全文Planned语气 -- 将01“核心创新与突破/全面进入/前所未有/无法突破/核心瓶颈”，02/03/06“确保/构建了/建立了完整/保障”等改为候选路径、条件要求和预注册设计，不作保证。
- [x] 成稿洁净与排版 -- 删除02“待填写/需专家书面确认”，修正03中文引号；扩洁净度门覆盖突破式标题、保证/已建立同义词、待填/审稿指令及错误引号。
- [x] 回环17冻结与终审 -- 保持04/05冻结，重算受影响ledger，重发/双root、SelfTest≥1800s、三门和精确零命中扫描通过；更新日志/Pending并重新六角色终审。
- [x] 附录1/14最终科学句 -- 改写附录1固定VMS/低阻/方法控制矿体与精确深度句；附录14每组物性/异常候选加入逐项source-id、适用域和不确定性，删除无来源“正相关/明显异常/矿体特征”确定性表述。
- [x] 成稿四项清洁 -- 删除算力说明“技术负责人待定”；删除03标题“第32轮增强/P0/P1优先级”痕迹；把附录5两处xref改为可定位标题/合同文件锚；删除00将POD维缩比推为速度比的错误条件句。
- [x] 范围边界 -- 在签核/执行日志明确16+1仅含manifest exact文件，附录6等未治理文稿不得用于WP5 PASS或作为本工作包残句；validator拒绝签核声明扩大范围。
- [x] 回环18冻结与终审 -- 保持04/05冻结，重算ledger/risk，重发/双root、SelfTest≥1800s、三门和精确零命中/xref审计通过；更新日志/Pending并重新六角色终审。
- [x] 06合成设计去成果化 -- 重写141-183深部金矿方案，删除固定探测深度/硬件/工期及“基于测试”的见矿率、定位误差、资源量精度和投入产出比；仅保留预注册变量、合成真值可计算指标和明确非现场/非资源/非经济边界。
- [x] 附录1案例边界 -- 删除或引用化“世界级/世界最大资源/实现世界级勘查”句，统一为待核验历史线索且不可归因于方法。
- [x] 附录14知识入库合同 -- 将“满足之一/2专家/3案例”固定门改为项目预注册Design-assumption；强制source-id、适用域、选择机制、版本、独立留出/prior predictive证据，不设跨项目通用有效性阈值。
- [x] 回环19冻结与终审 -- 保持04/05冻结，重算ledger/risk，重发/双root、SelfTest≥1800s、三门及三处精确扫描通过；更新日志/Pending并重新六角色终审。
- [x] 06统计实验合同 -- 明确定义重磁近零/符号变化异常的协方差噪声、绝对地板和截断；统一NRMSE/MAPE量纲与公式；撤销通用SSIM门、固定Bonferroni与单向优胜；按配对/层次设计定义效应量和重复单位，种子仅为算法重复；场景数由功效/模拟校准确定。
- [x] 06场景与附录条件 -- 删除06固定500m/10Ωm/SNR60%跨区域泛化；附录1 MT分辨率和5%重复点改为装置/频带/维性/QC功效条件；附录14 PENDING source仅允许prior-predictive压力测试，不得进入项目先验。
- [x] 03结构与代码围栏 -- 重排3.5/3.6/3.7及3.5.3，删除“下一版本重排”；补齐3.3.1父节并统一H4/H5；确保02/03代码块内`#`不被Markdown结构扫描当标题；跨章xref写为“第2章§2.3”。
- [x] 附录4与全局编辑 -- 附录4 Observed硬门只引用实际绑定run，删除未绑定WP2例外和重复句；统一章名/附录标题/结论与参考文献层级风格，加入结构顺序、fence标题污染、含糊xref和重复句变异。
- [x] 回环20冻结与终审 -- 保持04/05冻结，重算ledger/scope，重发/双root、SelfTest≥1800s、三门及统计/结构审计通过；更新日志/Pending并重新六角色终审。
- [x] 附录1先验合同 -- 删除固定λ和磁铁矿含量退磁门；将127-135固定先验/硬范围/围岩密度/深度加权改为项目候选，规定越界质量、混合/稳健尾部与非零支持；写明LogN_A算术矩到对数域换算。
- [x] 06可复现校准合同 -- 修正CRPS积分变量；分离SBC rank与经验coverage，冻结rank构造/随机化/重复/有限样本检验，以及功能量/区间/分母/失败处理/容差；PPC冻结discrepancy、分组和尾部失配但不设通过门；CRPS冻结比较对象、配对单位、实际重要差异和区间。
- [x] 深度与知识来源 -- 将DC/IP 0-1500m改为建模域候选并由灵敏度/分辨率/DOI决定；附录14 PENDING数值不得作为知识库内容，只保留source到位后的schema占位；留出已知点登记发现机制和空间选择偏倚。
- [x] 结构清洁 -- 将03 3.3.2标题改H4；去除附录4重复声明并将概述移至toy清单前；加入统计公式/合同、固定λ/退磁门、PENDING数值、标题层级变异。
- [x] 回环21冻结与终审 -- 保持04/05冻结，重算ledger/scope，重发/双root、SelfTest≥1800s、三门及统计公式审计通过；更新日志/Pending并重新六角色终审。
- [x] 附录1固定先验清除 -- 删除341-343无source的LogN_A(100,80)、1–5000Ωm硬范围和强层位先验，改为source-id到位后生成的稳健候选且禁止零支持。
- [x] 附录14构造与角度 -- 将14.3断裂尺度/褶皱公式与阈值纳入source schema或删除；PENDING时数值为null；修正平缓褶皱翼间角定义并明确角度约定。
- [x] 06术语精确 -- 定义SBC并列随机量U_r的离散支持和生成方式；将“SBC/PPC校准”改为“SBC算法校准检查与PPC模型检查”，禁止把PPC称校准。
- [x] 回环22冻结与科学/工程终审 -- 保持04/05及已通过编辑结构冻结，重算ledger，重发/双root、SelfTest≥1800s、三门和三项科学变异通过；更新日志/Pending；工程双角色PASS，科学双角色提出loop23精确残余。
- [x] 附录1物理先验残余 -- 删除LogN_A(1,1)数值锚；磁化率支持域容纳抗磁性并明确SI/符号约定；定义卤水密度公式ρ_a及所有变量。
- [x] 06 PPC与重复设计 -- 将PPC指标改为观测discrepancy在后验预测复制分布中的位置/尾部失配和校准图，不使用复制样本自身包络命中率；区分SBC算法校准重复数与方法比较功效场景数。
- [x] 附录14构造schema -- 翼间角定义为三维层面法向二面角或预注册剖面内切线夹角，强制坐标系/手性/走向/倾向/单位/剖面；删除“180°近水平”，改为近共面/平缓褶皱；构造机制必须绑定source-id、体制/层序/阶段/适用域/竞争机制，PENDING只作压力测试。
- [x] 回环23科学签核 -- 保持编辑与工程已通过结构/机器合同冻结，重发/双root、SelfTest≥1800s、三门和三项科学变异通过；更新日志/Pending，重新地球物理/Bayes-UQ终审并确认其他四角色哈希绑定。
- [x] 附录14确定性构造清除 -- 将114-185断层/褶皱/控矿方向映射全部改为PENDING机制候选schema或删除，必须source-id、体制/阶段/竞争机制到位；236改为同时检查正演、误差模型、支持错配和先验，不得data-dependent调先验。
- [x] 附录1逐表来源 -- 删除无source的斑岩延伸数字；所有保留物性/测网数值逐表绑定source-id/适用域/状态，未到位则数值null或移除。
- [x] 01/02理论强断言 -- 删除或限定01信息损失40–70%、N=500000与迭代/耗时通常事实；修正BMA“保证优于任何模型”和联合IG“严格不小于”断言，冻结有限模型池/评分/条件信息定义。
- [x] 06测试目标 -- 将固定代码覆盖率与100%通过率改为基于风险、可达分支、mutation有效性和预注册测试集合的质量门，不以覆盖百分比代替正确性。
- [x] 回环24科学签核 -- 保持编辑结构与04/05冻结，重算ledger/risk，重发/双root、SelfTest≥1800s、三门和四项科学变异通过；更新日志/Pending并重新科学终审、工程哈希确认。
- [x] 01边界/决策/权重合同 -- 删除错误零Neumann展示，统一自由空间地面/远场边界；用后验风险定义贝叶斯行动并删除凸损失必要条件；将tempering/精度缩放对应限制于冻结且模型无关的权重、协方差与归一化合同。
- [x] 02互信息单一条件合同 -- 将2.3-37显式限定于同一联合分布和给定模型条件独立，并指向2.3-59的统一证明与共享误差例外，删除无条件“最大可能”措辞。
- [x] 03基/钻孔/风险合同 -- 明确固定正交基下坐标唯一、重根子空间基不唯一且稳定性另验；钻孔统一为带误差、位置与支持体积的概率观测；删除“天然匹配”和无证据排序表，冻结风险中性γ=0。
- [x] 回环27理论/数值/工程残余 -- 修正重力任意散度零空间、相关高斯熵与互信息对象、沉积/PENDING与米兰科维奇/应变定义；POD强制独立留出并修正最优式维数，权重仅作观测空间提议度量；算力固定容量/耗时/覆盖与恢复门改为Hypothesis/实测空及risk-owner-oracle合同。
- [x] 回环26冻结与终审 -- 保持16+1、04/05冻结及六角色Pending，重算ledger，重发/双root，运行三门和完整SelfTest≥1800s；更新日志后交独立终审。

**Acceptance Criteria:**
- Given 16篇目标文档, when 运行术语和状态扫描, then 00/01/07能力边界一致且无未绑定的强定量主张。
- Given 任一Observed表或结果句, when 独立复验, then 可定位唯一Evidence ID、Run ID/manifest及允许支持的主张。
- Given 统计、深度、资源或代码能力术语, when 跨正文/附录比较, then 使用同一规范定义且场景参数不冒充全局验收门。
- Given 默认验证与SelfTest, when 正式签核后执行, then 均返回0，任一文档、合同、证据或发布根漂移返回非0。

## Spec Change Log

- 回环1：三层复审证明初版`ValidateClaim`只用于合成SelfTest，正式16篇仅验证篇首marker与哈希；窄PPC/伪代码regex、未消费合同字段和helper级SelfTest允许同步重发证据后绕过。任务现冻结逐主张/代码块结构记录、section归属、五类校准与阈值来源，要求scanner成功后才发布，并让所有负例进入隔离生产入口。避免“一处合法绑定覆盖全篇”、文件自洽冒充语义正确及任意异常算caught。KEEP：保留已完成的16篇就地治理块、WP1—WP4规范边界、精确文档清单/状态枚举/公式ID/threshold source、UTF-8/hash/双root/Pending证据骨架。
- 回环2：复审证明998条统一Planned标记不验证正文语义、未冻结exact记录集，49个代码块也可仅靠`executable=false`自述；WP2合同只核路径字符串，错误正文同步重发仍PASS。任务现移除机械标记，建立带文本hash/跨度/类型/真实状态/上游合同hash的独立ledger，并为诊断、IG、POD、RJMCMC、校准、深度和资源建立专用语义门及生产变异。避免marker自证、成对删除、publisher硬编码Passed和治理证据冒充科学证据。KEEP：保留16篇直接整改、28 section归属、机器合同/原子发布/双root骨架及Pending边界。
- 回环3：复审证明回环2 ledger仅绑定文本hash，未消费claim_type/metric/formula/source语义；窄regex可被同义改写，WP2—4只绑定pointer字节，publisher仍硬编码Passed。任务现冻结每条记录exact语义映射与tombstone、解引用上游Passed manifest、建立代码块能力合同，并从不可变snapshot派生scan状态。避免同步改正文+ledger+root、治理占位源支持科学事实和完整性冒充正确性。KEEP：保留1047真实跨度ledger、直接修文、原子发布/双root、完整fixture与六角色签核骨架。
- 回环4：第三轮专项复核发现PPC/coverage、资源升级、极限深度及无证据RJMCMC残句仍可绕过ledger；历史引用和阈值scope仍误分类。验证缺口复核同时证明snapshot漂移无故障注入，tombstone未解引用前版，专用语义、代码21字段、WP2—4深解引用和四标识陈旧仅有抽样负例。任务现要求逐句清障、逐字段消费及全分支专属变异，避免治理完整性再次冒充科学一致性。KEEP：保留第三轮已通过的EIG/IG/LOMO/POD定义、原子回滚、不可变发布、双root和Pending签核边界。
- 回环5：第四轮复核确认5000m、RJMCMC评价、附录11及EIG/IG/LOMO/POD已闭合，但PPC变量/阈值、资源升级残句、历史引用与section/scenario scope仍未闭合；tombstone只有非法计数负例，专用规则/代码文本真实性及上游独立冻结锚仍可同步重发绕过。任务现要求逐句命中、正文独立分类、逐类型唯一映射、代码标识符核对、独立上游允许列表和墓碑完整正负矩阵。KEEP：保留回环4已通过的snapshot/回滚、九类与code字段基础矩阵、18个上游分支、四标识陈旧及Pending门。
- 回环6（用户批准突破五轮上限）：第五轮验证覆盖已PASS，但专项终审仍发现PPC变量、三处资源升级残句、历史引用误分类、仅文档级scope及realized_ig/lomo ledger缺失；算法终审同时确认逐类型公式、正文独立分类、代码标识符和上游独立allowlist未闭合。本轮以精确残句搜索、正文派生类型、代码解析和独立冻结锚收口，不再以结构字段存在代替语义一致。KEEP：保留已通过的PPC 0.90删除、02留出校准、POD/RJMCMC/深度边界、tombstone完整矩阵及全部发布故障验证。
- 回环7：第六轮报告称残句清零，但主代理直接读取工作树仍确认`04:477`、`05:1814`、`05:2354`存在，且`CLM-DOC-01-0001`仍为depth/Planned/WP3-ACTIVE/DOC-01#SCENARIO；验证复核也确认scope、正文分类、非Python代码解析和allowlist外部独立性未闭合。本轮要求以文件实值、可解引用scope注册表和WP5发布集合之外的冻结锚验收。KEEP：保留唯一IG公式映射、PPC旧变量实际零命中、代码基础解析、tombstone与发布故障矩阵。
- 回环8：第七轮已修复三处资源主句、历史Reference及外部allowlist，但终审直接确认`04:596`旧PPC变量、`05:2345-2351`资源收益接口和泛化`#GENERAL-DESIGN`仍在；验证复核证明scope/risk registry集合可静默缩减，代码language未绑定fence标签。任务现要求精确残句修复、真实细粒度scope、冻结完整risk集合及按语言内容解析。KEEP：保留Reference-regression、唯一IG公式、根级九常量allowlist、9替换负例和既有全矩阵。
- 回环9：第八轮已闭合科学残句、108真实scope、9类risk、fence绑定、JSON/text/Python解析，但验证缺口复核证明YAML/TOML仍是行外形检查，无法拒绝未闭合结构、重复键和非法值。本轮仅替换/强化两类结构解析并增加外形合法但语法非法的正负矩阵。KEEP：保留loop8其余已通过的正文、registry、代码和发布验证。
- 回环10：loop9机器治理、严格配置子集、签核门及blind/edge已PASS，但首次六角色终审揭示正文仍有POD加速、IG/LOMO贡献、复制/放宽Rhat、PPC覆盖混称、无证据经济/性能强数字与局部成果化等漏记残句，并发现附录编号和“16+1”计数口径问题。本轮转回逐句科学与编辑清障，每项必须直接修文并进入ledger/risk。KEEP：保留loop9全部机器合同、上游冻结锚和发布/回滚/签核验证。
- 回环11：loop10点名行整改和SelfTest已PASS，但新六角色终审发现全文同类残句仍广泛存在：旧诊断门、IG贡献语义、通用行动阈值、固定方法/深度/精度模板、裸性能经济数字、附录概念错误与编号错位，且多数不在ledger。任务升级为17输入全文高风险扫描与逐项治理，不再限于上一轮行号。KEEP：保留loop10已修句、loop9机器合同和算法/数值已验证的公式/代码/上游骨架。
- 回环12：loop11虽处理651候选并使机器扫描零漏记，但独立终审仍发现附录2行动门、附录1/11固定模板、04深度切换、05/07性能经济数字、结论成果化、附录局部状态和16+1之外未治理附录边界。任务现要求逐表/逐图就地状态化或删除，并明确未治理附录不得进入完成口径。KEEP：保留loop11已修诊断/IG/编号/概念项与全部机器发布骨架。
- 回环13：loop12已增加条件边界和独立类型推导，但终审证明大量通用行动门、经济/性能表、无数字成果化语句和仅篇首统降的附录表仍存活；diagnostic ledger存在误标且RJMCMC漏记。本轮采用删除优先、逐表就地状态化和ledger重建，禁止再用篇首声明覆盖局部表格。KEEP：保留loop12已闭合的16+1治理边界、配置/发布/签核机器合同和逐记录语义框架。
- 回环14：loop13删除优先消除了大量风险表，但导致04/05章节仅余约40行、附录空标题/编号错乱和交叉引用失效，破坏可读性与工程完整性；附录1/3/5/14仍有固定模板与成果化残句。本轮恢复最小完整、合同驱动的04/05方案并逐附录修复，禁止用恢复完整性为由重新引入无证据数值。KEEP：保留loop13的425+623血缘、精简diagnostic/RJMCMC、无数字分类和全部机器骨架。
- 回环15：loop14的04/05最小完整骨架、diagnostic/RJMCMC及附录5统计边界通过，但终审仍发现附录1因果/阈值/确保承诺、附录14静态优先级与data-dependent prior诱导、附录1/2/13/14标题层级和编号、附录5断裂xref、附录11修订痕迹及局部成熟度语气。本轮仅整改这些附录，冻结已通过04/05。KEEP：保留loop14机器合同、414+634血缘、章节完整性门和04/05文本。
- 回环16：loop15结构/xref/成熟度变异已通过，但科学终审仍发现附录1圈定/验证/固定深度残句及附录14先验参数化矛盾；编辑终审发现正文仍保留大量整改过程痕迹、失效xref和宣传语。本轮将审计历史移出成稿，只保留当前有效主张，并精确闭合两附录科学边界。KEEP：保留loop15结构层级、编号、04/05冻结和全部机器骨架。
- 回环17：loop16长测已真实exit0，但终审直接读取仍发现附录1/14七处科学残句和01/02/03/06宣传/保证/待填文字，说明上一轮精确扫描集合不完整。本轮按行替换并冻结更广的成稿洁净同义门。KEEP：保留loop16前版墓碑修复、04/05冻结、成稿过程痕迹清理和全部发布合同。
- 回环18：loop17精确门已通过，但终审仍发现附录1固定物性/深度/方法归因、附录14无source候选表，以及算力说明待定、03修订标题、附录5失效xref和00维缩/速度混淆。另附录6被用于越界审查，需明确其不在16+1签核集合。本轮只处理这些精确项并冻结范围声明。KEEP：保留loop17洁净度门、04/05冻结和414+634血缘。
- 回环19：loop18限定16+1后，科学终审仍发现06章合成预注册方案冒充深度/资源/经济结果、附录1两个世界级案例强结论、附录14固定专家/案例入库门。本轮只精确修正这三处并冻结非现场/非资源/非经济和知识来源合同。KEEP：保留loop18 exact范围、附录1/14其余整改、04/05冻结及全部机器合同。
- 回环20：loop19三处科学边界已闭合，但终审进一步发现06噪声/指标/效应量/重复单位/多重比较与功效合同不自洽；编辑终审发现03章节失序/层级断裂、代码块标题污染、含糊xref及附录4未绑定WP2措辞。本轮精确修复统计实验与文档结构。KEEP：保留loop19非资源/非经济边界、16+1 exact范围、04/05冻结及全部机器合同。
- 回环21：loop20统计设计与大部分结构已修，但终审仍发现附录1固定λ/退磁门/硬先验，06 CRPS公式和SBC/coverage/PPC验收合同不完整，附录14 PENDING数值及留出选择偏倚，以及03单一H5层级错误。本轮冻结可复现统计细节与先验支持域。KEEP：保留loop20协方差噪声、层次重复/效应量/功效合同、04/05冻结和全部发布骨架。
- 回环22：loop21主编与技术编辑已PASS，CRPS/coverage合同通过；科学终审仅余附录1三条固定先验、附录14无source构造与翼间角、SBC并列随机量及PPC术语。本文轮只修这些精确科学项，冻结已通过编辑结构。KEEP：保留loop21全部统计设计、标题结构、04/05冻结和编辑双PASS证据。
- 回环23：loop22算法数值与工程架构已PASS，编辑双角色沿用loop21 PASS；科学终审仅余附录1一个数值锚/物理变量、PPC指标定义与重复数区分、附录14三维角度及构造机制条件。本轮只修科学残余并冻结其余四角色已通过表面。KEEP：保留loop22机器与编辑结构、04/05冻结及414+634血缘。
- 回环24：loop23编辑双角色确认PASS，PPC/SBC与物理变量通过；科学终审扩展发现附录14确定性构造机制与PENDING合同冲突、附录1逐表来源不闭合、01/02少量无证据量化/理论保证及06固定覆盖门。本轮逐项删除或条件化这些全文科学残余。KEEP：保留loop23编辑PASS、loop22工程PASS、04/05冻结及全部发布合同。
- 回环25：loop24独立终审定位02章无来源褶皱经验式/固定角度表和谱峰过度解释、01章点估计与决策可计算性强断言，以及03章平滑/风险准则和06章固定工程门、陈旧CI依赖与跳过slow集成。本文轮以项目source/schema、替代解释与独立验证、冻结状态—行动—损失合同、风险清单/供应链/发布哈希门精确收口。KEEP：保持16+1 exact范围、04/05冻结、414+634血缘、发布/回滚合同和六角色Pending。
- 回环26：loop25独立终审定位01零Neumann展示、贝叶斯风险定义和权重等价边界，02重复互信息上界条件，以及03正交基唯一性、钻孔硬固定、MRF“天然匹配”和γ=1风险中性示例。本轮以自由空间边界、后验风险、模型无关冻结权重、单一条件MI、概率支持体积观测及γ=0精确收口。KEEP：保持16+1 exact范围、04/05冻结、414+634血缘、发布/回滚合同和六角色Pending。
- 回环27：loop26独立终审继续定位错误的任意散度重力零空间、相关高斯熵差误称参数信息损失、沉积来源/天文归因/应变记号，以及POD训练集选秩、低秩最优式维数、自适应权重维数和似然目标混淆；工程侧定位算力表固定容量/耗时/覆盖/恢复门及CI边界缺口。本轮逐项修文并新增8项生产变异。KEEP：16+1 exact范围、04/05冻结、signoff Pending及不可变发布合同。
- 回环28：账本终检发现一条失效的04 active记录及42条正文重写后的文本锚。以逐ID迁移（28 replacement、14 tombstone）重建可审计锚，任何无活动主张绑定的旧语言风险规则（achievement/economic/performance/action）均显式退役而非静默绕过；保留`semantic_rules`对正向宣传语的阻断，并新增迁移、墓碑不复活和风险规则缩减负例。KEEP：04/05冻结、16+1 exact范围、1048条血缘守恒及六角色Pending。

## Design Notes

机器合同只验证结构化状态与证据关系，不尝试证明自然语言公式的Markdown字面等价。科学一致性由规范段引用、专项审查和针对性禁式共同保证。

## Verification

**Commands:**
- `pwsh -NoProfile -File ".../validate-wp5.ps1"` -- 正式文稿、合同、证据根与独立签核通过。
- `pwsh -NoProfile -File ".../validate-wp5.ps1" -SelfTest` -- 术语、状态、表结构、证据绑定及发布漂移正负例通过。

结果：loop15最终版本`20260719T151757811Z-49679c8799044d1caf41401cd5a93f18`，manifest `8c02e40d9e19c23e29792605015eda9c8cde5ad98c492247e7337e5944486475`；`-SemanticOnly` PASS，`-SkipSignoff` PASS，`-SelfTest -SkipSignoff` PASS（调用上限1800秒，实际1206.9秒）；默认验证非零且唯一命中`independent signoff Pending`。ledger保持414 entries + 634 tombstones = 1048，受影响记录文本hash已重算，scope集合保持冻结；04/05 SHA-256分别保持`61b215cb72e5a0393fc90793f4595aa2bcad578cbb03f046dda69adb89c56510`与`bf4565da548d69a3cf4e5fb0a6970831619c957428244c2edf44a8f34b96fbd2`。附录标题/内部编号、科学边界、先验边界、xref/list、修订痕迹和成熟度均进入生产门与隔离变异；六角色签核保持Pending。

结果：loop16版本`20260719T155255878Z-218c71705e2140b1b2d55d9bb0302ccd`，manifest `e8a85a12564a478a7797b4aabc717086e28062086458acb3e1e0dd3c9f85c776`；`-SemanticOnly` PASS，`-SkipSignoff` PASS，`-SelfTest -SkipSignoff` PASS（调用上限1800秒，实际1128.9秒，exit 0）；默认验证非零且唯一命中`independent signoff Pending`。ledger保持414 entries + 634 tombstones = 1048，13类risk规则保持exact集合并全部命中；新增过程痕迹、失效xref、宣传语、附录1候选边界和附录14正值先验五类生产变异。成员根`c4397c1edd3187fd62a17372a59debbc0f74f7c59341318ed2a5dd8bcf87707e`，根文件`fc393ce708b9166ae69cd8bf5c627a2d2ccf857113dd7eaffe4e62df10e4e31e`；04/05 SHA-256继续保持冻结值`61b215cb72e5a0393fc90793f4595aa2bcad578cbb03f046dda69adb89c56510`与`bf4565da548d69a3cf4e5fb0a6970831619c957428244c2edf44a8f34b96fbd2`。六角色签核保持Pending，未代签、未push。

结果：loop17版本`20260719T170859474Z-1d9c5f19703b4bfea836cc4c3485ccc8`，manifest `40ef538eaa93d8af8785d3b11fd21303b88ab79f719007f938d289b428918ea0`；`-SemanticOnly` PASS，`-SkipSignoff` PASS，`-SelfTest -SkipSignoff` PASS（调用上限1800秒，实际1185.0秒，exit 0）；默认验证非零且唯一命中`independent signoff Pending`。附录1七条与附录14两条点名旧句精确搜索零命中；全文“确保/保障/待填写/专家审稿指令”零命中，“突破/建立了/构建了”仅保留三处明确否定和两处带引用的历史文献合法上下文；逐文档中文引号平衡与方向门通过。ledger保持414 entries + 634 tombstones = 1048并全量重算当前文本hash；新增两附录exact、突破、保证、待填、审稿指令及错误引号七类隔离生产变异。成员根`dae9c3522d9513955b11be60b473e30b62983008c7f5b45e20040f87edf50578`，根文件`a19107d8c2bb3ab949c93cc31669d0edbfb2ef67849c59b98b3df548d49c95d7`；04/05 SHA-256继续保持冻结值`61b215cb72e5a0393fc90793f4595aa2bcad578cbb03f046dda69adb89c56510`与`bf4565da548d69a3cf4e5fb0a6970831619c957428244c2edf44a8f34b96fbd2`。六角色签核保持Pending，未代签、未push。

结果：loop18版本`20260719T174427507Z-ba602583e70449eb89e336eed31e218f`，manifest `28b78291a03e85c001bb0b995481b14bf42b99b668a90c7b025137b23519d2ba`；`-SemanticOnly` PASS，`-SkipSignoff` PASS，`-SelfTest -SkipSignoff` PASS（调用上限1800秒，实际1196.8秒，exit 0）；默认验证非零且唯一命中`independent signoff Pending`。附录14六个模式组分别登记source-id、适用域和不确定性；附录1固定VMS/低阻/方法归因、算力待定、03轮次优先级、00维缩速度混淆及附录5失效xref点名模式精确搜索零命中。scan exact为16篇文稿+1算力说明，共17成员；签核声明明确排除附录6—10/12，新增同步扩大范围的生产负例并专属命中`signoff exact 16+1 scope`。ledger保持414 entries + 634 tombstones = 1048，受影响span/hash与附录14 scope锚已重算。成员根`06fbe76a6840d164bf1dfab066df996bc3d6d26456a09dac94524992b8e3acf4`，根文件`28b3ded0a62c94a1a7922d9c0dd3610dfcef71880834023caee66547550f8d40`；04/05 SHA-256继续保持冻结值`61b215cb72e5a0393fc90793f4595aa2bcad578cbb03f046dda69adb89c56510`与`bf4565da548d69a3cf4e5fb0a6970831619c957428244c2edf44a8f34b96fbd2`。六角色签核保持Pending，未代签、未push。

结果：loop19版本`20260719T181717587Z-bc7b0965084c470dbc6b82ebb6f8109c`，manifest `4a535dfab3cb927d405e17e70ab8746852df0834fef0a09635fbb7044b669aee`；`-SemanticOnly` PASS，`-SkipSignoff` PASS，`-SelfTest -SkipSignoff` PASS（调用上限1800秒，实际1257.5秒，exit 0）；默认验证非零且唯一命中`independent signoff Pending`。06章6.6仅保留合成任务预注册变量、生成真值可计算指标及非现场/非资源/非经济边界；附录1三条世界级案例改为待核验历史线索并禁止方法归因；附录14固定专家/案例入库门改为项目级`Design-assumption`合同，强制source-id、适用域、选择机制、版本、prior predictive与独立留出。三组旧句精确搜索均为零命中，新增三项隔离生产变异均专属拒绝。ledger保持414 entries + 634 tombstones = 1048，受影响文本hash已重算，13类risk exact集合未扩缩并继续通过冻结门。成员根`17576bb0d45e88f94aa4b7e0096e9fb6de7fffba0c5b446cbd7eeccf40b56c81`，根文件`be160879e8b78fb6f1ff0bb152661a5fb9431062aff879ef85fd16e0f0e3956a`；04/05 SHA-256继续保持冻结值`61b215cb72e5a0393fc90793f4595aa2bcad578cbb03f046dda69adb89c56510`与`bf4565da548d69a3cf4e5fb0a6970831619c957428244c2edf44a8f34b96fbd2`。六角色签核保持Pending，未代签、未push。

结果：loop20版本`20260719T192316053Z-5f2de708ea8c4f78b7da27cd99b53e09`，manifest `ab27ed3dcbfdc12cf6261e9e9b4720e177e3f6ad7c1c9c974d953488ed787e4b`；`-SemanticOnly` PASS，`-SkipSignoff` PASS，`-SelfTest -SkipSignoff` PASS（调用上限1800秒，实际1289.6秒，exit 0）；默认验证非零且唯一命中`independent signoff Pending`。06统计合同现使用协方差噪声、绝对地板/截断、NRMSE与受限MAPE、配对/层次效应及功效/模拟校准；覆盖层场景参数不再跨区域泛化。03顺序为3.5.3→3.6→3.7并补3.3.1父节，结构扫描忽略围栏内标题。附录1固定MT分辨率/5%重复点改为条件合同，附录4仅保留实际绑定WP1 run的Observed例外，附录14 PENDING来源隔离于项目先验。新增10类隔离用例覆盖统计、条件、结构、xref、重复句、Observed和fence正例。ledger保持414 entries + 634 tombstones = 1048；成员根`0cba31e91f3004792d4568503028ef88efd5f3f750567f5d987fefe922b08b75`，根文件`2939a0bbd1e491dc76074a2fc8ec21b62accaeaf95520a07d472a0cef58a8a3c`；04/05 SHA-256保持冻结值`61b215cb72e5a0393fc90793f4595aa2bcad578cbb03f046dda69adb89c56510`与`bf4565da548d69a3cf4e5fb0a6970831619c957428244c2edf44a8f34b96fbd2`。六角色签核保持Pending，未代签、未push。

结果：loop21版本`20260719T201212981Z-617959b1cfb143b18c74f07aad72b330`，manifest `5e7d3a7f31b200dae84898bc54dff6209f9ee1a1d0ae700f6ce391c6fadca113`；`-SemanticOnly` PASS，`-SkipSignoff` PASS，`-SelfTest -SkipSignoff` PASS（调用上限1800秒，实际1427秒，exit 0）；默认验证非零且唯一命中`independent signoff Pending`。附录1已冻结项目级支持域、非零稳健尾部与`LogN_A`算术矩换算；06已分离SBC rank、经验区间coverage、PPC和CRPS配对合同并修正积分变量；DC/IP 0—1500 m仅为建模域候选。附录14删除全部PENDING数值，只保留`null` schema槽并登记已知点发现机制与空间选择偏倚。03单一H5改H4，附录4概述前移且重复声明删除。新增10项loop21专属变异，并迁移loop20/16两个失效旧变异。成员根`87026a30596a866b015aacfa6382a7614ac736c6706db1c59af8714e044416ce`，根文件`838ee62426479f9db32d8dda3c499c7ad2374d282bbead63da9df58f74bf8914`；04/05 SHA-256继续保持冻结值。六角色签核保持Pending，未代签、未push。

结果：loop22版本`20260719T205519247Z-aa077840857c45579f90fadba4ea5298`，manifest `9dcfeafb30eddcf0aad017c4319b650cf571362ceaaad3478000ee4504578ee0`；`-SemanticOnly` PASS，`-SkipSignoff` PASS，`-SelfTest -SkipSignoff` PASS（调用上限1800秒，实际1506.7秒，exit 0）。附录1删除`LogN_A(100,80)`、1—5000 Ω·m硬范围和强层位先验，改为项目`source-id`、竞争混合候选及非零稳健尾部；附录14删除无来源断裂尺度与褶皱公式/阈值，冻结PENDING数值为`null`，翼间角采用\(0^\circ<\phi\le180^\circ\)较小内角约定；06明确\(U_r\sim\mathrm{DiscreteUniform}\{0,\ldots,t_r\}\)、\(R_r\in\{0,\ldots,L\}\)及`t_r=0`边界，并将PPC严格称为模型检查。新增8类loop22隔离变异，长测实际暴露并补强PENDING几何赋值和连续均匀并列随机量两条漏网禁式。成员根`131bb6c9808a5d28c751f6838b52ec3775cf4bd97ba93b0f21ae614d9aa6edc3`，根文件`c97e7cbf492dc1f21065bec713bee7caada68cb87e1d8dbb039d605a46289971`；04/05保持冻结未改。六角色签核四标识已更新但状态继续Pending，未代签、未push。

结果：loop23版本`20260719T213933357Z-5be1e04ea0cf4ae884bf390a998fc0b1`，manifest `176bd14917e5d7c5ceacf4e8a543943cdd88d037fd6fcc16a9bbad28c7e95309`；`-SemanticOnly` PASS，`-SkipSignoff` PASS，完整`-SelfTest -SkipSignoff` PASS（调用上限1800秒，实际1481.6秒，exit 0），默认门唯一失败为`independent signoff Pending`。附录1删除`LogN_A(1,1)`锚，磁化率改为容纳抗磁性的有符号无量纲SI支持，并定义饱和地层表观体积密度\(\rho_a\)及六个变量；06以观测discrepancy相对复制discrepancy分布的位置、尾部失配和校准图定义PPC，分离\(R_{\mathrm{SBC}}\)与\(N_{\mathrm{power}}\)；附录14采用三维法向二面角或预注册剖面切线角二选一，冻结坐标/手性/姿态/单位/剖面字段及构造机制source合同。新增8项专属变异全部通过。成员根`a5be92059746ffddd7fecfc65d198fffadebde87306cfca0c6c3544009ef97f3`，根文件`dd45ea11115929f5a11ccbf0610c52254d3162aa2a64e488f631aeff4de7d95b`；04/05保持冻结未改。六角色继续Pending，未代签、未push。

结果：loop24版本`20260719T222611052Z-d846e055dd2e4e95b57a58b1be5822db`，manifest `794b8c0703e8688a56e8f0645b59f2c278e314ca8079e263b9ca1ac3d0e09f60`；`-SemanticOnly` PASS，`-SkipSignoff` PASS，完整`-SelfTest -SkipSignoff` PASS（调用上限1800秒，实际1618.2秒，exit 0），默认门exit 1且唯一失败为`independent signoff Pending`。附录14删除确定性构造映射并令PENDING机制逐字段为`null`；附录1冻结逐表source状态；01/02修正无证据数量与BMA/联合互信息条件；06改为风险、可达分支、不变量、mutation与失败注入联合质量门。新增10项loop24专属变异；首次长测捕获`prior_only_blame`门缺口后补强并重发。成员根`bb9da7f973729a1c9e15ad6bc6cd20ed2e3faa7c5d14867df22c0c0d40c9d548`，根文件`00987380c85c519fd3919b1d7f8eb7484e3aadbccbd1e2f4bf85123b744ff608`；04/05保持冻结未改。六角色继续Pending，未代签、未push。

结果：loop25版本`20260719T231129912Z-604f92d57a7f443490a65feb1ae4aefb`，manifest `ce03c8a7712a40ad9407b76484e579f9f93e0a13194e5554fe8ac999ef8d5d72`；`-SemanticOnly` PASS，`-SkipSignoff` PASS，完整`-SelfTest -SkipSignoff` PASS（调用上限1800秒，实际1752.7秒，exit 0），默认门exit 1且唯一失败为`independent signoff Pending`。02褶皱/谱峰、01点估计/决策可计算性、03平滑/风险准则和06风险CI/供应链合同已收口；新增12项loop25专属变异，首次长测捕获`gradient_min`同义门缺口后补强并重发。成员根`72adf67c9386f7a6b1351b37ed0fa2ff7b6ff35cf9670ab44129673af5fbb1b2`，根文件`848fbd0c180d3a644ad6d3eba0d5c5fe73f79f7ee86ef0a5c9c2ab0b75426ef9`；04/05保持冻结未改，ledger保持414 entries + 634 tombstones = 1048。六角色继续Pending，未代签、未push。

结果：loop26版本`20260719T235715381Z-6658765e661a480fbe1266bed0660f6f`，manifest `3c00946242352d521c378f1c8c6205b2cbc58646d133cce77400d402aeaa1b94`；`-SemanticOnly` PASS，`-SkipSignoff` PASS，完整`-SelfTest -SkipSignoff` PASS（调用上限1800秒，实际1740.1秒，exit 0），默认门exit 1且唯一失败为`independent signoff Pending`。01自由空间边界/贝叶斯后验风险/权重等价条件、02条件互信息单一合同、03固定基坐标/重根基不唯一/钻孔支持体积/MRF边界/风险中性γ=0已收口；新增8项loop26专属变异，前两次长测分别捕获`weight_equivalence`与`basis_unique`同义门缺口，补强后完成全矩阵。成员根`50dcd47ab78b9ccc0d8060704b99ef83c729f4afad5a2e96cc7106d479944bb0`，根文件`88184b8fd4958d49d324d5293f11cce58368d1a0c7a6e8f433914684cd4c9d97`；04/05保持冻结未改，ledger保持414 entries + 634 tombstones = 1048。六角色继续Pending，未代签、未push。

结果：loop27最终版本`20260720T014615916Z-3ac54000d6d249e3bff204f48605fc45`，manifest `caa7ca6dfb375441365e30d9fa89e10e1ca55352d23e2a099d3f5cd618c53caf`；`-SemanticOnly` PASS，`-SkipSignoff` PASS，完整`-SelfTest -SkipSignoff` PASS（调用上限1900秒，实际1648.9秒，exit 0），默认门exit 1且唯一失败为`independent signoff Pending`。首次长测在242.1秒捕获`divergence_null`变异未命中，补强八项loop27禁例后重发并完成全矩阵。成员根`b1417553b52bf25f4a5ab87cc4bf3812ec824bab2832f8fdd69da07f937c05ed`，根文件`c380baed56d240655caf024d441d324ed5b8c11ca8969db4bb94181d0054476c`；04/05保持冻结未改，六角色继续Pending，未代签、未push。
