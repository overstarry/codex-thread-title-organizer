# Codex Thread Title Organizer

使用 TypeSafe Jev 判断 Codex 对话的当前状态，并通过 Codex 原生线程能力为标题维护唯一的分类前缀。

支持 Windows、macOS 和 Linux。运行脚本仅依赖 Python 3.9 或更高版本的标准库，不需要 PowerShell 或额外 Python 包。

## 工作方式

1. `UserPromptSubmit` Hook 保存当前用户请求。
2. `Stop` Hook 将用户请求和最后一条助手消息提交给 Jev。
3. Jev 每轮都输出当前绝对状态标签，不读取上一轮标签，也没有 `keep` 选项。
4. 本地策略使用适合低风险标题变更的置信度门槛，并将新标签与上一轮已请求标签比较。
5. 仅当分类标签变化时，Hook 才发起一次受保护的继续执行，请求 Codex 更新当前线程标题。

插件不会修改 Codex 数据库或直接操作界面元素。分类置信度过低或标签未变化时会保留现有标题，不消耗额外的 Codex continuation 额度。会话状态还会记录最近一次观察到的标签和置信度，便于在不保存 Jev 响应正文的情况下诊断。

## 安装

Windows、macOS 和 Linux 使用相同的命令注册 GitHub marketplace 并安装插件：

```console
codex plugin marketplace add overstarry/codex-thread-title-organizer
codex plugin add codex-thread-title-organizer@starry-tools
```

仓库当前为私有仓库，执行安装命令前需要确保当前 Git 环境有权访问该仓库。安装后重启 Codex Desktop，并检查、信任 Hook。Codex Desktop 进程需要继承以下环境变量：

```text
TYPESAFE_API_KEY
```

可以使用 `TYPESAFE_MODEL` 覆盖默认模型 `jev-latest`。

Hook 信任入口目前只在 Codex CLI 中提供，不在 Codex Desktop 的聊天输入框中提供。打开终端进入交互式 CLI：

```console
codex
```

然后输入 `/hooks`，确认 `UserPromptSubmit` 和 `Stop` 下出现 `codex-thread-title-organizer@starry-tools`，逐项检查并信任。完成后彻底退出并重新打开 Codex Desktop。

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
- Hook 防止自身触发的继续执行形成循环，并且只在分类标签变化时请求改名。
- 相同分类不会自动重试改名；需要恢复时使用 `update-thread-title` 技能手动刷新。
- 插件只请求修改当前根线程，不操作其他线程。
