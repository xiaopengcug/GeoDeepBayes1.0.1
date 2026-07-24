# empymod第三方参考来源记录

- 包：`empymod==2.6.0`
- 用途：WP3的有限bipole频域/时域第三方参考；不构成现场验证。
- 安装环境：`validation/wp3-physics/.venv-oracle`（环境二进制不纳入签核根或版本产物）。
- `pip freeze`：见`requirements-lock.txt`。
- 许可证：Apache License 2.0；安装包许可证SHA-256为`cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`。
- 安装元数据`METADATA` SHA-256：`f99caf2ddb3b778935e53f6ec56f5f6a1d1fd2ef61bada38d69bfd99debe8b52`。
- 安装记录`RECORD` SHA-256：`75e0aab8caeab014b4fe7e3b7c42063ef1c294b6461b03633d9c3e049a1c7ccb`。
- `empymod/__init__.py` SHA-256：`c7951a545a1a5ad1d641ac61e3fd1af556fa7d9fd2f70d4cb3e3081e00518a03`。
- API锚：`empymod.bipole(src, rec, depth, res, freqtime, signal, ..., msrc, srcpts, mrec, recpts, strength, ht, htarg, ft, ftarg)`。
- 坐标约定：本参考使用East-North-Depth，正z向下；有限源/接收器用`[x0,x1,y0,y1,z0,z1]`，方向接收器用`[x,y,z,azimuth,dip]`。

许可证全文随本地安装环境保留；本文件仅记录许可证标识与可复核哈希，避免把虚拟环境二进制纳入文档根。
