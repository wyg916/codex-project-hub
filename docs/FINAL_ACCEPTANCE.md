# Codex Project Hub 最终验收记录

> **技术验收：PASS。首次公开发布准备：GO。** 2026-08-20 已完成 clean-root 候选实测；所有者随后批准 Apache-2.0、Copyright 2026 wyg、`v0.1.0`、保留品牌与准确目标仓库，并授权首次公开发布。GitHub Private Vulnerability Reporting 已启用并复核。

| 字段 | 验收值 |
|---|---|
| 验收时间 | 2026-08-20 约 17:00–17:10（UTC+08:00） |
| 分支 | `chore/open-source-release`（计划推送为远端 `main`） |
| 被测发布源提交 | `531ce8562b724600b7b052a11165ca1bff132e42` |
| 提交形态 | 0-parent clean-root 历史；3 commits；132 tracked files |
| 操作系统 | Windows 11 Pro 10.0.26200 |
| Python | 3.11.9 |
| Node.js / npm | 24.18.0 / 11.16.0 |
| Git | 2.55.0.windows.3 |
| 详细证据 | [TEST_REPORT.md](TEST_REPORT.md) |

初始 0-parent 源提交 `afadcda…` 已完成全新安装验收；`531ce85…` 仅新增/同步 Apache-2.0 法律文本、发布状态、GitHub 私密安全入口与包级 license metadata，不改变依赖解析、应用代码、安装/启动脚本或测试。其上重新执行了完整 `test-all.bat`。本记录和测试报告的后续提交属于 **evidence-only** 文档更新。

## 功能门禁

- [x] 首次启动时项目登记为空，不读取或自动登记任何私有仓库。
- [x] 可通过界面登记、编辑、移除和切换合成本地 Git 仓库。
- [x] 可识别 Git 根目录、Common Dir、主 Worktree 与 linked Worktree。
- [x] 分支、HEAD、提交、工作区、上游、ahead/behind、merge-base 与已合并状态来自实际只读 Git 命令结果。
- [x] 项目总览、压缩分支拓扑、搜索、筛选、缩放、适配、全屏和布局控制与 README 描述一致。
- [x] 状态元数据、阶段进度、测试证据、阻塞和下一步只来自显式维护内容；缺失时显示“未维护”、`NOT_RUN` 或 `UNKNOWN`。
- [x] 移除登记不会删除底层仓库、Worktree 或分支。
- [x] watchdog、有界轮询与本机 WebSocket 在自动化门限内收敛到最新 Git 状态。

## 安全与隐私门禁

- [x] Git 扫描只使用精确只读命令白名单，并以 subprocess 参数数组调用。
- [x] 应用不会自动执行 fetch、merge、rebase、reset、clean、push、删除分支或修改被监控业务代码。
- [x] 原生目录选择和本机打开操作默认禁用，仅在 `CPC_ENABLE_SYSTEM_ACTIONS=1` 时启用。
- [x] 启用本机打开操作后，请求路径必须与已登记仓库根目录或 Worktree 完全匹配；文件、UNC、device path 与 reparse point 被拒绝。
- [x] 服务默认绑定 `127.0.0.1`，Host、HTTP/WebSocket Origin、CORS、请求/消息大小和连接容量边界通过测试。
- [x] 远端 URL、Git 错误和 API 错误中的凭据形态已脱敏；运行日志作为本机敏感数据被忽略且未提交。
- [x] 公开截图不含真实用户名、机器特定绝对路径、私有项目名、凭据或客户数据。
- [x] E2E、截图和演示只使用合成仓库与独立本机数据目录。

## 自动化质量门禁

- [x] 全新 `install.bat`：新建虚拟环境、锁校验、Python/npm 安装、Playwright Chromium、生产构建、`pip check` 与 SQLite 初始化均成功。
- [x] 后端 pytest：77 passed；1 条已记录、非安全阻断的 `StarletteDeprecationWarning`；333.88s。
- [x] 前端 Vitest：15/15；94.81s。
- [x] TypeScript 与 Vite 生产构建：211 modules；TypeScript 检查由 `tsc -b` 完成；2.84s。
- [x] Playwright：4 passed；文档截图用例在常规门禁中按设计 opt-in skipped；51.7s。公开截图此前独立 capture 1 passed。
- [x] 1366×768、1920×1080、2560×1440 三分辨率检查。
- [x] 正常业务流程 console error 与 page error 均为 0。
- [x] `test-all.bat` 完整本地门禁返回 PASS。
- [x] `一键启动.bat` 连续两次启动、HTTP 200、进程归属与 `stop.bat` 受控停止。
- [x] `pip-audit`、npm 生产/完整审计均报告 0 个已知漏洞；npm provenance 为 192 signatures / 65 attestations。
- [x] Gitleaks 8.30 canary 有效，原工作区与 clean-root 历史均为 0 findings。
- [x] 公开内容的秘密、绝对路径、历史私有项目名和资源来源复核。

仓库没有独立 lint script，因此没有把 lint 虚构为已运行门禁。pytest warning 已记录为后续 HTTPX 2.x 测试栈迁移事项，不影响本次技术验收，也不声称已经修复。

## 发布资料门禁

- [x] `README.md` 与 `README.zh-CN.md` 的安装、配置、功能边界、徽章和截图来自当前实现。
- [x] `SECURITY.md`、`PRIVACY.md`、`CONTRIBUTING.md`、`SUPPORT.md`、`CODE_OF_CONDUCT.md` 与 Issue/PR 模板完成复核。
- [x] `THIRD_PARTY_NOTICES.md` 与 Python requirements/lock、npm lock 和发布构建一致。
- [x] `LICENSE` 与 Apache 官方 2.0 文本规范化后逐字一致；`NOTICE`、README 与 npm package metadata 均为 Copyright 2026 wyg / Apache-2.0。
- [x] `docs/images/dashboard-overview.webp` 与 `docs/images/project-dashboard.webp` 来自运行中的应用和合成数据；均为 1920×1080，并完成隐私、来源与渲染检查。
- [x] 16 个 Markdown 的 51 个本地目标无断链；3 个 GitHub Issue YAML 可解析。
- [x] clean-root 跟踪集与历史完成秘密/资源扫描；旧历史被明确判定为不可发布。
- [x] Release Notes 中可填写的测试与验证结果均由本记录和测试报告支持。

截图验证已经完成，不再是发布阻断项。

## 未执行项

- [ ] 独立性能基准：未执行。没有可公开复现的夹具规模、硬件、冷热缓存、重复次数与统计方式，因此不声明性能提升。
- [ ] 独立 lint：仓库未配置 lint script；TypeScript 检查已由生产构建执行。本项不是失败，也不标记为通过。

## 已解除的发布阻断与执行约束

- [x] 所有者选择 Apache-2.0，并确认 Copyright 2026 wyg。
- [x] 所有者决定保留 `Codex Project Hub`，接受独立非官方项目声明下的品牌风险。
- [x] 所有者明确批准目标 `wyg916/codex-project-hub`、版本 `v0.1.0`、推送、tag 与 Release。
- [x] GitHub Private Vulnerability Reporting 已通过 API 启用并返回 `enabled: true`。
- [x] 发布源保持 0-parent clean-root；旧本地历史与旧 refs 不进入远端。

发布执行仍必须只推送准确的 clean-root HEAD 到空仓 `main`，禁止 `--all`、`--mirror`、force push 或任何旧历史 ref；创建 tag/Release 前必须等待 GitHub CI 通过。

## 验收结论

clean-root 发布源提交 `531ce8562b724600b7b052a11165ca1bff132e42` 的法律/包元数据同步与完整自动化门禁通过；其应用源基线的全新安装、响应式检查、截图、启停、依赖审计和秘密扫描证据仍有效。技术验收结论为 **PASS**，所有者发布批准完整，首次公开发布准备结论为 **GO**。
