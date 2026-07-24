---
title: '安装SimPEG与discretize并执行DO-27验证'
type: 'chore'
created: '2026-07-17'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'NO_VCS'
context:
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/整改落实报告01.md'
  - '{project-root}/_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/runs/open-data-20260717-03/results.json'
  - '{project-root}/_bmad-output/planning-artifacts/research/open-data/mining_geophysics/Zenodo_DO27_kimberlite_gravity_magnetic_joint_inversion_synthetic/source_record.zenodo.json'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** DO-27目前只完成数据资产验证，完整反演被标记为Blocked；用户要求必须安装`simpeg/discretize`并实际运行验证。

**Approach:** 在项目隔离虚拟环境中安装并锁定Python 3.11兼容版本，解包DO-27原始研究代码，先审计2020年`examples/PGI_joint`接口与现代SimPEG兼容性，再实际执行可复算的重力—磁法正演/反演验证。原notebook若不能直接运行，则保留失败证据并用现代API兼容入口验证同一DO-27数据、网格和真值，不把兼容性烟测冒充原论文完整PGI复现。

## Boundaries & Constraints

**Always:** 使用独立`.venv-do27`，记录Python、SimPEG、discretize、NumPy、SciPy及安装锁文件；输入只读且逐文件哈希；记录命令、时间、随机种子、数值指标和输出哈希；区分正演一致性、单物理反演、联合反演与原PGI复现。

**Ask First:** 需要GPU/云费用、安装系统级驱动、修改全局Python、下载清单外数据或单次预计运行超过4小时时暂停确认。

**Never:** 不修改原始开放数据；不因依赖安装成功就升级`Synthetic-run`；不隐藏旧API异常、数值不收敛或资源不足；不把现代兼容验证称为原2020 notebook逐单元复现。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 依赖安装 | Python 3.11和网络可用 | 隔离环境可导入SimPEG/discretize并冻结版本 | 安装失败保留日志并停止证据升级 |
| 原notebook兼容 | 旧`SimPEG.PF`接口仍可迁移 | 执行并记录原数据指标 | API差异形成兼容矩阵 |
| 原notebook不兼容 | 2020分支依赖不可用于Python 3.11 | 使用现代API验证同一真值/观测并明确降级范围 | 不标为原PGI复现 |
| 数值运行失败 | 不收敛、内存或超时 | 保存失败点、资源和部分指标 | 保持Blocked/Failed |

</frozen-after-approval>

## Code Map

- `.venv-do27/` -- 隔离Python运行环境，不进入发布清单。
- `_bmad-output/.../validation/do27/requirements.lock.txt` -- 精确依赖版本。
- `_bmad-output/.../validation/do27/run_do27_validation.py` -- 解包、兼容审计和现代SimPEG验证入口。
- `_bmad-output/.../validation/runs/do27-*/` -- 日志、指标、环境和证据manifest。
- `_bmad-output/.../evidence-status.md`、`整改落实报告01.md`、`manifest.yaml` -- 状态及证据回写。

## Tasks & Acceptance

**Execution:**
- [x] `.venv-do27` -- 创建隔离环境，安装`simpeg`、`discretize`及运行依赖并冻结版本。
- [x] DO-27源码 -- 解包到验证工作目录，核对归档与关键输入哈希。
- [x] `run_do27_validation.py` -- 实现旧API兼容审计、现代SimPEG导入、DO-27模型/观测读取、正演和反演指标。
- [x] `validation/runs/do27-*` -- 实际运行并生成stdout/stderr、环境、配置、指标和证据manifest。
- [x] 治理文件 -- 根据真实结果回写Blocked/Failed/Synthetic-run，更新哈希并运行治理。

**Acceptance Criteria:**
- Given隔离环境，when执行导入检查，then输出精确版本且全局Python环境不被依赖安装修改。
- GivenDO-27归档，when运行验证，then输入哈希与开放数据清单一致且真值、网格、重磁观测均被实际读取。
- Given现代SimPEG运行入口，when执行验证，then至少完成重力和磁法正演及一个有明确终止条件的反演运行，并报告残差、模型误差、迭代数和耗时。
- Given旧notebook不兼容，when写回证据，then明确记录未复现部分，不把兼容验证描述为完整PGI复现。

## Spec Change Log

## Design Notes

原环境锁定于2019年的NumPy 1.17、discretize 0.4.10及SimPEG私有分支`examples/PGI_joint`，无法合理假定能直接安装到Python 3.11。优先保留原始资产和兼容审计，再用当前正式SimPEG API建立可维护验证入口。

## Verification

**Commands:**
- `.venv-do27\Scripts\python -c "import simpeg, discretize; print(simpeg.__version__, discretize.__version__)"` -- 导入成功并输出锁定版本。
- `.venv-do27\Scripts\python ...\run_do27_validation.py --archive <DO27.zip> --output <run>` -- 生成实际指标和证据包。
- `& .\validate-governance.ps1` -- 证据状态、运行包和发布哈希一致。

## Suggested Review Order

**验证入口与证据语义**

- 从参数边界、真实数值运行到证据生成的主入口。
  [`run_do27_validation.py:186`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/do27/run_do27_validation.py#L186)

- 仅在全部检查通过时升级，否则诚实标记失败。
  [`run_do27_validation.py:313`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validation/do27/run_do27_validation.py#L313)

- 最新证据注册为失败运行并明确未收敛边界。
  [`evidence-status.md:22`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/evidence-status.md#L22)

**治理与复算**

- 治理核对状态、停止码、输出哈希和隔离环境版本。
  [`validate-governance.ps1:168`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-governance.ps1#L168)

- 契约测试纳入最新DO-27失败运行清单。
  [`validate_contracts.py:56`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/contracts/validate_contracts.py#L56)

- 发布清单固定脚本、配置、日志与结果哈希。
  [`manifest.yaml:64`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/manifest.yaml#L64)

**验收结论**

- 整改报告区分单物理降阶验证、联合反演与PGI复现。
  [`整改落实报告01.md:45`](../planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/整改落实报告01.md#L45)
