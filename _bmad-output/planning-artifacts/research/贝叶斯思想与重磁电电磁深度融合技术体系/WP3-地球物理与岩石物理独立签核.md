# WP3地球物理与岩石物理独立签核

- 状态：PASS
- 审查人：未参与WP3实现的独立地球物理/数值验证代理与独立岩石物理/UQ代理
- 审查范围：Maxwell/扩散、TEM、有限源CSAMT、轴向WFEM、温压/IP/磁性、DOI、RTP/MT条件分支
- 输入版本：`20260718T103914410Z-d1ef8b18ed5d4cf2a761a62570f646db`
- manifest SHA-256：`5ef4fa8be5c5ef9cd3bdc4e7d1cbeee9b7f38a53dfa504bb190c2ef2352d4cb7`
- 成员清单内容根SHA-256：`fec10fed8a4c9982acb3c5adad1600744f41e7eb5940bcff87752a7d2980b7b8`
- 根清单文件SHA-256：`be19013af564d10d8d344e7109718e9f735ddc28980e05cd29f358246a8c335b`
- 证据等级：`Synthetic-run/Reference-regression`
- 自动验证：内部验证PASS；SelfTest PASS（含TEM面积派生小环域、OutputOverride决策类型/维性前置门、DC/MT输入域、journal安全恢复、渐近斜率/波形趋同及既有发布故障断言）；最终地球物理与岩石物理复签均PASS。
- 结论：PASS；两项最终复签均为PASS，P0=0、P1=0，并共同绑定上述版本、manifest、成员内容根和根清单文件。本记录不是人类签名或外部数字签名。

## 独立复核清单

1. 从时间约定独立复写Maxwell、扩散门及TEM电压极性。
2. 核对有限源CSAMT和WFEM四端点/复响应/装置系数量纲。
3. 独立复算DC、MT闭式值，并检查TEM/CSAMT参考来源隔离。
4. 核对IP支持域、Curie–Weiss相态、Pa/K和Biot有效应力。
5. 检查剩磁、低磁纬、MT维性及竞争解释是否正确触发替代分支。
