# MacAgent

一个可通过自然语言操控 macOS 应用的 Agent（MVP）。

## Features (V1)
- 微信发送消息：`wechat.send_message(contact, text)`
- 读取当前聊天最后一条消息：`wechat.read_last_message()`
- 读取指定联系人最后一条消息：`wechat.read_last_message(contact)`
- Chrome 聚焦地址栏：`chrome.focus_address_bar()`
- Chrome 搜索：`chrome.search(query)`

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Usage
```bash
macagent run "给hulk发微信说hello" --yes
macagent run "打开微信 给hulk发微信说hello" --yes
macagent run "读取当前聊天最后一条消息"
macagent run "读取不熬夜最后一条消息"
macagent run "聚焦 chrome 地址栏"
macagent run "搜索 macagent"
```

## Environment Variables
- `MACAGENT_PARSER_BACKEND=rule|openai`（默认 `rule`）
- `MACAGENT_REQUIRE_SEND_CONFIRMATION=true|false`（默认 `true`）
- `MACAGENT_OPENAI_MODEL=...`（默认 `gpt-4o-mini`）
- `MACAGENT_OPENAI_BASE_URL=...`（可选，适配第三方 OpenAI-compatible 服务）
- `MACAGENT_OPENAI_API_KEY=...`（可选，未设置时回退到 `OPENAI_API_KEY`）

> 若使用 `openai` parser：
```bash
pip install -e .[openai]
export OPENAI_API_KEY=...
```

> 若使用第三方 OpenAI-compatible 服务：
```bash
export MACAGENT_PARSER_BACKEND=openai
export MACAGENT_OPENAI_BASE_URL=https://your-provider.example.com/v1
export MACAGENT_OPENAI_API_KEY=your-key
export MACAGENT_OPENAI_MODEL=gpt-4o-mini
macagent run "打开微信 给hulk发微信说hello" --yes
```

## Project Structure
- `domain/`: 领域模型与错误
- `nlu/`: 自然语言解析
- `orchestrator/`: 安全校验与路由
- `tools/`: 可执行工具（AppleScript/open）
- `tests/`: 单元与集成测试
