# GeoDeepBayes

贝叶斯重磁电电磁联合反演研究框架（TRL 3-4）。

> 证据状态: 本代码库处于第一阶段（代码奠基 + 可验证核心模块）。matrix-free 算子、
> 诊断、k-NN KL、采样与 POD 已实现；多方法联合反演、RJMCMC/并行回火完整实现、
> benchmark 实测、矿区钻孔留出验证属后续阶段。

## 安装

项目工程门固定使用 Python 3.11.15、uv 0.11.29 和仓库内 `uv.lock`：

```bash
uv sync --frozen --extra dev
```

## 测试

```bash
uv run --frozen pytest tests/ -v
```

WP6契约、治理与故障注入门：

```powershell
pwsh -NoProfile -File "_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/validate-wp6.ps1" -SelfTest
```

## 模块

- `geodeepbayes.forward` —— 重力/磁法正演算子（matrix-free Jv/Jᵀv）
- `geodeepbayes.diagnostics` —— rank-R̂ / bulk-tail-ESS / MCSE
- `geodeepbayes.divergence` —— k-NN (KSG) KL 估计器
- `geodeepbayes.sampling` —— 自适应 Metropolis、POD 降维
- `geodeepbayes.benchmarks` —— 小规模合成验证

## 文档

技术体系文档与审查/整改闭环见 `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/`。

## Paper 01 RASTI 发布候选

论文 01 的稿件、修订证据、重放摘要、发布边界和人工核验清单见
[`papers/paper01-rasti/`](papers/paper01-rasti/README.md)。正式 GitHub tag/release
及 Zenodo DOI 在通讯作者完成人工核验并明确放行前保持暂停。
