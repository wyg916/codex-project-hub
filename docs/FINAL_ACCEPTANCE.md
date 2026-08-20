# Codex Project Hub 最终验收记录

> **当前状态：待验收。** 本文件是 2026-08-20 首次公开发布准备使用的可维护模板。根代理尚未完成对准确发布候选提交的最终实测，因此所有门禁均保持未勾选，不构成质量或发布通过声明。

| 字段 | 值 |
|---|---|
| 计划验收日期 | 2026-08-20 |
| 验收完成时间 | 待填写 |
| 分支 | `codex/multi-project-control-center-mvp` |
| 准确提交 SHA | 待填写 |
| 操作系统与版本 | 待填写 |
| Python 版本 | 待填写 |
| Node.js / npm 版本 | 待填写；Node.js 必须满足 `^20.19.0 || >=22.12.0` |
| 详细测试证据 | [TEST_REPORT.md](TEST_REPORT.md) |

## 功能门禁

- [ ] 首次启动时项目登记为空，不读取或自动登记任何私有仓库。
- [ ] 可通过界面登记、编辑、移除和切换合成本地 Git 仓库。
- [ ] 可识别 Git 根目录、Common Dir、主 Worktree 与 linked Worktree。
- [ ] 分支、HEAD、提交、工作区、上游、ahead/behind、merge-base 与已合并状态来自实际只读 Git 命令结果。
- [ ] 项目总览、压缩分支拓扑、搜索、筛选、缩放、适配、全屏和布局控制与当前 README 描述一致。
- [ ] 状态元数据、阶段进度、测试证据、阻塞和下一步只来自显式维护内容；缺失时显示“未维护”、`NOT_RUN` 或 `UNKNOWN`。
- [ ] 移除登记不会删除底层仓库、Worktree 或分支。
- [ ] watchdog、有界轮询与本机 WebSocket 能在测试门限内收敛到最新 Git 状态。

## 安全与隐私门禁

- [ ] Git 扫描只使用文档白名单中的只读命令，并以 subprocess 参数数组调用。
- [ ] 应用不会自动执行 fetch、merge、rebase、reset、clean、push、删除分支或修改被监控业务代码。
- [ ] 原生目录选择和本机打开操作默认禁用，仅在 `CPC_ENABLE_SYSTEM_ACTIONS=1` 时启用。
- [ ] 启用本机打开操作后，请求路径必须与已登记仓库根目录或 Worktree 完全匹配。
- [ ] 服务默认绑定 `127.0.0.1`，CORS/WebSocket Origin 限制与 `CPC_ALLOWED_ORIGINS` 文档一致。
- [ ] 远端 URL、Git 错误和 API 错误的凭据形态已脱敏；运行日志作为本机敏感数据被忽略且未提交，任何对外片段均经人工脱敏审查。
- [ ] 公开截图不含真实用户名、机器特定绝对路径、私有项目名、凭据或客户数据。
- [ ] E2E、截图和演示只使用合成仓库与独立本机数据目录。

## 自动化质量门禁

下列项目只有在准确提交上实际执行并保留输出后才能勾选。结果、耗时与失败原因填写在 [TEST_REPORT.md](TEST_REPORT.md)。

- [ ] 后端 pytest 测试。
- [ ] 前端 Vitest 测试。
- [ ] TypeScript 与 Vite 生产构建。
- [ ] Playwright 端到端测试。
- [ ] 1366×768、1920×1080、2560×1440 三分辨率检查。
- [ ] 正常业务流程浏览器 console 与 page error 检查。
- [ ] `test-all.bat` 完整本地门禁。
- [ ] `一键启动.bat` 连续两次启动、健康身份与 `stop.bat` 受控停止。
- [ ] Python 与 npm 依赖审计。
- [ ] 公开内容的秘密、绝对路径、私有项目名和资源来源复核。

## 发布资料门禁

- [ ] `README.md` 与 `README.zh-CN.md` 的安装、配置、功能边界和截图来自当前实现。
- [ ] `SECURITY.md`、`PRIVACY.md`、`CONTRIBUTING.md`、`SUPPORT.md`、`CODE_OF_CONDUCT.md` 与 Issue/PR 模板完成复核。
- [ ] `THIRD_PARTY_NOTICES.md` 与准确的 Python requirements、npm lock 和发布构建一致。
- [ ] `docs/images/dashboard-overview.webp` 与 `docs/images/project-dashboard.webp` 来自运行中的应用和合成数据，并完成隐私与来源复核。
- [ ] Git 历史、待发布文件、交付归档和二进制资源完成秘密与来源扫描。
- [ ] 最终 Release Notes 中的验证结果已由本记录和测试报告支持。

## 当前发布阻断项

以下事项在解决并记录批准前持续阻断首次公开发布：

1. 项目开源许可证尚未由所有者选定，仓库中不得提前创建 `LICENSE` 或声称已获开源授权。
2. 版权主体与初始年份尚待确认。
3. `Codex` 名称的品牌风险尚待所有者完成决定或法律/品牌复核；非官方声明不能替代该决定。
4. 两张公开截图必须由真实应用和合成数据生成并完成隐私、来源与渲染检查。
5. 本模板中的最终测试、依赖审计、秘密扫描和两次一键启动结果仍待根代理实测填写。

## 验收结论

结论：**待填写**。

填写结论时必须同时记录准确提交 SHA、所有失败或豁免项、证据位置和批准人。不得沿用其他日期、其他提交、某台机器上的 PID、私有仓库数量或历史测试计数作为本次发布证据。
