# Codex Project Hub 最终测试报告

> **技术门禁结论：PASS。发布结论：NO-GO。** 本报告记录 2026-08-20 对准确 clean-root 源提交的最终实测。NO-GO 原因仅为许可证、版权与品牌决定、发布授权、历史边界和远端安全报告配置，详见 [FINAL_ACCEPTANCE.md](FINAL_ACCEPTANCE.md)。

## 1. 测试对象与环境

| 字段 | 实测值 |
|---|---|
| 测试时间 | 2026-08-20 约 16:00–16:10（UTC+08:00） |
| 分支 | `main` |
| 被测 clean-root 源提交 | `afadcda81bc6a649b8a38992f03a9b307454758f` |
| 提交父节点 | 0（root commit） |
| 被跟踪文件 | 130 |
| 操作系统 | Windows 11 Pro 10.0.26200 |
| Python | CPython 3.11.9 |
| Node.js | 24.18.0，满足 `>=22.12.0` |
| npm | 11.16.0 |
| Git | 2.55.0.windows.3 |
| 安装起点 | 全新 `.venv`，按公开安装流程执行 |

本报告及最终验收记录的后续提交属于 **evidence-only** 文档更新，不改变上述被测源代码。若代码、依赖锁、安装/启动脚本或测试发生变化，必须对受影响门禁重新实测并记录新的源提交。

## 2. 全新安装验收

| 门禁 | 结果 | 实测证据 |
|---|---|---|
| `install.bat` | PASS | 从新的 `.venv` 开始并正常退出 |
| Python bootstrap 与锁校验 | PASS | 9 个直接依赖、53 个解析包、53 个带哈希 wheel |
| Python 环境安装 | PASS | 按 `backend/pylock.toml` 安装；`pip check` 成功 |
| 前端安装 | PASS | `npm ci` 安装 192 个包，报告 0 个漏洞 |
| Playwright 浏览器 | PASS | Chromium 安装成功 |
| 前端生产构建 | PASS | 安装流程中的构建成功 |
| 本机数据初始化 | PASS | SQLite 初始化成功 |

安装过程按文档访问 PyPI/Python 包托管服务、npm Registry 和 Playwright Chromium 下载源。该结果只适用于上述 Windows、CPython 与 Node.js 环境。

## 3. 完整自动化门禁

`test-all.bat` 在同一 clean-root 源提交上完整执行并返回 `TEST_ALL_STATUS=PASS`。

| 门禁 | 结果 | 耗时/证据 |
|---|---|---|
| Python lock verifier | PASS | 9 direct / 53 packages / 53 hashed wheels |
| `pip check` | PASS | 已安装 Python 环境依赖一致 |
| `pip-audit --local --strict` | PASS | 未发现已知漏洞 |
| 后端 pytest | PASS | 77 passed，6 warnings，182.29s |
| 前端 Vitest | PASS | 15/15，25.07s |
| TypeScript + Vite build | PASS | 211 modules，2.13s |
| Playwright E2E | PASS | 4 passed；1 个需显式 opt-in 的文档截图用例按设计 skipped；44.3s |
| 状态与 demo 辅助脚本检查 | PASS | `update-codex-status.py --help` 与 `create-demo-repo.py --help` 成功 |

仓库没有独立 lint script，因此未虚构 lint 结果。TypeScript 检查由生产构建中的 `tsc -b` 执行。

### Warning 展开复跑

为确认 pytest warning 的性质，另行展开 warning 复跑：77 passed，1 条可见 `StarletteDeprecationWarning`，292.92s。该 warning 未指示安全失败，也未影响测试结果；后续迁移到 HTTPX 2.x 测试栈时处理，不把它描述为已修复。

## 4. Playwright、响应式与公开截图

E2E 使用系统临时目录中的合成 Git 仓库、独立 SQLite 数据和专用本机测试服务，不读取或登记私有项目。

| 检查 | 结果 | 证据 |
|---|---|---|
| 核心 UI 闭环 | PASS | Playwright 4 个用例全部通过 |
| 1366×768 | PASS | 无失控横向溢出，主要操作可达 |
| 1920×1080 | PASS | 主要区域与详情可读 |
| 2560×1440 | PASS | 布局无异常拉伸，内容可读 |
| Console error / page error | PASS | 正常业务流程均为 0 |
| 独立公开截图 capture | PASS | 显式 opt-in 后 1 passed，23.0s |
| README 截图尺寸 | PASS | 两张 WebP 均为 1920×1080 |
| 截图隐私与来源目检 | PASS | 仅合成项目/任务数据与折叠路径；无真实用户名、机器特定绝对路径、私有项目名、凭据或客户数据 |

公开截图来自运行中的真实应用；来源和再生成流程见 [images/README.md](images/README.md)。截图验证已经完成，不再是发布阻断项。

## 5. Windows 一键启动与停止

| 场景 | 结果 | 实测证据 |
|---|---|---|
| 首次 `一键启动.bat` | PASS | 10.957s；默认项目 configured/registered 为 0/0 |
| 首次健康与页面 | PASS | `/api/health` 与根页面均返回 HTTP 200；进程归属校验通过 |
| 第二次 `一键启动.bat` | PASS | 已有健康实例路径 8.677s；HTTP 与进程归属校验通过 |
| `stop.bat` | PASS | 7.391s；停止后监听器数量为 0 |

报告不保存或公开测试机器的 PID、用户名、绝对路径或终端历史。

## 6. 依赖、秘密与文档门禁

| 门禁 | 结果 | 实测证据 |
|---|---|---|
| Python 已知漏洞审计 | PASS | `pip-audit`：no known vulnerabilities |
| npm 生产依赖审计 | PASS | 0 vulnerabilities |
| npm 完整依赖审计 | PASS | 0 vulnerabilities |
| npm provenance 验证 | PASS | 192 signatures，65 attestations |
| Gitleaks 8.30 canary | PASS | canary 能被检测，验证扫描不是空跑 |
| 原工作区历史 Gitleaks | PASS | 0 findings |
| clean-root 历史 Gitleaks | PASS | 0 findings |
| Markdown 本地链接 | PASS | 16 个 Markdown、46 个本地目标、0 broken |
| GitHub Issue YAML | PASS | 3 个 YAML 均可解析并通过结构检查 |
| README 双语、徽章与截图引用 | PASS | 双语结构与截图路径一致，静态徽章可访问 |
| Python/npm locks 与第三方清单 | PASS | 直接依赖版本一致；Python lock 哈希校验成功 |

Gitleaks 的 0 findings 只表示其规则未发现秘密，不等于旧 Git 历史可公开。旧历史仍包含不应发布的内部内容，因此发布只能使用已审计的 clean-root 历史，绝不能推送旧历史。

## 7. 安全边界结果

本轮自动化测试和静态复核覆盖并通过以下边界：

- Git Runner 精确只读白名单、参数数组、环境清理、输出上限与凭据形态脱敏；
- Host、HTTP Origin、CORS、WebSocket Origin、消息大小与连接容量限制；
- 原生目录选择和本机打开操作默认关闭，仅 `CPC_ENABLE_SYSTEM_ACTIONS=1` 时启用；
- 本机打开路径只接受已登记仓库根目录或 Worktree，并拒绝文件、UNC、device path 与 reparse point；
- 状态元数据显式写入的 schema、1 MiB 上限、写锁、原子替换、备份上限与路径边界；
- 刷新 single-flight、并发上限、SQLite 事件保留上限与本机运行产物忽略规则。

这些结果不把本机单用户工具描述为可安全暴露到不可信网络的多用户服务。

## 8. 性能基准

**未执行独立性能基准。** 本轮没有记录可公开复现的仓库规模、硬件、冷热缓存、重复次数与统计方法，因此不声明扫描或拓扑性能提升。安装、测试与启动耗时仅是本次验收流水线证据，不是产品性能承诺。

## 9. 最终结论

被测 clean-root 源提交 `afadcda81bc6a649b8a38992f03a9b307454758f` 的安装、自动化测试、响应式检查、截图、启停、依赖审计、秘密扫描和公开文档门禁均通过。

技术验收为 **PASS**；首次公开发布仍为 **NO-GO**。剩余阻断只包括：许可证/版权主体/初始年份、品牌决定、显式发布批准、只能发布 clean-root 且绝不能推送旧历史，以及经批准后启用远端 Private Vulnerability Reporting。详见 [FINAL_ACCEPTANCE.md](FINAL_ACCEPTANCE.md)。
