# WP0 Edge Case Hunter Review Prompt

请在独立会话中调用`bmad-review-edge-case-hunter`技能，审查以下文件：

- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/整改台账03.md`
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/主张-证据映射03.md`
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/evidence-status-03草案.md`
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/基线冻结03.sha256`
- `_bmad-output/planning-artifacts/research/贝叶斯思想与重磁电电磁深度融合技术体系/修改计划03-执行日志.md`
- `_bmad-output/implementation-artifacts/spec-wp0-freeze-remediation-baseline.md`

审计规格I/O矩阵全部边界：正常文件、缺失文件、无证据主张、证据范围冲突；检查哈希清单范围和可解析性、重复/缺失整改ID、正式`evidence-status.md`是否未变。仅报告未处理边界案例，给文件、行号和修正动作，不修改文件。
