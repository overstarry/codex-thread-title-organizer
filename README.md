# Codex Thread Title Organizer

使用 TypeSafe Jev 判断 Codex 对话的当前状态，并通过 Codex 原生线程能力为标题维护唯一的分类前缀。

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

## 验证

```powershell
pwsh -NoProfile -File .\scripts\test-contract.ps1
pwsh -NoProfile -File .\scripts\test-live.ps1
```

第二个命令会调用 TypeSafe API。

## 标题分类

支持 `wip`、`blocked`、`validate`、`done`、`plan`、`bug`、`chat`、`art`、`feature` 和 `ops`。重复运行时会先移除已知旧前缀，再添加一个新前缀。

## 安全边界

- API Key 仅从环境变量读取。
- 会话状态写入 Codex 提供的 `PLUGIN_DATA` 目录。
- Hook 防止自身触发的继续执行形成循环。
- 插件只请求修改当前根线程，不操作其他线程。
