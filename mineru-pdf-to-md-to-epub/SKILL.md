---
name: mineru-pdf-to-md-to-epub
description: 'Convert/process a PDF through the MinerU pipeline (PDF → Markdown via MinerU cloud API → EPUB via pandoc) and file it into the math-ai-base-data hot_papers library. The library lives on a data disk mounted at /data, and the pipeline runs locally. Use when the user asks to "do the mineru pipeline", "pdf to md to epub", "convert this paper/book", "process this pdf", "install this into hot papers", gives a PDF path/URL/arXiv link and expects md + epub outputs under math-ai-base-data, or asks to check/refresh MinerU API tokens. Triggers: mineru, pdf 转 md, 转 epub, hot papers, hot-paper-md, hot-paper-epub, math-ai-base-data, data disk, MinerU token.'
---

# MinerU PDF → MD → EPUB pipeline

Converts a PDF into Markdown（MinerU 云端 API，保留公式/表格）与 EPUB（pandoc），产物进入 `math-ai-base-data` 库：

- 源 PDF：`<ROOT>/hot_papers/<subfolder>/`
- MD：`<ROOT>/hot-paper-md/<同相对子目录>/<Title>.md`（含图片目录 `images/`）
- EPUB：`<ROOT>/hot-paper-epub/<同相对子目录>/<Title>.epub`

## 0. 环境现状

- **本地环境运行**：不再通过 SSH。
- 数据盘：`/dev/sdc1`，NTFS，挂载点 `/data`
- `<ROOT>`：`/data/projects/math-ai-base-data`
- Python 环境：`<ROOT>/.venv-linux`（requests + pymupdf）。旧的 `.venv` 是 Windows venv，**不要用**。
- EPUB：本地环境 `pandoc`。

### 挂载与磁盘状态（重要）

正常写入需要可写挂载：

```bash
findmnt /data
test -w /data/projects/math-ai-base-data && echo RW_OK
```

正常状态应为 rw（fstab 已配置 `uid=1000,gid=1000`）：

```bash
sudo mount /data
findmnt /data   # 期望 rw,uid=1000
```

若内核日志出现 `volume is dirty and "force" flag is not set!`，说明 NTFS dirty
（常见于未安全弹出）。2026-10-22 曾出现 `$MFTMirr does not match $MFT`，
用 `sudo ntfsfix -d /dev/sdc1` 修复 MFTMirr、清 dirty、清日志后恢复正常 rw。

处理顺序：

1. `sudo umount /data`
2. `sudo ntfsfix -d /dev/sdc1`（快速修复；若失败或怀疑索引损坏，转 Windows `chkdsk /f`）
3. `sudo mount /data`，确认 `findmnt` 为 `rw`
4. 写入测试：`touch /data/.rwtest && rm /data/.rwtest`

`ntfsfix` 不能替代完整的 chkdsk；如果修复后仍报错，再到 Windows 上跑 `chkdsk /f`。
不要为了能读而长期挂 `ro,force`，那会让后续 pipeline 全部无法写。

## 1. MANDATORY：先确认目标子目录

用户必须指定 PDF 放入 `hot_papers/` 的哪个子目录（如 `2026.3.16ai`）。未指定就**先用 question 工具问**，不要猜。

PDF 一律以**论文/书名本身命名**（不用 arXiv/会议编号）：

- arXiv：取 abs 页 `<title>`（去掉 `[id]` 前缀）。
- 本地文件：用 pymupdf 读第一页标题。
- 文件名清洗：`: / \ * ? " < > |` 替换为 ` -`，合并多余空格。

例：`DeepSeek-V4.1-Flash: Pushing...` → `DeepSeek-V4.1-Flash - Pushing....pdf`

## 2. Token 管理

- **主 token 文件**：`<ROOT>/minerU-api-token.md`。
- **本地缓存（首选来源）**：`~/.local/share/kilo-secrets/mineru`，用 `<secret-store>/get-secret.sh mineru` 读取（首次弹 Zenity 掩码窗，之后走缓存）。
- 校验 / 删除过期 / 用本地缓存刷新主文件：

```bash
S=~/.config/opencode/skills/mineru-pdf-to-md-to-epub/scripts
bash $S/mineru_token_check.sh                 # 只探测并打印 HTTP 状态
bash $S/mineru_token_check.sh --delete-expired        # 删 401 的 token 文件
bash $S/mineru_token_check.sh --refresh-from-local-cache   # 用缓存写回主文件
```

- 探活原理：`POST https://mineru.net/api/v4/file-urls/batch`（假文件，不上传、不耗配额）；`200 = 有效`，`401 + A0202 = 过期`。
- **绝不打印/回显 token**；不要把它写进命令行参数（会进 shell 历史/日志）——脚本都从文件读取并导出为 `MINERU_API_TOKEN`。

## 3. 步骤

1. **放入 PDF**（标题命名）：

```bash
ROOT=/data/projects/math-ai-base-data
cp "/path/to/foo.pdf" "$ROOT/hot_papers/<sub>/<Title>.pdf"
```

   sanity check：`file`、pymupdf 页数；>200 页会自动拆分并在产物中出现 `partNNN_<Title>.md`。

2. **PDF → MD**（长任务，**后台运行 + 轮询日志**）：

```bash
S=~/.config/opencode/skills/mineru-pdf-to-md-to-epub/scripts
LOG=/tmp/opencode/mineru-pdf2md-$(date +%s).log
nohup bash $S/mineru_pdf2md.sh "<sub>/<Title>.pdf" > "$LOG" 2>&1 &
```

   - 幂等：已存在且新的 MD 会跳过。
   - 轮询：定期 `tail "$LOG"`，用 `pgrep -f mineru_pdf2md` 判断是否结束；不要阻塞等待。

3. **验证**：列 `hot-paper-md/<sub>/*.md` 与 `images/` 数量/大小；抽查 md 头部与公式、表格是否完整。

4. **MD → EPUB**（可选；pandoc，后台运行 + 轮询日志）：

```bash
LOG=/tmp/opencode/md2epub-$(date +%s).log
nohup bash $S/md2epub.sh "<sub>/<Title>.md" > "$LOG" 2>&1 &
```

   轮询同步骤 2（`tail "$LOG"` / `pgrep -f md2epub`）。

5. 汇报时给出实际本地路径：`/data/projects/math-ai-base-data/...`。

## 4. 坑位（实战）

- **NTFS dirty / MFTMirr mismatch**：不要强行 rw 挂载；先在 Windows `chkdsk /f`。只读挂载用 `-o ro,force`。
- **NTFS3 `do_truncate` 挂起**：重复处理“已完成”的文件时，python 可能进入 `D` 状态、`/proc/<pid>/wchan = do_truncate`、长时间零输出。处理：`kill -9`，确认产物是否已完整；不要盲目重跑。频繁出现时把 config 的 `cache_root`/`preprocessed_root` 改到本地环境 ext4 盘（如 `~/...`）。
- 旧 `.venv`（Windows）不可执行：用 `.venv-linux`。
- token 过期表现为 `POST /file-urls/batch` 的 401 重试 5 次后失败；先跑 §2 的检查。
- MinerU 结果是 zip 流，下载后自动解包到 `cache/hot_paper_epub/downloads/<hash>/`，再发布 MD 与 `images/`；缓存可清理但不要动正在跑的任务目录。

## 5. 脚本清单

- `scripts/mineru_pdf2md.sh`：本地 MinerU 反填 MD（读 token 文件、用 `.venv-linux`、`--config config/hot_paper_epub.json`）。
- `scripts/md2epub.sh`：本地 MD→EPUB（本地环境 pandoc）。
- `scripts/mineru_token_check.sh`：token 探活 / 删除过期 / 从本地缓存刷新。

（可选环境变量：`MINERU_ROOT`、`MINERU_CONFIG`、`PANDOC_PATH`、`TOKEN_GET`。）
