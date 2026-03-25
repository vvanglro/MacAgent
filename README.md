# MacAgent

MacAgent 是一个运行在 macOS 上的自然语言桌面 Agent，当前重点聚焦在微信和 Chrome。

它不是传统的“写死脚本集合”，而是一个偏产品化的 ReAct Agent：

- 能理解一句自然语言背后的真实目标
- 会把复杂任务拆成多个可执行步骤
- 执行时持续观察结果，再决定下一步
- 在终端里输出清晰的人话日志，方便你知道它现在在做什么

当前最强的场景是微信聊天辅助：

- 打开微信
- 搜索并进入指定聊天
- 读取当前聊天内容
- 总结双方在聊什么
- 给出“下一句怎么回”建议
- 用 loop 模式持续盯住一个聊天，自动记录、分析、并按规则回复

## 产品定位

MacAgent 更像一个“桌面上的微信聊天副驾”，而不是一个单纯的命令执行器。

你可以把它理解成：

- 一个会观察屏幕的聊天助手
- 一个会把聊天过程沉淀成 Markdown 记录的 loop agent
- 一个能逐渐学会“像你一样说话”的 persona-driven agent

## 核心能力

### 1. 单次执行 `run`

适合一次性指令：

- `给某人发微信`
- `读取最后一条消息`
- `总结当前聊天`
- `看看对方说了什么，我该怎么继续聊`
- `聚焦 Chrome 地址栏`
- `用 Chrome 搜索`

示例：

```bash
uv run macagent run "给hulk发微信说hello" --yes
uv run macagent run "打开微信 给hulk发微信说hello" --yes
uv run macagent run "读取当前聊天最后一条消息"
uv run macagent run "读取不熬夜最后一条消息"
uv run macagent run "读取一下我和 沪上小牛爷 都聊了些什么内容"
uv run macagent run "读取一下沪上小牛爷说了些什么，我该怎么继续聊天"
uv run macagent run "聚焦 chrome 地址栏"
uv run macagent run "搜索 macagent"
```

### 2. 持续轮询 `loop`

适合盯住一个聊天持续运行：

- 周期性读取聊天
- 将每一轮结果落盘到当前目录的 Markdown 文件
- 带上最近几轮历史上下文继续分析
- 加载“微信主人长期风格档案”
- 只在对方有新消息时考虑回复
- 刚回复过时，遵守冷却期，不会马上再次回复

示例：

```bash
uv run macagent loop "沪上小牛爷" --interval 60 --rounds 5
uv run macagent loop "沪上小牛爷" --interval 60 --rounds 0 --yes --cooldown 180 --context-rounds 3
uv run macagent loop "沪上小牛爷" --interval 60 --persona-file ./my-wechat-style.md
```

## 工作方式

MacAgent 当前采用 ReAct 风格执行：

1. 理解用户目标
2. 决定下一步动作
3. 执行动作
4. 观察结果
5. 根据观察结果继续推进

所以它不会总是“一句话直接映射一个固定脚本”，而是会动态做这些事情：

- 先打开微信
- 再搜索联系人
- 再进入聊天
- 再截图
- 再用 OCR 或视觉模型分析内容
- 最后决定是返回消息、生成摘要，还是给出回复建议

终端里你会看到类似这样的执行日志：

```text
• 正在解析指令并构建执行计划
• 开始执行
• 思考：先打开微信，再读取和 沪上小牛爷 的聊天内容。
• 开始执行动作：打开微信
• 正在打开并激活微信
• 思考：微信已就绪，现在根据用户意图分析聊天截图。
• 开始执行动作：读取微信聊天
• 正在搜索并打开聊天：沪上小牛爷
• 正在截取微信聊天区域
• 正在使用视觉模型分析截图
```

## 微信能力说明

### 读取模式

MacAgent 会根据你的自然语言意图，自动选择不同读取模式：

- `last`
  只返回最后一条来信

- `all`
  返回当前可见范围内的全部来信

- `summary`
  总结当前可见聊天内容

- `reply_advice`
  分析当前聊天，并给出“下一句怎么回”的建议

### 消息识别原则

微信读取时，目前默认遵循这些规则：

- 左侧气泡视为对方发送的消息
- 右侧气泡视为微信主人的消息
- 时间标签不会被当成消息
- 图片、表情、贴纸等非纯文字内容，视觉模型会尽量用中文描述

### 发送消息

发送链路现在是显式聚焦输入框后再粘贴发送，避免出现“已经切到聊天页，但焦点不在输入框”导致发不出去的问题。

## Loop Agent 设计

`loop` 模式不是简单地“反复读屏”，它内部维护了三层上下文：

### 1. 当前屏幕上下文

来自这一次截图里能看到的聊天内容。

### 2. 短期历史上下文

来自最近几轮 loop 的结果，包括：

- 对方最近说了什么
- 最近几轮摘要
- 我们上一次发了什么

### 3. 长期 persona 上下文

来自微信主人的长期风格档案，用来让回复更像你本人。

## 微信主人风格档案

loop 模式默认会尝试读取当前目录下的：

```text
macagent-wechat-owner-profile.md
```

你也可以用 `--persona-file` 显式指定另一份文件。

这份文件建议记录长期稳定信息，而不是当前聊天内容。比如：

- 你的说话风格：口语/正式、句子长短、常用语气词
- 你的性格：克制、幽默、温和、直给
- 你的身份设定：年龄段、职业、兴趣
- 你的聊天边界：别太油、别太官方、少用表情、别发长篇
- 和不同人的关系：熟人、朋友、客户、同事、暧昧对象

示例：

```md
你本人说话偏口语、轻松，不爱太官方。
和熟人聊天可以带一点玩笑，但别油腻。
不喜欢长篇大论，尽量两三句说完。
和“沪上小牛爷”是比较熟的朋友，可以接梗、可以轻松一点。
少用夸张表情，避免过度热情。
```

## Loop 日志文件

loop 模式会把每轮结果落到当前目录的 Markdown 文件里。

默认文件名会带上 loop 启动时间，避免多次运行互相覆盖，例如：

```text
macagent-loop-沪上小牛爷-20260325-100000.md
```

日志里会记录：

- 每轮时间
- 是否检测到变化
- 是否检测到对方新消息
- 是否处于冷却期
- 当前摘要
- 对方来信
- 建议回复
- 实际发送内容

同时还会嵌入结构化上下文，便于下一轮继续读取最近历史。

## 自动回复规则

带 `--yes` 时，loop 才允许自动发送。

即使开启自动发送，也不是每轮都发。当前默认还会额外满足这两个条件：

1. 对方确实有新消息
2. 不在我们刚发完的冷却期里

相关参数：

- `--cooldown`
  控制刚回复后要等待多久才能再次自动回复

- `--context-rounds`
  控制每轮带多少轮最近历史上下文

- `--rounds 0`
  一直循环，直到你手动停止

## 安装

推荐使用 `uv`：

```bash
uv sync
```

如果你要使用 OpenAI-compatible parser 或视觉模型，确保已经安装对应依赖：

```bash
uv sync --extra openai --extra dev
```

## 运行前准备

MacAgent 依赖 macOS 桌面自动化能力，通常需要这些前提：

- macOS
- 已安装并登录微信桌面版
- 已安装 Chrome（如果要用 Chrome 相关能力）
- 已给终端 / Python / Codex / 运行进程授予：
  - 辅助功能权限
  - 自动化权限
  - 屏幕录制权限

如果权限没开，常见现象会是：

- 能打开微信但点不到目标区域
- 能截图但 OCR 读不到内容
- 能进入聊天但发消息时没有焦点

## 环境变量

### Parser

- `MACAGENT_PARSER_BACKEND=rule|openai`
  默认 `rule`

- `MACAGENT_REQUIRE_SEND_CONFIRMATION=true|false`
  默认 `true`

- `MACAGENT_OPENAI_MODEL=...`
  默认 `gpt-4o-mini`

- `MACAGENT_OPENAI_BASE_URL=...`
  可选，适配第三方 OpenAI-compatible 服务

- `MACAGENT_OPENAI_API_KEY=...`
  可选，未设置时回退到 `OPENAI_API_KEY`

### Vision

- `MACAGENT_VISION_MODEL=...`
  可选，配置后读取微信消息时优先使用视觉模型

- `MACAGENT_VISION_BASE_URL=...`
  可选，未设置时回退到 `MACAGENT_OPENAI_BASE_URL`

- `MACAGENT_VISION_API_KEY=...`
  可选，未设置时回退到 `MACAGENT_OPENAI_API_KEY` / `OPENAI_API_KEY`

## 配置示例

### 使用 OpenAI parser

```bash
export MACAGENT_PARSER_BACKEND=openai
export OPENAI_API_KEY=your-key
uv run macagent run "读取一下沪上小牛爷说了些什么，我该怎么继续聊天"
```

### 使用第三方 OpenAI-compatible 服务

```bash
export MACAGENT_PARSER_BACKEND=openai
export MACAGENT_OPENAI_BASE_URL=https://your-provider.example.com/v1
export MACAGENT_OPENAI_API_KEY=your-key
export MACAGENT_OPENAI_MODEL=gpt-4o-mini
uv run macagent run "打开微信 给hulk发微信说hello" --yes
```

### 使用视觉模型分析微信截图

```bash
export MACAGENT_VISION_MODEL=gpt-4.1-mini
export MACAGENT_VISION_BASE_URL=https://your-provider.example.com/v1
export MACAGENT_VISION_API_KEY=your-key
uv run macagent run "读取不熬夜消息"
```

## 常见工作流

### 1. 单次看消息并生成建议

```bash
uv run macagent run "读取一下沪上小牛爷说了些什么，我该怎么继续聊天"
```

### 2. 持续观察，不自动发

```bash
uv run macagent loop "沪上小牛爷" --interval 60 --rounds 10
```

### 3. 持续观察并自动回复

```bash
uv run macagent loop "沪上小牛爷" --interval 60 --rounds 0 --yes --cooldown 180 --context-rounds 3
```

### 4. 带 persona 的长期运行

```bash
uv run macagent loop "沪上小牛爷" \
  --interval 60 \
  --rounds 0 \
  --yes \
  --cooldown 180 \
  --context-rounds 3 \
  --persona-file ./my-wechat-style.md
```

## 项目结构

- `src/macagent/domain/`
  领域模型与错误定义

- `src/macagent/nlu/`
  自然语言解析

- `src/macagent/orchestrator/`
  ReAct 执行与动作路由

- `src/macagent/tools/`
  微信、Chrome、OCR、点击等底层工具

- `src/macagent/loop_agent.py`
  loop agent 主逻辑

- `tests/`
  单元测试与集成测试

## 当前边界

这是一个很能干的 MVP，但仍然有边界：

- 微信桌面版 UI 变化可能影响搜索、点击、输入框定位
- OCR 和视觉模型都依赖当前可见屏幕内容，不是直接读取微信数据库
- 自动回复再智能，也应该在你的风格档案和冷却策略下谨慎使用
- 对于高风险联系人或场景，建议先不开 `--yes`，先观察建议质量
