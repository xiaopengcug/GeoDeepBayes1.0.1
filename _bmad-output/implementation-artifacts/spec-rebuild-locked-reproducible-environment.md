---
title: '重建锁定环境与一键复现闭包'
type: 'bugfix'
created: '2026-07-27'
status: 'done'
review_loop_iteration: 1
baseline_commit: '50e25166f8897f0fc6e82cbadbc3c4f0a98c14d5'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `.venv` 解释器路径失效且 `uv` 不在 PATH，报告中的测试结果当前不可复现。

**Approach:** 按 `pyproject.toml` 和 `uv.lock` 重建环境，验证关键依赖链并实跑约定门禁。

## Boundaries & Constraints

**Always:** 使用冻结依赖；记录环境指纹、命令、退出码和真实计数。

**Ask First:** 修改锁文件或依赖版本。

**Never:** 用系统 site-packages 拼接环境或把失败写成 Passed。

</frozen-after-approval>

## Code Map

- `pyproject.toml`、`uv.lock` -- 依赖锁。
- `.github/workflows/ci.yml` -- 双平台参考命令。
- `_bmad-output/.../validate-wp6.ps1` -- 本地治理入口。

## Tasks & Acceptance

**Execution:**
- [x] 安装固定 uv/Python，执行 `uv sync --frozen --extra dev`。
- [x] 验证 `matplotlib`、`simpeg`、`discretize` 导入与版本。
- [x] 运行 pytest、governance、WP5/WP6/WP7/WP8/WP9 门并记录结果。

**Acceptance Criteria:**
- Given 干净锁定环境，when 执行复现入口，then 不依赖旧 `.venv` 路径。
- Given 任一门失败，when 生成报告，then 总状态不得为 Passed。

## Verification

- `python -m uv lock --check`
- `python -m uv sync --frozen --extra dev`
- `python validation/wp9/run_final_gates.py`
- `python -m uv run --frozen pytest -q`

## Implementation Notes

- 固定工具与环境：uv 0.11.29、CPython 3.11.15；`uv lock --check` 和 `uv sync --frozen --extra dev` 均退出 0，未改锁。
- 本机 `uv` 未进入 PATH 时，governance/WP6/WP7 入口自动回退到 `python -m uv`；在 `uv_on_path=False` 的新 PowerShell 中 governance 与 WP6 self-test 已复验通过。
- 关键依赖：matplotlib 3.11.1、simpeg 0.25.2、discretize 0.12.0、numpy 2.4.6、scipy 1.17.1。
- 统一 runner 最终全量测试：`431 passed, 1 skipped, 119 warnings`，退出 0；governance 与 WP6 self-test 通过。
- WP5、WP7、WP8 当前分别因活动指针签根漂移、运行对签核/归档漂移、方法验证语义重放漂移而阻断；WP9 保存证据包审计通过。
- `final-gates-v1.json` 已更新为 `current-local-rerun` 且总状态 `blocked`，未把局部门通过写成整体验收通过。

## Review Findings Addressed

- 新增 `validation/wp9/run_final_gates.py`：从固定 uv bootstrap 开始，自动执行 pytest、governance、WP5—WP9，保存 exact argv/cwd/起止时间/退出码/stdout/stderr 及哈希，并由退出码派生总状态。
- runner 使用仓库外临时会话目录采集，全部子门结束后一次原子发布，避免 pytest/WP9 在执行窗口读取半更新日志。
- `final-gates-v1.json` 记录 `.python-version`、PowerShell、锁文件、依赖、runner、tracked diff 与 status-path 指纹；所有门日志进入 WP9 精确 manifest。
- WP9 validator 重算日志哈希、stdout/stderr 哈希、pytest 计数、gate status 和 blocking 集合，并对环境/锁/runner 漂移 fail-closed。
- CI required-gates 已显式接入 WP5、WP7、WP8 live gates；本机无 `uv` PATH 时，governance/WP6/WP7 自动使用 `python -m uv`。
- 状态页与落实报告区分“保存证据登记通过”和“当前 live gates 阻断”，不再把本地复跑写为 pending。
- 最终统一复跑：pytest `431 passed, 1 skipped, 119 warnings`；WP9 local audit/manifest 通过；总状态仅由 WP5、WP7、WP8 三门阻断。相关定向回归 `33 passed`。

## Suggested Review Order

1. `validation/wp9/run_final_gates.py`：核对临时采集、原子发布和状态派生。
2. `validation/wp9/gate-logs-v1/*.json`：抽查 pytest、WP5、WP7、WP8、WP9 原始输出与 exact argv。
3. `validation/wp9/final-gates-v1.json`：确认环境指纹、431 计数和三项 blocking 集合。
4. `validation/wp9/validate_wp9.py`：确认日志/计数/阻断集合不再循环自证。
5. `.github/workflows/ci.yml` 与三个 PowerShell wrapper：确认远程 live gates 和 no-PATH fallback。
6. `验收审查意见03.md`、`evidence-status-03.md`、`整改落实报告03.md`：核对保存状态与 live 状态口径。
