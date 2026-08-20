# Codex Project Hub 最终验收记录

> **技术验收：PASS。首次公开发布：NO-GO。** 2026-08-20 已完成对准确 clean-root 源提交的最终实测；当前 NO-GO 只来自尚未完成的治理、历史边界、远端安全报告配置与显式发布授权，不来自测试或截图失败。

| 字段 | 验收值 |
|---|---|
| 验收时间 | 2026-08-20 约 16:00–16:10（UTC+08:00） |
| 分支 | `main` |
| 被测 clean-root 源提交 | `afadcda81bc6a649b8a38992f03a9b307454758f` |
| 提交形态 | 0 parents；130 tracked files |
| 操作系统 | Windows 11 Pro 10.0.26200 |
| Python | 3.11.9 |
| Node.js / npm | 24.18.0 / 11.16.0 |
| Git | 2.55.0.windows.3 |
| 详细证据 | [TEST_REPORT.md](TEST_REPORT.md) |

本记录和测试报告的后续提交属于 **evidence-only** 文档更新，不改变被测源代码。任何代码、依赖锁、安装/启动脚本或测试变化都必须重新执行受影响门禁，不能沿用本结论。

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
- [x] 后端 pytest：77 passed；常规门禁 6 warnings，展开复跑仅 1 条可见非安全阻断 `StarletteDeprecationWarning`。
- [x] 前端 Vitest：15/15。
- [x] TypeScript 与 Vite 生产构建：211 modules；TypeScript 检查由 `tsc -b` 完成。
- [x] Playwright：4 passed；文档截图用例在常规门禁中按设计 opt-in skipped，随后独立执行 1 passed。
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
- [x] `docs/images/dashboard-overview.webp` 与 `docs/images/project-dashboard.webp` 来自运行中的应用和合成数据；均为 1920×1080，并完成隐私、来源与渲染检查。
- [x] 16 个 Markdown 的 46 个本地目标无断链；3 个 GitHub Issue YAML 可解析。
- [x] clean-root 跟踪集与历史完成秘密/资源扫描；旧历史被明确判定为不可发布。
- [x] Release Notes 中可填写的测试与验证结果均由本记录和测试报告支持。

截图验证已经完成，不再是发布阻断项。

## 未执行项

- [ ] 独立性能基准：未执行。没有可公开复现的夹具规模、硬件、冷热缓存、重复次数与统计方式，因此不声明性能提升。
- [ ] 独立 lint：仓库未配置 lint script；TypeScript 检查已由生产构建执行。本项不是失败，也不标记为通过。

## 当前发布阻断项

以下事项在完成并记录批准前持续阻断首次公开发布：

1. 所有者必须选定项目许可证，确认版权主体与初始年份，并加入获批准的最终许可证文件；当前不得声称已获得开源授权。
2. 所有者必须完成 `Codex` 名称的品牌决定或法律/品牌复核；非官方声明不能替代该决定。
3. 所有者必须对首次公开发布、远端写入、tag 与 Release 给出显式批准。
4. 只能从已审计的 clean-root 历史发布；绝不能推送、合并或恢复旧历史中的内部内容。
5. 远端 Private Vulnerability Reporting 当前未启用；必须在获得批准后启用并复核真实私密报告入口，不得虚构私密邮箱或让用户在公开 Issue 中披露漏洞。

## 验收结论

准确 clean-root 源提交 `afadcda81bc6a649b8a38992f03a9b307454758f` 的安装、自动化测试、响应式检查、截图、启停、依赖审计、秘密扫描与公开文档门禁均通过，技术验收结论为 **PASS**。

由于上述 5 项发布治理阻断尚未解除，首次公开发布结论保持 **NO-GO**。解除阻断并取得显式批准前，不得配置发布远端、推送、打 tag 或创建 GitHub Release。
