---
title: 'WP9 四专项差异化审查门禁'
type: 'bugfix'
created: '2026-07-27'
status: 'done'
review_loop_iteration: 1
baseline_commit: '50e25166f8897f0fc6e82cbadbc3c4f0a98c14d5'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 四份 WP9 review 使用相同检查模板，validator 不能拒绝同质化退化。

**Approach:** 增加专项证据检查、结构门禁和负例；只验证证据与边界，不重判科学结论。

## Boundaries & Constraints

**Always:** 保留 `identity_type=automated-ai-specialist-evidence-review` 和非人类边界。

**Ask First:** 改变 finding 状态或科学验收口径。

**Never:** 冒充独立人类专家。

</frozen-after-approval>

## Code Map

- `validation/wp9/run_specialist_reviews.py` -- review 生成器。
- `validation/wp9/validate_wp9.py` -- 退化门禁。
- `validation/wp9/build_finding_registry.py` -- 台账到 registry 的确定性映射。
- `tests/validation/test_wp9_acceptance.py` -- 回归与负例。

## Tasks & Acceptance

**Execution:**
- [x] 四专项分别增加 `forward_unit_consistent`、`sbc_coverage_recorded`、`discretization_converged`、`gates_blocked_on_fail`。
- [x] 缺专项键或四份键集合相同，返回 `reviews:template-degraded` 和退出码 4。
- [x] 增加 Rejected、同质模板、身份误标三类负例并重发 review/manifest。
- [x] 严格校验 registry schema、动态计数、ID 唯一性、台账 SHA/逐行映射和非空安全证据路径。
- [x] 严格校验 review 文件集合、专项身份、公共/专项键、布尔值、作用域声明和覆盖集合。
- [x] 默认 validator 只审计/验 manifest；发布必须显式 `--publish`，阻断时不得硬编码为 Passed。
- [x] manifest 使用精确且唯一的成员闭包，纳入生成器、validator、台账、主张映射和审查产物。

**Acceptance Criteria:**
- Given 四份 review，when 比较 `checks`，then 各含对应专项键且集合不全同。
- Given 任一退化负例，when 运行 validator，then 以退出码 4 拒绝。

## Verification

- `python validation/wp9/run_specialist_reviews.py`
- `python validation/wp9/validate_wp9.py --publish`
- `python validation/wp9/validate_wp9.py`
- `pytest tests/validation/test_wp9_acceptance.py -q`

## Implementation Notes

- 四专项键分别绑定 WP8 正演参考一致性、SBC、三层离散化收敛记录，以及 CI 失败阻断配置；自动审查不重判科学结论。
- validator 默认路径为只读；仅 `--publish` 重发报告、状态与 manifest。
- `final-gates-v1.json` 的历史登记与本地证据审计解耦；后续环境规格已把它更新为当前锁定环境复跑记录。
- 本地验证：`22 passed`；WP9 audit 与 manifest replay 均通过。

## Review Findings Addressed

- 消费者端现重放 WP8 方法级专项记录、九方法唯一集合、completion 投影、CI 中实际 WP9 阻断步骤，以及三个 supplement NPZ 的传递哈希；不再只信 review 自报布尔值。
- 工程 review 绑定 `.github/workflows/ci.yml`，其余专项绑定方法级验证记录；workflow、传递资产和生成/验证程序均进入精确 manifest 成员集。
- registry 增加精确字段、canonical `PRIMARY_WP`、evidence claim/形状校验；坏 JSON、坏结构和 manifest 非法成员统一 fail-closed。
- 阻断发布不再输出 package-level `Passed`/`Approved`；三类核心负例直接验证 `main()` 返回 4。
- 复审后相关验证增至 `22 passed`，WP9 默认只读审计与 manifest replay 通过。

## Suggested Review Order

1. `validation/wp9/validate_wp9.py`：先看 registry/review/WP8 证据重放与 fail-closed 行为。
2. `validation/wp9/run_specialist_reviews.py`：核对四专项键、证据绑定和非人类身份边界。
3. `.github/workflows/ci.yml`：确认 WP9 审计位于 required gate 且未设置 `continue-on-error`。
4. `tests/validation/test_wp9_acceptance.py`：复核 Rejected、同质模板、身份误标、底层证据退化及阻断发布负例。
5. `validation/wp9/manifest-v1.json` 与四份 review：核对重发后的实际闭包。
