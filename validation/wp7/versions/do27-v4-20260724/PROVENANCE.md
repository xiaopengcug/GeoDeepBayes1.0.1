# DO-27 v4 数值附件来源与许可

本目录中的 `raw-numerics.npz` 是 GeoDeepBayes 项目在 2026-07-24 运行现代 SimPEG API 降阶兼容性验证时产生的冻结数值附件。它包含从上游 DO-27 合成资产读取或投影的重力/磁法数据与真值、降阶响应矩阵、候选解和正则化参数；它不是野外观测，也不是原始 notebook 的完整复现。

上游来源：Thibaut Astic，*simpeg-research/Astic-2020-JointInversion: Joint inversion of synthetic potential fields data based on the DO-27 kimberlite pipe*，版本 1.0.0，Zenodo DOI `10.5281/zenodo.3633239`。

- 上游 Zenodo 来源记录：`source_record.zenodo.json`
- 上游 MIT 许可证全文：`UPSTREAM-LICENSE-MIT.txt`
- 上游归档 SHA-256：`c98d1abd655e2bb2656d1ce97347c4def9619012acabceeffc7192b83a19a80e`
- 本目录 `raw-numerics.npz` SHA-256：`e5b866e84922bb428474a422743dbf4d8392d5dbe1b72cd76cabb5b589ad47b2`
- 生成与输入绑定：`run-manifest.json`、`evidence-run-v2.json`

上游脚本、notebook 与合成资产按所附 MIT License 许可再使用。GeoDeepBayes 自有代码和论文发布包的其他部分仍受仓库 Proprietary 许可约束；本说明不把 MIT 许可扩展到这些其他部分。

证据边界：本附件只支持 DO-27 同源数据的现代 API 降阶双单物理读取、正演、GCV 选参和 LSQR 运行兼容性陈述；不证明模型恢复、PGI、联合反演、贝叶斯推断、野外有效性或原 notebook 复现。
