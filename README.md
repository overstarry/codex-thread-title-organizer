# Codex Thread Title Organizer

使用 TypeSafe Jev 判断 Codex 对话的当前状态，并通过 Codex 原生线程能力为标题维护唯一的分类前缀。

支持 Windows、macOS 和 Linux。运行脚本仅依赖 Python 3.9 或更高版本的标准库，不需要 PowerShell 或额外 Python 包。

## 工作方式

1. `UserPromptSubmit` Hook 保存当前用户请求。
2. `Stop` Hook 将用户请求和最后一条助手消息提交给 Jev。
3. 本地策略根据分类结果和置信度选择标题前缀。
4. Hook 发起一次受保护的继续执行，请求 Codex 更新当前线程标题。

插件不会修改 Codex 数据库或直接操作界面元素。分类不确定时会保留现有标题。

## 安装

注册本地 marketplace：

```powershell
codex plugin marketplace add "C:\path\to\codex-thread-title-organizer"
```

重启 Codex Desktop，在插件界面安装 `Thread Title Organizer`，检查并信任 Hook。Codex Desktop 进程需要继承以下环境变量：

```text
TYPESAFE_API_KEY
```

可以使用 `TYPESAFE_MODEL` 覆盖默认模型 `jev-latest`。

运行时命令按平台选择：

- macOS/Linux：`python3`
- Windows：Python Launcher 的 `py -3`

## 验证

macOS/Linux：

```bash
python3 scripts/test_contract.py
python3 scripts/test_live.py
```

Windows：

```powershell
py -3 scripts\test_contract.py
py -3 scripts\test_live.py
```

第二个命令会调用 TypeSafe API。

仓库的 GitHub Actions 会在 Ubuntu、macOS 和 Windows 上执行离线契约测试。

## 标题分类

支持 `wip`、`blocked`、`validate`、`done`、`plan`、`bug`、`chat`、`art`、`feature` 和 `ops`。重复运行时会先移除已知旧前缀，再添加一个新前缀。

## 安全边界

- API Key 仅从环境变量读取。
- 会话状态写入 Codex 提供的 `PLUGIN_DATA` 目录。
- Hook 防止自身触发的继续执行形成循环。
- 插件只请求修改当前根线程，不操作其他线程。
