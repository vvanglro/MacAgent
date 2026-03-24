# MacAgent

一个可通过自然语言操控 macOS 应用的 Agent（MVP）。

## Features (V1)
- 微信发送消息：`wechat.send_message(contact, text)`
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
macagent run "聚焦 chrome 地址栏"
macagent run "搜索 macagent"
```

## Environment Variables
- `MACAGENT_PARSER_BACKEND=rule|openai`（默认 `rule`）
- `MACAGENT_REQUIRE_SEND_CONFIRMATION=true|false`（默认 `true`）

> 若使用 `openai` parser：
```bash
pip install -e .[openai]
export OPENAI_API_KEY=...
```

## Project Structure
- `domain/`: 领域模型与错误
- `nlu/`: 自然语言解析
- `orchestrator/`: 安全校验与路由
- `tools/`: 可执行工具（AppleScript/open）
- `tests/`: 单元与集成测试
