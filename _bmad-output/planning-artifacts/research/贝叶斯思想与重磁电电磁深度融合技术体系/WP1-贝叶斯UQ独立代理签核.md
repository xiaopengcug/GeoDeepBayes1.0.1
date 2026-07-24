# WP1贝叶斯/UQ独立代理角色签核

> 状态：**PASS**。这是非真人AI代理的独立技术复审签核，不是真人签字、机构背书、执业鉴证或外部认证。

- 角色：独立贝叶斯理论与UQ复审代理（非真人AI代理角色，不代表真人、机构、执业资格或外部认证）
- 签核输入根：`a773824fd0b18afe8ddb8c7bb4e55f3886c9c137b9651536e6c5fef7a5027335`
- 输入成员：16个，包含验证器和外置锚。
- 完整性核验：16个成员逐文件SHA-256与清单一致；按声明的路径排序、行格式及末尾LF重新计算所得根与上述根一致。
- 理论影响核验：02章、03章、附录2/4/5/12/14、toy配置/worker/统计结果的冻结哈希相对上一已签核理论版本未变化；唯一DAG、联合$\Sigma$、共享标量Gamma尺度、单一$\nu$、proper条件、Full/Empirical Bayes边界及五类校准无回归。
- 发布事务核验：runner使用独占锁、固定事务工件和write-ahead journal；journal先写临时文件、flush到稳定存储后原子替换，再按output/anchor阶段推进。中断恢复统一回滚到先前一致的output与anchor对。
- 截断恢复核验：journal无法解析时，runner依据固定`.publish-old`、anchor备份及临时工件执行确定性回滚并清除残留；验证器显式注入截断JSON journal，复核恢复前后manifest与anchor哈希不变且无锁、journal或事务残留。
- 负例核验：验证器覆盖journal写入后、旧output移动后、新output移动后、anchor移动后等中断阶段，并在每次`RecoverOnly`后重新执行完整toy包验证。
- 验证结果：`validate-wp1.ps1 -AllowPendingSignoff`及`-SelfTest -AllowPendingSignoff`均PASS。
- 当前结论：**PASS**；本输入根范围内未发现阻断最终贝叶斯/UQ签核的P0或P1残留。
