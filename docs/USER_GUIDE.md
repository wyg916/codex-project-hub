# Codex Project Hub 使用指南

Codex Project Hub 是面向 Windows 单机开发者的本地 Git 观察总控台。它通过白名单中的只读 Git 命令读取仓库和 Worktree 事实；除明确维护任务元数据外，不会修改被登记仓库的业务代码，也不会自动执行 fetch、merge、rebase、reset、clean、push 或删除分支。

## 1. 系统要求

- Windows 10 或 Windows 11
- 64 位 CPython 3.11.x，并可通过 Windows `py` 启动器以 `py -3.11` 调用
- Node.js `20.19.x` 或 `22.12.0` 及更高版本，以及 npm
- `PATH` 中可用的 Git
- Visual Studio Code 为可选项，仅本机打开快捷操作需要

Node.js 21 不在当前 Vite 工具链的支持范围内。项目在 `frontend/package.json` 中使用 `^20.19.0 || >=22.12.0` 作为准确的运行时约束。

## 2. 安装、启动与停止

在项目根目录执行：

```bat
install.bat
start.bat
```

`install.bat` 创建 `.venv`、根据 `backend/pylock.toml` 安装带哈希锁定的 Python 应用与测试依赖、执行 `npm ci`、安装 Playwright Chromium、构建前端并初始化本机 SQLite。该锁文件面向 Windows x86-64 上的 CPython 3.11。`start.bat` 默认在 <http://127.0.0.1:8765> 启动生产构建；根目录的 `一键启动.bat` 是等价的双击入口。

项目首次启动时登记列表为空，`config/default-projects.json` 有意保存空项目数组。应用不会自动登记任何真实仓库。请启动后在界面中通过“新增项目”登记仓库。

如需隔离演示，可先创建合成仓库：

```powershell
.venv\Scripts\python.exe scripts\create-demo-repo.py
```

脚本会在项目的 `data/demo-repositories/` 下生成演示仓库。随后在界面中登记其中一个生成目录即可；演示流程不需要访问私有项目。

停止应用：

```bat
stop.bat
```

停止脚本只处理本项目 PID 文件记录且通过身份校验的进程，不会按端口终止无关程序。

## 3. 登记项目

1. 在项目总览点击“新增项目”。
2. 粘贴本地 Git 仓库或 linked Worktree 路径。
3. 检查识别出的 Git Common Dir、主 Worktree 和 linked Worktree。
4. 确认显示名称，并按需显式填写主分支、集成分支和 RC 分支。
5. 保存后进入项目驾驶舱。

同一 Git Common Dir 只能登记一次；远端 URL 相同但 Common Dir 不同的 Clone 会视为独立项目。删除登记只会移除 Codex Project Hub 的本机登记和快照，不会删除仓库、Worktree 或分支。

原生 Windows 目录选择器默认关闭。未启用系统操作时仍可直接粘贴路径完成登记。

## 4. 可选的本机系统操作

原生目录选择以及“打开目录、终端、Visual Studio Code”操作默认禁用。只有在可信本机环境中确实需要时，才在启动应用前显式设置：

```powershell
$env:CPC_ENABLE_SYSTEM_ACTIONS = "1"
.\start.bat
```

后端仅在变量值恰好为 `1` 时启用这些操作。本机打开请求必须与已登记仓库根目录或其某个 Worktree 完全匹配；任意外部路径都会被拒绝。不要通过网络向其他用户暴露启用系统操作的实例。

## 5. 其他配置

启动器和后端读取当前进程环境变量，不会自动加载 `.env`。可参考项目根目录的 `.env.example`：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `CPC_DATA_DIR` | `<项目目录>/data` | SQLite、日志与 PID 文件目录 |
| `CPC_SCAN_INTERVAL` | `4` | 当前项目轮询秒数；小于 1 的值会提升为 1 |
| `CPC_DISABLE_BACKGROUND` | 未设置 | 设为 `1` 时禁用 watchdog 与后台轮询 |
| `CPC_ENABLE_SYSTEM_ACTIONS` | 未设置（禁用） | 仅设为 `1` 时启用原生目录选择和本机打开操作 |
| `CPC_ALLOWED_ORIGINS` | 内置回环 Origin | 逗号分隔的额外明确 HTTP(S) Origin；拒绝凭据、非根路径、查询参数与片段 |
| `CPC_NO_BROWSER` | 未设置 | 设为 `1` 时阻止 `start.bat` 自动打开浏览器 |

`CPC_ALLOWED_ORIGINS` 只追加经过校验的浏览器 Origin，不改变服务默认绑定回环地址的事实，也不构成把应用暴露到不可信网络的建议。

## 6. 项目总览

项目卡展示主/集成/RC 分支、活跃、待合并、阻塞、脏工作区、任务元数据维护状态和下一步动作。顶部筛选支持开发中、验证中、阻塞、待合并、冻结和长期未更新。

Git 事实未知时显示 `UNKNOWN`；任务状态元数据缺失时显示“未维护”。Codex Project Hub 不根据提交数、文件数或活动量推断任务进度。

## 7. 项目驾驶舱

- 顶部：主项目目录、主/集成/RC、主线 HEAD、工作区、远端同步、扫描时间和实时连接状态。
- 左侧：本机项目切换、分支状态环图、异常提醒和最近活动。
- 中央：可拖动、缩放、搜索、筛选、适配、全屏和切换布局的压缩分支拓扑。
- 右侧：所选分支的任务元数据、阶段进度、Git 事实、测试证据、阻塞、下一步和可选快捷操作；提交详情显示 SHA、说明、作者与时间。

“工作区”异常可下钻到全部脏 Worktree、变更分类和文件清单。界面只展示事实，不会自动清理、提交或合并这些变更。

图谱使用聚焦和压缩策略，不承诺展示无限完整的提交 DAG。需要更多分支时可切换到“查看全部分支”。

## 8. 实时更新

watchdog 监听 Git Common Dir 和有效 Worktree，并过滤依赖目录、构建产物、Git 锁文件及内部事件日志。连续事件会防抖合并；后台使用有界轮询兜底。检测到有意义的变化后，后端通过本机 WebSocket 通知页面。

设置 `CPC_DISABLE_BACKGROUND=1` 会禁用 watchdog 和后台轮询；此时需要使用界面刷新或重新进入项目以获取新状态。

## 9. 显式任务状态

状态文件位于 `<git-common-dir>/codex-dashboard/status.json`，同一仓库的全部 Worktree 共享。推荐使用 `scripts/update-codex-status.py` 明确更新，不要手工覆盖 JSON。

- 无状态文件：显示“未维护”。
- 无测试证据：显示 `NOT_RUN`。
- JSON 或 Schema 错误：显示不可解析状态并保留原文件。
- 元数据结果与 Git 阻塞事实并存：两者都会展示，不会互相覆盖。

完整契约见 [STATUS_SCHEMA.md](STATUS_SCHEMA.md)。仓库路径、分支、提交作者、任务文本和测试证据均可能包含敏感信息，分享前请先脱敏。

## 10. 开发与测试

`dev.bat` 启动 FastAPI reload 服务与 Vite 开发服务器。`test-all.bat` 运行项目定义的本地门禁；也可以按 README 分别运行 pytest、Vitest、生产构建和 Playwright。

Playwright 使用系统临时目录中的合成 Git 仓库、专用测试服务和独立数据库，不应读取或登记任何私有项目。最终发布验收结果必须来自待发布的准确提交，并填写到 [TEST_REPORT.md](TEST_REPORT.md) 和 [FINAL_ACCEPTANCE.md](FINAL_ACCEPTANCE.md)；模板中的“待实测”不是通过结论。
