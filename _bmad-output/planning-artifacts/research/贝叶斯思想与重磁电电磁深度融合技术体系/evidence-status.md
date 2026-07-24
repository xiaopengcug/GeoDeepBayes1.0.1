# 证据状态登记

更新日期：2026-07-17。状态词仅允许：`Hypothesis`（假设/目标）、`Planned`（已预注册但未运行）、`Open-data-run`（仅有公开数据完整性/摄取/质量运行证据）、`Synthetic-run`（有可复算且全部验收检查通过的合成运行证据）、`Field-validated`（有现场留出验证证据）、`Blocked`或`Failed`。`Open-data-run`和失败运行不得自动升级或等同于后两者。

`evidence_id` 是稳定主键，不随章节改名而改变。`source/run` 在证据生成前写 `none`，生成后必须填写证据包相对路径及run ID；`owner/date` 必须由责任人和实际运行日期回写，不得以文档修订日期替代。

| evidence_id | 主张类别与位置 | metric / unit | 当前状态 | source / run | owner / date | 升级验证条件 | writeback target |
|---|---|---|---|---|---|---|---|
| EVD-PHYS-001 | 物性范围、矿种判别；附录1、13、14 | 电阻率 Ω·m；密度 kg/m³；磁化率 SI；极化参数及条件概率 | Hypothesis | none | 岩石物理负责人 / 未运行 | 绑定样本数、测量条件、来源、SI单位；独立先验预测与混淆类别校准 | 附录1物性表；附录13数据库元数据；附录14先验条目 |
| EVD-TARGET-001 | 物探靶体体积/潜力情景；附录1、2、10、11、12 | P10/P50/P90体积 m³；连通性；事件概率 0—1 | Planned | none | UQ负责人 / 未运行 | 联合后验样本逐次计算；报告可信区间与空间支持尺度；不得自动分类为资源量 | 附录1、2情景表；附录10、11交付表；附录12可视化 |
| EVD-RESOURCE-001 | 正式资源量/金属量合规升级条件 | 质量 t；品位 %；体积密度 kg/m³；资源类别 | Planned | none | 资源地质负责人 / 未运行 | 钻孔品位、体积密度、支持尺度、合理开采前景、适用标准与合资格人员签署 | 独立合规资源评价报告；不得回写为物探结果 |
| EVD-ALGO-001 | 算法选型、POD秩与采样性能；附录3 | rank-\(\hat R\)；bulk/tail ESS；MCSE；代理似然误差 | Hypothesis | none | 数值推断负责人 / 未运行 | 冻结数据、配置、代码哈希；报告代理误差和采样诊断 | 附录3选型表；附录4Observed列 |
| EVD-BENCH-001 | 核心算法性能与复杂度；附录4 | wall time s；GPU-hours；峰值内存 GB；误差；扩展效率 % | Planned | none | 性能工程负责人 / 未运行 | 至少5个规模×5次重复；原始日志、环境、随机种子、误差及bootstrap区间 | 附录4Synthetic-run报告 |
| EVD-FIELD-001 | 真实矿区定位、命中率和现场收益；附录5 | 定位误差 m；事件Brier/对数评分；命中率 %；成本 | Planned | none | 现场验证负责人 / 未运行 | 数据许可、原始测线/钻孔ID、时空留出、复算脚本、盲态解封记录 | 附录5Field-validated报告 |
| EVD-IP-001 | 论文、专利、软件和示范应用；附录6、7 | 受理/授权/发表/验收件数 | Planned | none | 知识产权负责人 / 未发生 | 受理、授权、发表或验收文件及对应版本和日期 | 附录6、7成果清单 |
| EVD-FIN-001 | 收入、利润、估值、ROI/NPV；附录8 | CNY；ROI %；NPV CNY；折现率 % | Hypothesis | none | 财务负责人 / 未运行 | 审计合同与财务数据、样本期、币值税费折现口径及敏感性分析 | 附录8Observed财务表 |
| EVD-UX-001 | 快速上手时长与自动化能力；附录9 | 任务完成时间 min；契约测试通过率 % | Planned | none | 产品负责人 / 未运行 | 能力矩阵契约测试和端到端benchmark日志 | 附录9操作时长与功能状态 |
| EVD-PPC-001 | 后验预测校准；附录2、9、10、11、12 | 名义覆盖率 %；实测覆盖率 %；区间宽度/锐度；PIT/rank | Planned | none | UQ负责人 / 未运行 | 预注册复制观测统计量和名义区间；覆盖率与锐度联合报告 | 附录2验收清单；附录9—11检查表；附录12元数据 |
| EVD-SBC-001 | 参数真值覆盖与推断校准 | SBC rank；经验覆盖率 %；z-score | Planned | none | UQ负责人 / 未运行 | 多次独立合成数据/SBC；不得用PPC替代 | 附录4、5验证报告 |
| EVD-COMPUTE-001 | 云端时长、吞吐、加速比与成本；算力说明 | wall time s；samples/s；speedup；GPU-hours；CNY | Planned | none | 系统架构负责人 / 未运行 | 完整benchmark manifest、平台报价、原始日志与计费明细 | 算力说明Observed列；附录4 |
| EVD-OPEN-001 | 本地公开地球物理数据完整性、格式与数值资产验证 | 文件数；SHA-256失败数；格式检查通过数；上游大小差异数 | Open-data-run | validation/runs/open-data-20260717-03 / open-data-20260717-03 | 数据治理负责人 / 2026-07-17 | 仅支持数据摄取与质量边界；不得升级为Field-validated或替代钻孔留出验证 | 整改落实报告01；开放数据验证run包 |
| EVD-SYNTH-001 | DO-27同源重磁数据现代SimPEG降阶兼容验证 | 正演有限性；归一化RMS；模型RMSE；迭代数；停止码；耗时 | Synthetic-run | validation/runs/do27-simpeg-20260717-06 / do27-simpeg-20260717-06 | 待复核 / 2026-07-17 | 12×12×8网格、每方法121观测；重力与磁法**均收敛(stop_code=2)**，磁法经 iter_lim=2000+alpha 扩展后 882 次收敛(normalized_rms≈4e-5)；**仍非原2020 PGI notebook复现**（用 LSQR+Tikhonov，非 ProjectedGNCG+PGI） | 整改落实报告02；DO-27运行证据包 |
| EVD-ALGO-002 | matrix-free 算子梯度、MCMC 诊断与端到端链路；src/geodeepbayes | adjoint dot rel_err；rank-R̂；bulk/tail ESS；MCSE；k-NN KL；MAP misfit | Synthetic-run | validation/runs/synthetic-block-20260717 / synthetic-block-20260717 | 数值推断负责人 / 2026-07-17 | gravity/magnetic 算子 Jv/Jᵀv 三类梯度测试通过(adjoint dot rel_err≈1e-16)；rank-R̂/bulk-tail-ESS/MCSE 与 k-NN KL 模块在已知分布验证通过；小块状模型端到端 MAP→POD→MH→诊断→IG 链路 R̂<1.05、ESS>100 | src/geodeepbayes/{forward,diagnostics,divergence,sampling,benchmarks}；tests/ |

任何证据升级都必须同时记录证据包路径、生成日期、责任人、代码/数据SHA-256和审批记录。没有证据包的数字保持原状态。

## 字段级锚点

| evidence_id | exact_anchor | source_span |
|---|---|---|
| EVD-PHYS-001 | `附录1::证据与使用边界` | 附录1物性机制与先验表；附录13 LogN_A表；附录14先验条目 |
| EVD-TARGET-001 | `附录2::2.1.3 P10/P50/P90靶体潜力情景定义` | 附录1、2、10—12全部靶体体积/潜力情景表 |
| EVD-RESOURCE-001 | `附录11::资源分类边界` | 所有“正式资源量须……”合规交接语句 |
| EVD-ALGO-001 | `附录3::算法选型总决策流程图` | 附录3算法配置；canonical附录7算法效率计划 |
| EVD-BENCH-001 | `附录4::数据性质声明` | 附录4全部性能目标表 |
| EVD-FIELD-001 | `附录5::5.1 真实矿区验证计划` | 附录5现场留出方案；附录6命中率目标 |
| EVD-IP-001 | `附录7::证据状态：Planned` | 附录6、7论文、专利、软件及示范计划 |
| EVD-FIN-001 | `附录8::数据性质声明` | 附录6成本假设；附录8全部财务表 |
| EVD-UX-001 | `附录9::工程状态：Planned` | 附录9时长、功能和操作清单 |
| EVD-PPC-001 | `附录12::统计契约` | 附录2、9—12 PPC结构化字段与验收表 |
| EVD-SBC-001 | `附录5::5.1.2 验证指标体系` | 参数覆盖/SBC计划 |
| EVD-COMPUTE-001 | `算力说明::零、唯一可复算benchmark矩阵` | B01—B05及Observed回写字段 |
| EVD-OPEN-001 | `validation::open-data-20260717-03` | 公开数据主清单184文件、MT清单421文件及8类选定格式/资产检查 |
| EVD-SYNTH-001 | `validation::do27-simpeg-20260717-06` | 原393660单元/961观测输入读取；降阶1152单元/121观测的两个单物理正演与正则化反演；磁法经修复后收敛(stop_code=2)；非PGI复现 |
| EVD-ALGO-002 | `validation::synthetic-block-20260717`；`src::geodeepbayes.{forward,diagnostics,divergence,sampling,benchmarks}`；`tests::{forward,diagnostics,divergence,sampling}` | gravity/magnetic matrix-free Jv/Jᵀv 三类梯度测试；rank-R̂/bulk-tail-ESS/MCSE/k-NN KL 已知分布验证；小块状端到端链路(metrics.json: max_rhat=1.017, min_ess=344) |
