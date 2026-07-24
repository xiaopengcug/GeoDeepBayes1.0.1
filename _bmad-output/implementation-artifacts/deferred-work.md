- source_spec: `H:\GeoDeepBayes1.0.1\_bmad-output\implementation-artifacts\spec-revise-bayesian-fusion-review01.md`
  summary: 按审查意见01修订附录1—14中的物性、资源量、算法配置、公式、CRS、先验与验证规范。
  evidence: 附录整改可作为独立文档集审查和交付，与正文理论整改存在引用依赖但不阻断正文先行修正。

- source_spec: `H:\GeoDeepBayes1.0.1\_bmad-output\implementation-artifacts\spec-revise-bayesian-fusion-review01.md`
  summary: 统一附录7、参考文献和算力说明的canonical版本，并建立manifest及证据状态登记。
  evidence: 版本治理和证据登记是可独立验收的发布管理工作，拆分可降低正文修订的上下文与误操作风险。
- source_spec: `_bmad-output/implementation-artifacts/spec-wp1-rewrite-joint-probability-uq-core.md`
  summary: 在WP6建立运行包外部数字签名、可信时间戳或受保护登记锚。
  evidence: WP1可用目录外根哈希发现意外漂移，但没有项目级密钥、签名者身份和受保护存储，无法抵御脚本、结果、清单与本地锚同时被重写。
- source_spec: `_bmad-output/implementation-artifacts/spec-wp2-correct-numerical-inference-theory.md`
  summary: 为WP2运行证据增加仓库外冻结签名、可信时间戳或独立可信摘要。
  evidence: 当前manifest及文件哈希只能检测非同步篡改；抗攻击真实性需要WP6已规划的外部证据治理基础设施。
- source_spec: `_bmad-output/implementation-artifacts/spec-wp2-correct-numerical-inference-theory.md`
  summary: 在WP6中用Windows ACL、独立服务身份或可信执行环境隔离toy worker的stage写权限。
  evidence: 同一用户且拥有toy目录写权限的恶意进程可伪造本地bearer capability；WP2的capability仅作为防误用门，不构成操作系统安全边界。
- source_spec: `_bmad-output/implementation-artifacts/spec-wp2-correct-numerical-inference-theory.md`
  summary: 在WP6运维治理中增加未被active pointer引用的孤儿版本保留期、配额和安全垃圾回收。
  evidence: 硬中断后活动指针始终有效，但可能遗留不可达版本目录并长期占用磁盘。
- source_spec: `_bmad-output/implementation-artifacts/spec-wp6-engineering-contracts-ci-evidence-governance.md`
  summary: 升级GitHub Pro或调整仓库可见性后，为main启用Ubuntu/Windows required checks。
  evidence: GitHub branch protection API对个人账户私有仓库返回403并明确要求升级Pro或改为公开；当前双平台门已执行但平台不提供强制合并保护。
