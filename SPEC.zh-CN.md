# CLI 风格 HTTP API 核心规范

状态：草案 v1

本文档为面向 LLM 智能体的 CLI 风格 HTTP API 定义了一个最小化的在线协议约定。

目标很简单：智能体应能通过一个端点完成服务发现、逐条查看命令详情并调用命令，无需学习路由特定行为。

实现指南与示例见 `CLI_API_PATTERN.md`。

伴生规范：

- `SPEC_OPENAPI_MAPPING.md` - 从 OpenAPI 生成 CLI 服务的可选指南
- `SPEC_FEDERATION_EXTENSION.md` - 多服务发现与联邦的可选指南

---

## 1. 设计目标

本规范刻意保持狭窄范围。

它标准化了：

- 用于发现和调用的单一 HTTP 端点
- 统一的 JSON 请求格式
- 保留的 `help` 命令
- 紧凑的发现响应与逐命令帮助
- 标准的非流式响应
- 标准的错误码
- 可选的 NDJSON 流式传输

它未标准化：

- 认证或授权
- 后端实现细节
- 保留名称之外的命令命名约定
- 风险推导策略
- OpenAPI 生成规则
- 异步任务处理

---

## 2. 核心原则

**P1 - 单一端点。**
所有面向智能体的发现与调用均通过一个端点完成。

**P2 - 渐进式披露。**
智能体应先看到紧凑的命令目录，然后仅为其需要执行的命令获取详细帮助。

**P3 - 帮助即协议。**
`help` 是保留命令。智能体不得依赖带外文档来查看命令。

**P4 - 调用格式统一。**
智能体对每个命令发送相同的 JSON 信封。

**P5 - 错误必须引导恢复。**
错误响应必须是机器可读的，且应使下一步操作显而易见。

**P6 - 流式传输可选。**
流式传输对列表类输出有用，但必须保持可选且行为可预测。

---

## 3. 端点约定

### 3.1 发现

```text
GET /cli
```

返回根命令目录。

### 3.2 调度

```text
POST /cli
Content-Type: application/json
```

接受：

- `help`
- 领域命令

---

## 4. 请求格式

所有命令请求使用以下 JSON 信封：

```json
{
  "command": "<command_name>",
  "args": {},
  "stream": false
}
```

| 字段 | 类型 | 必需性 | 说明 |
|---|---|---|---|
| `command` | string | MUST | 要运行的命令。 |
| `args` | object | SHOULD | 命令的命名参数。未使用时省略或发送 `{}`。 |
| `stream` | boolean | MAY | 若为 `true`，响应为 NDJSON。默认为 `false`。 |

规则：

- `command` MUST 为非空字符串。
- `args` 存在时 MUST 为 JSON 对象。
- `stream` 存在时 MUST 为布尔值。

### 4.1 帮助请求

`help` 使用相同的请求信封调用：

```json
{
  "command": "help",
  "args": {
    "command": "<command_name>"
  }
}
```

规则：

- 省略 `args.command` 表示"返回根目录"。
- 设置 `args.command` 表示"返回该命令的详细帮助"。
- 未知的帮助目标 MUST 返回 `help_target_not_found`。

本规范有意使用 `args.command` 而非单独的节点标识符。在线协议应保持简洁，除非服务有明确的 richer 发现图需求。

---

## 5. 响应信封

所有非流式 JSON 响应 MUST 包含：

```json
{
  "status": "ok",
  "interface": "cli",
  "version": "1.0"
}
```

`status` MUST 为以下之一：

- `ok`
- `error`

---

## 6. 发现模型

本规范标准化的是命令路径发现，而非完整节点树。

服务 MAY 使用命令路径分层组织命令，例如：

- `catalog list`
- `catalog get`
- `offering create`

在线协议将每个完整命令路径视为命令标识。

### 6.1 根目录响应

`GET /cli` 和 `POST /cli {"command":"help"}` MUST 返回根目录：

```json
{
  "status": "ok",
  "interface": "cli",
  "version": "1.0",
  "service": "<service_name>",
  "commands": [
    {
      "name": "catalog",
      "kind": "group",
      "summary": "浏览目录命令。"
    },
    {
      "name": "health",
      "kind": "command",
      "summary": "检查服务健康状态。"
    }
  ],
  "total": 2
}
```

规则：

- `commands` MUST 保持紧凑。
- 每个条目 MUST 包含 `name`、`kind` 和 `summary`。
- `kind` MUST 为 `command` 或 `group`。
- `total` MUST 等于返回条目的数量。
- 根发现 MUST NOT 内联每个命令的完整参数模式。

对于 `kind: "group"` 条目，`name` 是发现标签，其本身不是可调用命令，除非服务明确将其文档化为可调用。

### 6.2 分组帮助响应

若服务使用分组命令路径，对分组的 `help` SHOULD 返回其子条目：

```json
{
  "status": "ok",
  "interface": "cli",
  "version": "1.0",
  "command": "catalog",
  "kind": "group",
  "summary": "浏览目录命令。",
  "subcommands": [
    {
      "name": "list",
      "kind": "command",
      "summary": "列出目录。"
    },
    {
      "name": "get",
      "kind": "command",
      "summary": "按 ID 获取单个目录。"
    }
  ]
}
```

规则：

- 分组帮助 MUST 保持紧凑。
- 分组帮助 MUST NOT 展开每个子命令的完整参数模式。

### 6.3 命令帮助响应

叶命令的详细帮助 MUST 返回足够的信息，使智能体能够正确调用：

```json
{
  "status": "ok",
  "interface": "cli",
  "version": "1.0",
  "command": "catalog list",
  "summary": "列出目录。",
  "description": "从后端服务返回目录列表。",
  "risk": {
    "level": "read",
    "reversible": true,
    "idempotent": true,
    "confirmation_required": false
  },
  "arguments": [
    {
      "name": "limit",
      "required": false,
      "type": "integer",
      "default": null,
      "description": "返回的最大记录数。"
    }
  ],
  "examples": [
    {
      "description": "列出前 5 个目录",
      "request": {
        "command": "catalog list",
        "args": {
          "limit": 5
        }
      }
    }
  ]
}
```

规则：

- `command` MUST 为完整的可调用命令字符串。
- `arguments` MUST 描述该命令接受的 `args` 键。
- 每个参数条目 MUST 包含：
  - `name`
  - `required`
  - `default`
- `type`、`description`、`enum`、`example` 和 `warning` 在有用时为 RECOMMENDED。
- `risk` 存在时 MUST 为包含以下字段的对象：
  - `level`（REQUIRED）— MUST 为 `read`、`write`、`destructive` 或 `simulate` 之一。
    - `read` — 无副作用。
    - `write` — 创建或修改状态。
    - `destructive` — 删除或不可逆地更改状态。
    - `simulate` — 试运行；无持久副作用。
  - `reversible`（RECOMMENDED）— 布尔值，指示效果是否可撤销。
  - `idempotent`（RECOMMENDED）— 布尔值，指示重复调用是否产生相同结果。
  - `confirmation_required`（RECOMMENDED）— 布尔值，提示智能体在调用前应寻求用户确认。
  - 省略 `risk` 表示服务未声明风险；智能体 SHOULD NOT 从缺失中推断安全性。
  - 伴生规范（如 `SPEC_OPENAPI_MAPPING.md`）MAY 定义从源元数据填充 `risk` 的推导规则。

本规范不要求除上述公共字段外的某一种确切模式词汇。目标是智能体可用性，而非模式最大化。

---

## 7. 调用响应

成功的非流式调用响应 MUST 使用以下格式：

```json
{
  "status": "ok",
  "interface": "cli",
  "version": "1.0",
  "command": "<command_name>",
  "result": {}
}
```

规则：

- `result` MUST 包含命令特定的输出。
- 实现 MAY 在有用时包含额外的顶层元数据，如 `resources`。

---

## 8. 错误响应

错误响应 MUST 使用以下格式：

```json
{
  "status": "error",
  "interface": "cli",
  "version": "1.0",
  "error": {
    "code": "<machine_readable_code>",
    "message": "<human_readable_message>"
  }
}
```

以下错误码为必需：

| 错误码 | 使用场景 |
|---|---|
| `command_not_found` | 请求的命令未注册为可调用命令。 |
| `help_target_not_found` | `help` 引用了未知的命令或分组。 |
| `missing_required_argument` | 缺少必需参数。 |
| `invalid_argument` | 某个参数验证失败。 |
| `invalid_arguments` | `args` 不是对象，或存在多个参数验证错误。 |
| `invalid_request` | JSON 主体结构有效但顶层格式错误。 |
| `invalid_command` | `command` 缺失或不是非空字符串。 |
| `invalid_json` | 请求主体不是有效的 JSON。 |
| `tool_invocation_failed` | 命令已运行但底层工具意外失败。 |
| `stream_failed` | 流式响应在流开始后失败。 |

规则：

- `code` MUST 为 snake_case。
- `message` MUST 为人类可读文本。
- 实现 MAY 添加 `retryable`、`suggestions` 或 `next_actions`。

---

## 9. 流式协议

流式传输是可选的。使用时 MUST 通过以下方式显式请求：

```json
{
  "command": "<command_name>",
  "args": {},
  "stream": true
}
```

响应 MUST 使用：

```text
Content-Type: application/x-ndjson
```

每个分块为一个 JSON 对象，后跟 `\n`。

### 9.1 分块类型

**started（已启动）**

```json
{"type":"started","command":"<command_name>","interface":"cli","version":"1.0"}
```

**item（条目）**

```json
{"type":"item","data":{}}
```

**done（完成）**

```json
{"type":"done","command":"<command_name>","total":0}
```

**result（结果）**

```json
{"type":"result","command":"<command_name>","data":{}}
```

**error（错误）**

```json
{"type":"error","error":{"code":"<code>","message":"<message>"}}
```

### 9.2 流式规则

- 第一个分块 MUST 为 `started`。
- 对于自然返回集合的命令，实现 SHOULD 发出零或多个 `item` 分块，后跟一个 `done` 分块。
- 对于返回单个结果对象的命令，实现 SHOULD 发出一个 `result` 分块并终止流。
- 若在流开始后发生错误，实现 MUST 发出一个 `error` 分块并终止流。

本规范有意不要求每个命令都支持流式传输，也不要求从后端载荷格式到分块格式的某一种确切映射。它仅标准化流信封。

---

## 10. 保留命令名称

以下名称为保留名称，MUST NOT 用于领域命令：

- `help`

未来版本可能会保留更多名称，但本版本将保留面保持最小。

---

## 11. 一致性

一致性实现 MUST：

1. 暴露 `GET /cli` 并返回根目录。
2. 接受使用本文档定义的请求信封的 `POST /cli`。
3. 支持 `help` 作为保留命令。
4. 对 `POST /cli {"command":"help"}` 返回根发现。
5. 对 `POST /cli {"command":"help","args":{"command":"..."}}` 返回命令或分组帮助。
6. 对未知的帮助目标返回 `help_target_not_found`。
7. 对未知的可调用命令返回 `command_not_found`。
8. 在每个非流式 JSON 响应中包含 `interface: "cli"` 和 `version: "1.0"`。
9. 使用标准错误响应格式。
10. 若支持流式传输，以 `started` 开头发出 NDJSON。

一致性实现 SHOULD：

- 保持根发现紧凑
- 在命令帮助中提供具体示例
- 在已知时包含参数默认值
- 一致使用标准错误码
- 对列表类命令支持流式传输
- 在命令帮助响应中包含 `risk` 元数据

