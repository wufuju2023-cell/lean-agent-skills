---
name: ai-agent-gui
description: Browser and desktop automation on this machine via the AI Agent GUI semantic CLI (agentgui), plus the machine's permanent browser-accessible XFCE remote desktop (TigerVNC + noVNC on display :5). Use for websites that need an existing login session, multi-step web interactions (click, fill, upload), extracting data from authenticated pages, native desktop app automation, and any task where the user must see or operate the desktop themselves. Prefer this over ad-hoc Playwright/curl when the task needs a real browser session or GUI, and reuse the existing VNC desktop instead of creating a new one. Triggers: browser automation, web automation, login-required site, authenticated page, form fill, click, upload, desktop app, GUI automation, agentgui, ai-agent-gui, Firefox, X11, screenshot, pixel fallback, 远程桌面, VNC, noVNC, XFCE, 桌面复用, 人机交接.
---

# AI Agent GUI（本地环境浏览器 / 桌面自动化）

## 它是什么

`ai-agent-gui/linux-version`：不依赖视频/视觉的 Linux 桌面自动化——

- **观察**：AT-SPI2 语义树 + Firefox WebDriver BiDi DOM
- **动作**：AT-SPI 语义动作 / XTEST / BiDi 真实输入
- **确认**：tree_hash / 事件 / 页面条件
- **降级**：无语义界面（Canvas/游戏/raw X11 自绘）可显式切到像素通道（截图 + 坐标点击；次要、策略门控）

本地环境仓库：

```text
/data/projects/ai-agent-gui/linux-version
```

CLI（在仓库根执行）：

```bash
B="python3 routes/python/bin/agentgui"
```

## 0. 已有远程桌面：默认直接用它，不要新建

本地环境已常驻一套**用户能在浏览器里看到并亲手操作**的 XFCE 桌面（TigerVNC + noVNC）。
需要人机交接、需要用户登录、需要「让用户看一眼」时，**优先复用这一套**，
不要再用 `tools/agent-session.sh` 起新的 Xvfb/XFCE 会话（除非本套已确认损坏）。

| 项目 | 值 |
|---|---|
| systemd 服务 | `vnc-desktop.service`（TigerVNC，显示 `:5`，监听 `127.0.0.1:5905`） |
| 网页入口 | `novnc.service`（websockify，`0.0.0.0:6080`） |
| 用户访问（Tailscale） | `http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=remote` |
| 用户访问（局域网） | `http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=remote` |
| Windows 快捷方式 | 桌面 `remote-desktop.url` |
| VNC 密码 | `~/.vnc/novnc-password.txt`（需要时读文件使用，**不要打印到聊天/日志**） |
| 显示号 | `:5`（`export DISPLAY=:5`） |
| 分辨率 | 客户端 `resize=remote` 跟随浏览器窗口；服务端默认 1600×900 |
| 桌面布局 | 单条顶部面板：应用菜单 / 终端 / Firefox / 文件 / 任务栏 / 时钟（无底部 dock） |
| 终端 | 登录后自动开 `xfce4-terminal` 并聚焦，可直接打字 |

```bash
systemctl status vnc-desktop novnc
sudo systemctl restart vnc-desktop   # 注意：会杀掉桌面里所有窗口（含 Firefox）
```

要点：

- 同一个桌面只开**一个** noVNC 标签页；多客户端连接时 TigerVNC 会拒绝改分辨率。
- 启动参数必须禁用 GLX：本地环境 NVIDIA 驱动已损坏，Xvnc 一旦探测 GPU 就会卡成 `D` 状态（连 SIGKILL 都杀不掉）。
  配置在 `~/.config/tigervnc/config`（`extension=GLX`、`AcceptSetDesktopSize=1`）。
- 桌面里的 Firefox 启动器是 `~/.local/bin/firefox-remote`。
- 旧的 `vnc-xfce.service` 已废弃（可能停在 `deactivating`，重启机器后消失）。
- 重启 `vnc-desktop` 前确认用户没在桌面上做未保存的操作。

## 0.1 Firefox profile：人和自动化共用一份

> **强制规则（用户 2026-11-09 指定）**：除非用户当次明确要求换 profile，否则**一律使用
> `~/.mozilla/firefox/remote.default`**。不要用 snap 的 `zvt4rtsy.default`，不要用
> `~/agentgui-workspace/ffprofile`，也不要新建 profile。用户的 Google / Kaggle /
> Firefox 账号 / the university Canvas（canvas.example.edu）登录态都在这一份里。

| 用途 | profile 路径 | 启动方式 | 登录态 |
|---|---|---|---|
| **远程桌面 + agentgui 自动化（同一个实例）** | `~/.mozilla/firefox/remote.default` | `~/.local/bin/firefox-remote`；自动化用 `$B web launch`（复用同一个实例，BiDi `ws://127.0.0.1:9222`） | `/opt/firefox`（关沙箱）；已登录 Google、**Kaggle**、Firefox 账号（同步） |
| 人类桌面的真实 Firefox | `~/snap/firefox/common/.mozilla/firefox/zvt4rtsy.default` | snap `firefox`（物理 GNOME 桌面） | 用户日常使用 |
| 旧自动化 profile（仅兜底） | `~/agentgui-workspace/ffprofile` | 仅在 `remote.default` 不存在时自动回退 | 早期从 snap profile 拷贝 |

人看的窗口和自动化操作的是**同一个 Firefox 实例**：

- 桌面上的启动器 `~/.local/bin/firefox-remote` 固定带 `--remote-debugging-port=9222`。
- `$B web launch` 先探测 `127.0.0.1:9222`，端口通就直接接管，**不会**再起第二个浏览器。
- 端口没开（例如机器刚重启）时，`web launch` 会自己用 `/opt/firefox` + `remote.default` 在 `:5` 上启动一个。

规则：

- 要用户看见 / 要用户亲手登录 → 直接在 noVNC 里操作那个 Firefox；登录态就写进 `remote.default`，自动化立刻能用。
- 要脚本点击、抓 DOM → `$B web ...`，操作的就是用户眼前这个窗口（会抢焦点/切标签页，跑任务前先告诉用户）。
- **绝不**把 snap profile `rsync` 覆盖到 `remote.default` —— 会抹掉用户在远程桌面里登录的账号（Kaggle、Firefox 同步、Google）。
- 不要同时手工再开一个 `firefox-remote` 之外的同 profile 实例：profile 锁会冲突。
- 两份 profile 都要用同一套账号时，用 Firefox 同步（Sync）而不是拷贝目录。

## 会话与环境

```bash
cd /data/projects/ai-agent-gui/linux-version
# This machine currently uses :82 (recorded in var/state/agent-session.json).
# Start/reuse it with:
AGENTGUI_DISPLAY_NUM=82 bash tools/agent-session.sh
$B session probe
```

会话状态写入：

```text
var/state/agent-session.json
```

若机器上已有别的 Xvfb（例如 `:98`），先读该文件或 `pgrep -af Xvfb`，不要假设一定是 `:77`。需要固定显示号时：

```bash
AGENTGUI_DISPLAY_NUM=77 bash tools/agent-session.sh
```

> 只是要在**已有的远程桌面**上操作时（见上面第 0 节），直接用 `DISPLAY=:5`，
> 不必跑 `agent-session.sh`，也不要在 `:5` 上再起一套 Xvfb。

Firefox 用**远程桌面那一份**（`~/.mozilla/firefox/remote.default`，见第 0.1 节），
不再默认使用旧的 `~/agentgui-workspace/ffprofile`：

```text
~/.mozilla/firefox/remote.default      # 默认
~/agentgui-workspace/ffprofile         # 仅在 remote.default 缺失时回退
```

BiDi 端点：`ws://127.0.0.1:9222`。端点不可达时先：

```bash
$B web launch
```

- 端口已开（用户在 VNC 桌面里开着 Firefox）→ 直接接管这个实例，不新起浏览器。
- 端口没开 → 用 `/opt/firefox` + `remote.default` 在 `:5` 上启动，用户同样能看到。
- 想临时换回旧 profile：`AGENTGUI_FIREFOX_PROFILE=~/agentgui-workspace/ffprofile $B web launch`
  （先关掉共用实例，profile 锁不允许两个同时用）。

## 浏览器自动化（登录态站点、多步交互）

```bash
$B web launch
$B web open --url "https://example.com/account" --timeout-ms 60000
$B web wait --selector "main" --timeout-ms 15000
$B web observe --max-elements 200
```

`web observe` 返回可交互元素和 ref。之后可用 ref / selector / role / name 操作：

```bash
$B web click --ref "<ref>" --wait-selector "form" --timeout-ms 15000
$B web type  --ref "<ref>" --text "hello" --wait-text "Saved" --timeout-ms 15000
$B web eval  --expr "$(cat /tmp/ag_extract.js)"
```

常用命令：

| 命令 | 用途 |
|---|---|
| `web open --url URL [--new-tab]` | 导航 |
| `web wait --selector/--text/--url-glob/--js-expr` | 等渲染/跳转 |
| `web observe --max-elements N` | 交互元素清单 + ref |
| `web click --ref/--selector/--role/--name` | 点击 |
| `web type --text ...` | 输入 |
| `web key --keys ...` | 按键 |
| `web scroll` | 滚动 |
| `web eval --expr EXPR` | 只读 JS 提取 |
| `web tabs` / `web switch` / `web close` | 标签页管理 |

### 登录态复用

默认情况下自动化**直接复用**远程桌面那个 Firefox（`remote.default`），
它的登录态是用户在 noVNC 里亲手登录的，不需要再拷贝 profile。

只有在需要用旧自动化 profile 时，才走「拷贝人类 profile」这条路：

```bash
# 先停 agentgui Firefox，再镜像人类 profile
rsync -a --delete \
  --exclude lock --exclude .parentlock \
  ~/snap/firefox/common/.mozilla/firefox/<id>.default/ \
  ~/agentgui-workspace/ffprofile/
```

随后 `$B web launch` 重新启动。profile 过期时需要人工在图形界面登录一次；登录后按下面的 HITL 流程确认用户真的能看到窗口。

**注意区分**：上面这条只针对 `~/agentgui-workspace/ffprofile`。
远程桌面用的 `~/.mozilla/firefox/remote.default` 里已经有用户亲手登录的
Kaggle / Firefox 同步 / Google 账号，**不要对它做 rsync 覆盖**，否则登录态全丢。
需要在远程桌面里补登录时，直接让用户在 noVNC 里操作 `firefox-remote` 那个窗口。

### 域名 allowlist

`web open` 只允许 `policy.json` 的 `allow_web_domains` 中的域名。新增域名属于仓库修改，必须走 git：

```bash
cd /data/projects/ai-agent-gui/linux-version
git status
# 修改 policy.json
git add policy.json
git commit -m "policy: allow <domain>"
```

不要绕过 allowlist 用 curl/Playwright 直接抓取。

### JS 提取限制

`web eval` 有 `WRITE_GUARD`，禁止：

```text
fetch(  xmlhttprequest  websocket  import(  eval(  function(
document.cookie  localstorage  clipboard.write
```

JS 用箭头函数：

```js
(() => {
  return [...document.querySelectorAll("a")].map(a => ({
    text: a.innerText.trim(),
    href: a.href
  }));
})()
```

需要站点 API 的结构化数据时，写独立 Python 脚本直接使用 `agentgui.webbidi.Bidi`，不要绕过 guard 在页面里 `fetch`。

## 原生桌面应用

```bash
$B observe --app nautilus --max-nodes 200
$B find --app nautilus --role button --name-contains 创建
$B click --app nautilus --key "<key>" --post tree_changed
$B set_text --app org.gnome.TextEditor --key "<key>" --text "内容"
$B key --keys "ctrl+shift+n"
$B launch --app-id org.gnome.Nautilus --wait-frame --app-name nautilus
$B close_window --app nautilus --role frame
```

## 像素降级（无语义界面，次要通道）

```bash
$B observe --app <name> --fallback pixel      # 仅在语义为空时降级
$B screenshot --out /tmp/handoff.png
$B click_xy --x N --y N --post pixel_changed
$B move_xy --x N --y N
```

- 判读在调用方：用读图工具核对 PNG，**不要**在仓库里接 VLM/OCR。
- 策略门控：`policy.json` 的 `deny` 加 `screenshot` / `coordinate_input` 即整体关闭；语义存在时 `--fallback pixel` 不降级。

## HITL 交接与“用户视角可见性”（强制）

凡是要请用户在界面里操作/查看（登录、人工确认、看页面），交接前必须确认用户此刻真的能看到目标界面。**不得只凭进程存活 / 命令成功就交接。**

交接前 3 项检查：

1. **截图并亲自读图**：

   ```bash
   DISPLAY=$(python3 -c 'import json;print(json.load(open("var/state/agent-session.json"))["display"])')
   DISPLAY="$DISPLAY" $B screenshot --out /tmp/handoff.png
   ```

   用读图工具确认目标窗口/页面可见且内容正确。PNG 异常小（如 <10 KB）通常是黑屏/空白。

2. **窗口 Map 状态**：

   ```bash
   DISPLAY="$DISPLAY" xwininfo -root -tree | grep -i "Mozilla Firefox"
   DISPLAY="$DISPLAY" xwininfo -id <id> | grep "Map State"
   ```

   必须是 `IsViewable`；`IsUnMapped` = 被最小化，先恢复再交接。

3. **观看通道**：

   如果交接目标是**常驻远程桌面**（显示 `:5`），直接给用户 URL 即可，不需要 watch-session：

   ```text
   http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=remote
   ```

   只有交接目标是 agentgui 自己的 Xvfb（如 `:82`）时才需要：

   ```bash
   AGENTGUI_DISPLAY_NUM=82 bash tools/watch-session.sh
   ```

   本地环境打开：

   ```text
   http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale
   ```

   > 端口冲突：`6080` 已被常驻的 `novnc.service`（远程桌面 `:5`）占用。
   > `watch-session.sh` 启动前先确认，必要时给它换端口，不要把常驻服务停掉。

   如果你从另一台机器访问，先建隧道：

   ```bash
   ssh -N -L 6080:127.0.0.1:6080 a@127.0.0.1
   ```

### 窗口被最小化时如何恢复

openbox 无任务栏，Firefox 最小化后可能无处可点。恢复方式：

```bash
DISPLAY="$DISPLAY" xwininfo -root -tree | grep -i "Mozilla Firefox"   # 取主窗口 id
DISPLAY="$DISPLAY" python3 -c '
from Xlib import X, display, protocol
d = display.Display(); root = d.screen().root
w = d.create_resource_object("window", 0x1200015)   # 换成上一步的 id
root.send_event(protocol.event.ClientMessage(
    window=w,
    client_type=d.intern_atom("_NET_ACTIVE_WINDOW"),
    data=(32, [2, X.CurrentTime, 0, 0, 0])),
    event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
d.sync()'
```

用户侧：桌面空白处按鼠标中键 → openbox 窗口列表 → 选 Firefox；或 `Alt+Tab`。

## 坑位

- **Xvfb 启动坑（本地环境 kernel 7.0）**：`Xvfb` 需要 `-extension GLX`，且不要加 `-listen tcp`，否则进程会卡在 D 状态。`tools/agent-session.sh` 已改为默认加 GLX、关闭 TCP；如需 TCP 应急通道用 `AGENTGUI_XVFB_TCP=1`。
- **BiDi 僵尸会话（高危）**：Firefox 同时只允许 1 个活动 BiDi 会话。自写脚本必须在 `finally` 里 `session.end` + `ws.close()`。
  现在浏览器是**用户眼前那个共用实例**，别再用 `pkill -f firefox` 清场（会把用户的窗口一起关掉）。
  优先重试连接；确实卡死时先告知用户，再用 `systemctl restart vnc-desktop` 或重新 `firefox-remote` 重启。
- **每条 CLI 命令一个 BiDi 会话**：页面重渲染后旧 `ref` 失效，重新 `web observe`。
- **跨命令定位标签页**：不要传旧的 context id；用 `--tab "<URL 子串>"`，唯一查询 URL 最稳。
- **`web open` 只校验域名 allowlist**；`web click` 不校验，仅用于任务内页面交互。
- **长任务**：后台运行并轮询日志，遵守 4 分钟/命令预算；多批次任务先建 `state/` 和完成标记。
- **登录态过期**：重新镜像人类 profile；不要尝试用 `storage.setCookies`（此 Firefox 报 `unknown command`）。
- **远程桌面相关**：
  - 6080 端口被常驻 `novnc.service` 占用，不要再另起 websockify 抢端口。
  - 同一桌面开多个 noVNC 标签页 → TigerVNC 拒绝 `SetDesktopSize`，表现为「窗口大小不跟随」；关掉多余标签页并刷新。
  - `vncserver`/`Xvnc` 必须带 `-extension GLX`，否则会卡死成 `D` 状态，`systemctl stop` 也会一直 `deactivating`（只能重启机器清掉）。
  - 桌面里 `x-terminal-emulator` 必须指向 `xfce4-terminal`；指向 GTK4 的 `ptyxis` 会在坏显卡上卡死，表现为「点终端没反应」。
  - 不要在 `DISPLAY=:5` 下手工起 `xfce4-panel`/`xfdesktop`：不带 `GDK_BACKEND=x11` 会走 Wayland 后端，画出幽灵窗口。需要重启就重启整个 `vnc-desktop` 服务。

## 仓库修改规则

所有仓库修改走 git，保持工作区可审计：

```bash
cd /data/projects/ai-agent-gui/linux-version
git status
# 修改
git add <files>
git commit -m "<message>"
```

`var/`、`routes/rust/target/` 已 gitignore，不要提交运行数据/构建产物。若 exFAT 上的 git 出现 mode 噪音，先把仓库 clone 到 `/tmp/opencode/aglv-work` 修改，再提交回本地仓库。

## 验收与回归

```bash
python3 -m unittest discover -s routes/python/tests
python3 tests/acceptance/run.py --scenario smoke
python3 tests/acceptance/run.py --scenario all
cd routes/rust && cargo build --release
```

## 按需参考

- `spec/01-contract.md`：命令面 / 错误码 / 退出码
- `spec/03-acceptance-tests.md`：A1–A6 验收定义
- `spec/decisions/ADR-010-pixel-fallback.md`：像素通道决策与边界
- `docs/status.md`：当前验证状态与证据
- `tools/watch-session.sh`、`tools/video-replay.sh`、`tools/video-frames.sh`
