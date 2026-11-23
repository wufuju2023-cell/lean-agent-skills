---
name: tui-e2e-test-experience
description: '用 tmux 驱动真实 OpenCode TUI（真实 PTY、真实渲染、send-keys 输入、capture-pane 读屏），再用 OpenCode HTTP API 做硬断言的端到端验收流程：启动、等待、发提示、轮询、取证、triage、清理；含本地环境 v2 二进制路径、模型 pin、插件热加载、tool-call 与 RPC 状态核对、常见坑位。Use when running or designing an end-to-end test of the OpenCode TUI, validating a plugin or tool from the user perspective, driving a TUI programmatically, or debugging why a TUI test did not trigger the expected tool/command. Triggers: TUI E2E, tmux send-keys, capture-pane, 真实 TUI, PTY, 端到端测试, 插件验收, tool call 验证, opencode api, /api/session, RPC, goal 测试, 无桌面测试.'
---

# TUI E2E 测试经验（tmux + OpenCode API）

用**真实 TUI + 真实 PTY**做端到端验收，全程不需要桌面 / VNC / 截图 / OCR。

判定原则：**TUI 只负责“跑起来、被输入、被看见”；通过与否由 API 里的 tool-call 参数和状态机决定。**

## 模型策略（强制）

真实 TUI 验收需要模型跑时，**只用下面这一个模型，禁止换任何别的模型**：

| 项 | 值 |
|---|---|
| provider | `opencode-go` |
| model | `deepseek-v4.1-flash`（TUI 显示名 `DeepSeek V4.1 Flash 1017`） |
| 思考强度 / variant | `max`（该模型的 variants：`low` / `high` / `max`） |

固定写法（项目 `opencode.json`）：

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "model": "opencode-go/deepseek-v4.1-flash#max"
}
```

规则：

- 不依赖全局默认模型（本地环境全局可能是 `teamorouter/claude-sonnet-5`），也不要在 TUI 里手动切别的模型。
- 控制组用 `opencode run` 时同样显式指定：`--model opencode-go/deepseek-v4.1-flash#max`。
- 每次测试开始后必须断言 session 的 model 是
  `{"providerID":"opencode-go","id":"deepseek-v4.1-flash","variant":"max"}`；
  不一致立即判 **FAIL**，不要继续跑（断言命令见 §4.5）。
- TUI header 必须出现 `DeepSeek V4.1 Flash 1017 OpenCode Go · max`；只看到 `DeepSeek` 而没有 `· max` 也要查 variant。

## 0. 适用与不适用

适用：

- 验收一个插件 / 工具在真实 TUI 里能不能被模型调用；
- 验收 `/命令`、session 流程、goal 循环、跨轮续跑；
- 复现“只在 TUI 里出现”的问题（补全、快捷键、渲染、输入法、重排）。

不适用 / 别用：

- 只关心模型输出 → 用 `opencode run --model ... "..."`，更快；
- 只关心 server 逻辑 → 直接 `opencode api`，连 TUI 都不用起；
- 用户明确要求“我现在要在屏幕上看着它跑 / 要亲手接管” → 那才需要另开桌面 attach，不属于本 skill。

## 1. 三十秒配方

```bash
OC=~/.opencode2/bin/opencode
DIR=/tmp/opencode/tui-e2e
mkdir -p "$DIR"

# 1) 项目级 pin 模型（TUI 没有全局 --model flag）
cat > "$DIR/opencode.json" <<'JSON'
{ "$schema": "https://opencode.ai/config.json", "model": "opencode-go/deepseek-v4.1-flash#max" }
JSON

# 2) 起真实 TUI（后台 tmux + 固定尺寸）
tmux new-session -d -s e2e -x 200 -y 50 \
  "cd $DIR && exec $OC; echo EXIT=\$?; sleep 86400"
tmux set-option -t e2e window-size manual

# 3) 等就绪（出现输入框/模型名）
tmux capture-pane -p -t e2e | grep -E "Ask anything|Build ·" && echo READY

# 4) 以用户身份发提示
tmux send-keys -t e2e -l "Build a tiny Python project ..."; tmux send-keys -t e2e Enter

# 5) 读屏 + API 断言（见第 3、4 节）
tmux capture-pane -p -t e2e | tail -40
```

辅助脚本：`scripts/tui-e2e.sh start|send|key|read|wait|stop`。

## 2. 本地环境环境事实（2026-11 实测）

| 事实 | 值 |
|---|---|
| v2 二进制 | `~/.opencode2/bin/opencode`（写 skill 时 v2.3.0；版本会随自动更新变化，用 `--version` 现查） |
| PATH 上的 `opencode` | V1（1.18.x），**不要用**；始终写绝对路径或先 `export PATH=~/.opencode2/bin:$PATH` |
| 全局配置 | `~/.opencode2/config/opencode/opencode.json` |
| 项目配置 | `<dir>/opencode.json`（`model`、plugins 等按 location 合并） |
| 插件热加载 | 改配置/源码后 `opencode reload`；`opencode plugin list` 确认 |
| TUI 选模型 | **没有**全局 `--model`；项目配置固定写 `"model": "opencode-go/deepseek-v4.1-flash#max"`；禁止切其他模型 |
| 非 TUI 控制组 | `opencode run --model opencode-go/deepseek-v4.1-flash#max "..."` |
| 健康检查 | `opencode api get /api/info` |
| 服务 | TUI 默认连后台共享 service；要隔离用 `--standalone` |

## 3. 五步法

### 3.1 准备

- 独立 scratch 目录，避免污染真实项目；把 `opencode.json` 放进去 pin 模型。
- 确认插件已加载：`opencode plugin list | grep <id>`；刚改过源码就 `opencode reload`。
- 记下验收目标（例如“模型应自己调用 `goal set`”），后面断言只认这个。

### 3.2 起 TUI

```bash
tmux new-session -d -s e2e -x 200 -y 50 \
  "cd $DIR && exec $OC; echo EXIT=\$?; sleep 86400"
tmux set-option -t e2e window-size manual
```

- `-x/-y` 固定尺寸；`window-size manual` 防止后续 client attach 触发重排。
- 末尾 `echo EXIT=$?` 用于区分“TUI 正常退出”和“启动即崩”。
- 名字用唯一前缀（`e2e-<topic>`），不要跟用户的 tmux session 撞名。

### 3.3 等就绪

```bash
tmux has-session -t e2e 2>/dev/null || { echo "session died"; exit 1; }
tmux capture-pane -p -t e2e | tail -30
```

看三样：logo/输入框、模型名、MCP/插件提示。首次启动可能 5–10 秒才画完，**不要只 sleep 一次就发提示**。

### 3.4 发提示

```bash
tmux send-keys -t e2e -l "你的需求原文"   # -l：字面发送，不解释特殊字符
tmux send-keys -t e2e Enter
```

常用键：`C-u` 清空输入行，`Escape` 关弹窗，`C-c` 中断（视 TUI 而定）。

### 3.5 轮询 + 取证

```bash
# 每 2–5 秒抓一次，直到出现完成标志或超时
tmux capture-pane -p -t e2e | tail -40
```

同时跑 API 断言（第 4 节）。**不要只靠“看起来完成了”。**

## 4. 判据：API 硬断言

### 4.1 找 session

```bash
$OC api get /api/session > /tmp/sessions.json
python3 - <<'PY'
import json
d = json.load(open("/tmp/sessions.json"))
items = d.get("data") or d
items = sorted(items, key=lambda s: s.get("time", {}).get("updated", 0), reverse=True)
for s in items[:5]:
    print(s["id"], "|", str(s.get("title"))[:50])
PY
```

TUI 会用首条提示自动生成标题；用标题 + 目录/时间定位。注意：**重启 TUI 可能恢复旧标签页**，不要假设一定是新 session。

### 4.2 查 tool call（最硬的证据）

```bash
$OC api get /api/session/$SID/message > /tmp/msgs.json
python3 - <<'PY'
import json
d = json.load(open("/tmp/msgs.json"))
for m in d.get("data") or d:
    for p in (m.get("parts") or m.get("content") or []):
        if p.get("type") == "tool":
            st = p.get("state", {})
            print(p.get("tool") or p.get("name"),
                  json.dumps(st.get("input") or p.get("input"), ensure_ascii=False),
                  "->", st.get("status"))
PY
```

要断言的是：**工具名 + 原始 input + 状态**（例如 `goal {"action":"set","objective":"..."} -> completed`）。

### 4.3 查插件状态（RPC）

插件 RPC 的 HTTP 形态：

```bash
$OC api post /api/rpc/<rpcID>/<method> --data '{"input":{...}}'
# 返回 {"output": ...}
```

例：内置 goal 引擎

```bash
$OC api post /api/rpc/opencode.goal/get \
  --data '{"input":{"sessionID":"ses_..."}}'
```

断言状态机：`active → complete`（带 judge 的 `reason`）或 clear 之后 `null`。

> 注意：body 必须包在 `{"input": ...}` 里，输出在 `{"output": ...}` 里；直接传裸对象会得到 `Expected object`。

### 4.4 绕过 TUI 做二分

怀疑是 TUI 层的问题时，用同一条 server 路径复现：

```bash
# 命令（与用户敲 /命令 等价）
$OC api post /api/session/$SID/command --data '{"name":"goal","text":"..."}'
# 普通提示
$OC api post /api/session/$SID/prompt  --data '{"text":"..."}'
```

TUI 失败但 API 成功 → 问题在输入/渲染/TUI；两边都失败 → 问题在命令/插件/模型。

### 4.5 模型断言（每次必做）

```bash
$OC api get /api/session/$SID > /tmp/session.json
python3 - <<'PY'
import json
s = json.load(open("/tmp/session.json"))
s = s.get("data") or s
model = s.get("model") or {}
expect = {"providerID": "opencode-go", "id": "deepseek-v4.1-flash", "variant": "max"}
if model != expect:
    raise SystemExit(f"WRONG MODEL: {model} (expected {expect})")
print("model ok:", model, "| agent:", s.get("agent"))
PY
```

- 不一致 → 立即 FAIL，不要“先跑完再说”。
- 同时对照 TUI header：`Build · DeepSeek V4.1 Flash 1017 OpenCode Go · max`。

更强的检查（防止中途被切模型）：逐条断言 assistant 消息的 model。

```bash
$OC api get /api/session/$SID/message > /tmp/msgs.json
python3 - <<'PY'
import json
d = json.load(open("/tmp/msgs.json"))
msgs = d.get("data") or d
used = {
    (m["model"]["providerID"], m["model"]["id"], m["model"].get("variant"))
    for m in msgs
    if m.get("type") == "assistant" and m.get("model")
}
expect = {("opencode-go", "deepseek-v4.1-flash", "max")}
if not used or used - expect:
    raise SystemExit(f"WRONG MODEL IN TRANSCRIPT: {used}")
print("transcript models ok:", used)
PY
```

## 5. 读屏约定

TUI 里值得 grep 的标志：

| 文本 | 含义 |
|---|---|
| `Build · <模型名>` | 当前模型（先核对是不是你要的） |
| `✓ <tool> [action=..., ...]` | 模型发起的工具调用及其参数 |
| `← Write` / `$ cmd` | 文件/Shell 工具 |
| `◎ goal` / `◎ goal met` | 目标进行中 / 已被 judge 判定完成 |
| `Retrying in Ns · attempt 2 · Connection lost ...` | 传输层重试（SSE 看门狗），不是功能失败，继续等 |
| `esc interrupt` | 正在生成，可中断 |

补充：

- TUI 用 alternate screen，`capture-pane -S -400` 的“历史”通常只有当前屏；**高频抓屏**比事后翻历史可靠。
- 弹窗/对话框会占右半边，grep 时可能把正文截断；先 `Escape` 再读。
- `/命令` 补全：第一次 `Enter` 可能只是选中候选，**再按一次 `Enter`** 才执行。

## 6. 坑位清单（实测）

1. **TUI 必须有 TTY**：非 TTY 运行会打印 help 后退出；tmux 是必需的。
2. **`--model` 不是全局 flag**：TUI 用项目 `opencode.json` 的 `model`；`opencode run` 才有 `--model`。
3. **attach 第二个 client 会 resize**：TUI 重排（如 210×45 → 80×23），可能改变布局与行为。自动化时不要 attach；必须 attach 时 `window-size manual`。
4. **`tmux kill-server` 会杀掉机器上所有 tmux session**（包括用户自己的）。只用 `tmux kill-session -t <name>`。
5. **插件工具默认可能只进 Code Mode**：`options.codemode: true` 的工具不会出现在直接工具表里，TUI 模型无法直接调用；要 TUI 验收就注册成直接工具（`codemode: false`）。
6. **配置热加载但插件源码未必**：改完 `opencode reload`，并用 `opencode plugin list` + 实际请求确认。
7. **首次请求可能被 SSE 看门狗打断**：出现 `Retrying` 就等待重试，别当失败；必要时看 `sse-watchdog.log`。
8. **session 定位要按目录/标题/时间**：TUI 会恢复旧标签页；`/api/session` 顺序不保证。
9. **不要用截图判定**：截图只做人眼存证；断言落在 API 的 tool-call 与状态。
10. **共享 service 是多会话的**：测试前确认没有同名标题/同目录的旧 session 干扰。
11. **模型必须项目级 pin 并断言**：全局默认不是 `opencode-go/deepseek-v4.1-flash`；`#max` 是 variant，默认可能恰好是 max，但不要依赖默认。session model、TUI header、assistant 消息三者任一不符 → FAIL。

## 7. Triage 树

```text
0) 先查 session model == {"providerID":"opencode-go","id":"deepseek-v4.1-flash","variant":"max"}；
   不是 → FAIL，先修模型 pin（项目 opencode.json 的 #max / agent 覆盖 / TUI 手动切换）再往下查。

TUI 起来了吗？
├─ 否：检查二进制路径/版本、TTY、tmux session 是否存活（capture 里有没有 EXIT=）
└─ 是
   ├─ 模型没调工具？
   │  ├─ 工具在直接工具表里吗（codemode 是否 false）
   │  ├─ system 提示注入了吗（只在有该工具时注入才合理）
   │  ├─ 换 `opencode run` 同模型最小复现
   │  └─ 看是否被权限/工具白名单过滤（agent.tools）
   ├─ 调了但命令报错？
   │  ├─ `POST /session/$SID/command` 直接复现
   │  └─ 看 tool 返回文本（`state.output`）
   └─ 状态没变化？
      ├─ RPC get 直接读状态
      ├─ 等 judge/续跑（goal 类状态机不是同步的）
      └─ 检查服务是否重启导致 paused
```

## 8. 清理

```bash
tmux kill-session -t e2e
```

- 保留证据目录（消息 JSON、日志）即可，不要删共享 service 的 DB/状态。
- 不要 `tmux kill-server`；不要 `pkill opencode`（会杀掉用户的 TUI 和后台服务）。

## 9. 一次真实案例（goal-tools 插件验收）

目标：模型的 goal 必须由 agent 自己设置，用户只提需求。

1. 项目 `/tmp/opencode/goal-tui-e2e`，`opencode.json` pin `opencode-go/deepseek-v4.1-flash#max`（TUI header 核对 `· max`，session model 断言 variant=`max`）。
2. tmux `goal-e2e` 起 TUI，发一句纯需求（没提 goal、没敲 `/goal`）。
3. `capture-pane` 看到 `Build · DeepSeek V4.1 Flash 1017 OpenCode Go · max`。
4. `GET /api/session/$SID/message` 拿到：
   `goal {"action":"set","objective":"Create calc.py, test_calc.py, and README.md ..."} -> completed`
5. `POST /api/rpc/opencode.goal/get` → `{"status":"active"}`，随后 judge 把它变成 `complete` 并附 `reason`；TUI 出现 `◎ goal met`。
6. 再说“把目标改成 …” → `goal {"action":"update",...}`；再说“清除目标” → `goal {"action":"clear"}`，RPC 返回 `null`。
7. 清理日志后复测一轮（新需求 mul），再次 `set` → `◎ goal met`，9 个测试通过。
8. 模型 pin 复测：项目 `opencode.json` 写 `opencode-go/deepseek-v4.1-flash#max`，TUI header 显示 `... OpenCode Go · max`；`GET /api/session/$SID` 的 model 为 `{opencode-go, deepseek-v4.1-flash, max}`；该 session 所有 assistant 消息的 model 也只有这一个值。

结论：**TUI 负责真实交互，API 负责不可抵赖的证据；两者都过才算通过。**
