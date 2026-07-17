---
name: whisper-transcribe
description: "本地语音转文字（Apple Silicon Metal GPU 加速）。把音频/视频文件转成逐句分行的 Markdown 逐字稿，或带时间戳的 SRT 字幕。基于 mlx-whisper + large-v3，M1/M2/M3/M4 原生 Metal 加速，无需 GPU 配置。当用户提到「转字幕」「语音转文字」「转录音频」「提取视频文字」「生成 SRT」「whisper 转写」「音频转文字」时使用。"
---

# 本地语音转文字 (mlx-whisper)

基于 mlx-whisper 的本地 ASR，Apple Silicon 原生 Metal GPU 加速，默认 large-v3 模型，输出带时间戳的 SRT 字幕。环境封装在 skill 自带 venv，开箱即用。

## 何时用

- 用户给音频/视频文件，要转成文字或字幕
- 需要 SRT 字幕文件（带时间戳），用于视频配字幕或后续整理
- 批量转录 podcast、会议录音、视频口播稿

## 与其他技能的衔接

- 转出的 SRT 要整理成笔记 -> 衔接 `zimu-to-note` 技能
- 只要纯文本、不需时间戳、且 newmax SenseVoice 服务(127.0.0.1:18923)在跑 -> 那个更快（参考 `ffmpeg-usage` 文档末尾）；但该服务常未启动且不出 SRT，默认用本技能
- 要下载视频再转写 -> 先 `video-download`，再本技能
- 转出 SRT 要烧录到视频 -> `ffmpeg-usage` 的字幕烧录命令

## 性能（M1 Pro 16G 实测）

| 方案 | 速度 | 说明 |
|------|------|------|
| **本技能 mlx-whisper large-v3** | ~4.7x 实时 | 1 小时音频 ≈ 13 分钟，质量最佳 |
| Windows 4060 faster-whisper large-v3 | 5.6x 实时 | 参照基准 |
| brew openai-whisper CPU large-v3 | <1x 实时 | MPS 模式有 bug 不可用，慢 |

## 前置条件

- ffmpeg（`/opt/homebrew/bin/ffmpeg`），视频抽音频用
- large-v3 模型约 3GB，已下载到 `~/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-mlx`，脚本默认 `HF_HUB_OFFLINE=1` 离线加载
- 换其他模型首次下载：前缀 `HF_ENDPOINT=https://hf-mirror.com HF_HUB_OFFLINE=0` 运行一次

## 用法

```bash
~/.claude/skills/whisper-transcribe/.venv/bin/python \
  ~/.claude/skills/whisper-transcribe/scripts/transcribe.py \
  "/path/to/audio.mp3"
```

默认：中文、large-v3、输出 **md 逐句逐字稿**到原文件同目录。脚本已默认离线模式，无需手动设环境变量。

输出格式说明：
- `md`（默认）：逐句分行逐字稿，每行一句，无时间戳无序号——适合口播稿整理、衔接 `zimu-to-note` 转笔记
- `srt`：带时间戳的字幕，适合直接配视频字幕
- `all`：md + srt 都输出

### 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--model` | HuggingFace 模型 repo 或本地路径 | `mlx-community/whisper-large-v3-mlx` |
| `--language` | 语言代码 `zh`/`en`/`ja`/`yue`/`auto` | `zh` |
| `--format` | `md` / `srt` / `all` | `md` |
| `--output-dir` | 输出目录 | 原文件同目录 |
| `--output-name` | 输出文件名（不含扩展名） | 同原文件名 |

### 视频直接转

视频文件直接传入，脚本自动用 ffmpeg 抽成 16kHz 单声道 wav：

```bash
~/.claude/skills/whisper-transcribe/.venv/bin/python \
  ~/.claude/skills/whisper-transcribe/scripts/transcribe.py \
  "/path/to/video.mp4" --format all
```

### 批量转写

批量时每批最多 5 个文件，由 Claude 逐个「转录 → 校对 → 落盘」并报告 `[n/总数]` 进度，详见下方「进度与批量规则」。不要并行；也不要用无校对的 shell 循环去跳过校对环节。

### 模型档位

| 模型 | 大小 | 适用 |
|------|------|------|
| `mlx-community/whisper-large-v3-mlx` | ~3GB | 默认，质量最佳 |
| `mlx-community/whisper-large-v3-mlx-4bit` | ~1.5GB | 16G 内存吃紧或要更快 |
| `mlx-community/whisper-large-v3-turbo-mlx` | ~800MB | 速度优先，质量略降 |
| `mlx-community/whisper-medium-mlx` | ~1.5GB | 质量与速度平衡 |

切换模型（首次需在线下载）：
```bash
HF_ENDPOINT=https://hf-mirror.com HF_HUB_OFFLINE=0 \
  ~/.claude/skills/whisper-transcribe/.venv/bin/python \
  ~/.claude/skills/whisper-transcribe/scripts/transcribe.py \
  input.mp3 --model mlx-community/whisper-large-v3-turbo-mlx
```

## 支持的文件格式

- **视频**（自动 ffmpeg 抽音频）：mp4 / mov / mkv / avi / flv / webm / m4v / wmv / ts / mts
- **音频**（直接解码，底层 ffmpeg/PyAV）：mp3 / wav / m4a / flac / aac / ogg / aiff / wma / opus 等，凡是 ffmpeg 能解码的都行

## Claude 使用指南

### 强制交互流程

当用户**已经提供音频/视频文件**，并明确要求转录/转字幕时，必须按下面顺序执行：

1. **确认文件存在**：用 `ls` 或等效只读方式检查文件路径
2. **在转录前询问格式**：文件确认存在后、**执行转录脚本前**，必须调用 `AskUserQuestion`；不得默认选格式，也不要用纯文本提问

   ```json
   {
     "header": "导出格式",
     "multiSelect": false,
     "question": "这次转录要导出什么格式？",
     "options": [
       {
         "label": "只要 MD",
         "description": "逐句分行的 Markdown 逐字稿，适合阅读、整理口播稿和转笔记。"
       },
       {
         "label": "SRT + MD",
         "description": "同时输出带时间戳字幕（SRT）和逐句分行逐字稿（MD），适合后续配字幕视频。"
       }
     ]
   }
   ```

3. **根据选择执行**：
   - 「只要 MD」→ `--format md`
   - 「SRT + MD」→ `--format all`
4. **输出位置固定**：不传 `--output-dir`，默认导出到音频/视频文件**旁边**（同目录）
5. **快速校对并报告结果**：转录后立刻进入下方的「快速校对」，校对结果写入「-校对版」文件（原始稿保留不动）；完成后列出原始稿和校对版的绝对路径

### 快速校对（转录后的必经步骤）

转录完成后，先发一条简短进度：`[2/2] 转录完成，正在快速校对明显识别错误…`，然后通读原始稿一次，把校对结果写入**新文件**：在原名后加 `-校对版`（原始 ASR 稿保留不动，便于回看对比）。

- 只要 MD：原始 `测试.md` + 校对版 `测试-校对版.md`
- SRT + MD：再加 `测试-校对版.srt`
- 实现方式：读原始 md/srt → 只改明显错误 → 写入 `同目录/原名-校对版.同后缀`

**只修正能由上下文明确确认的错误**：同音/近音错字、明显错词或断词、中英混排中的产品名/品牌名、明显错误的数字和单位。

**保持转录忠实**：不改写语气，不删除口头语或重复，不总结，不调整句子/段落顺序；无法从文字上下文确定的内容不猜、不改。校对版 MD 必须与原始稿行数、行序一一对应；校对版 SRT 只能改 cue 文本，cue 序号和时间戳与原始 srt 完全一致。

### 进度与批量规则

- **单文件**：只发两条阶段提示，避免打断用户：`[1/2] 正在转录：文件名`，随后是 `[2/2] 转录完成，正在快速校对明显识别错误…`。
- **批量**：顺序处理，每个文件开始/完成各报告一次：`[n/总数] 正在转录：文件名`、`[n/总数] 已完成：文件名`。每个文件完成转录后立即校对、落盘，再开始下一个；单个失败不影响已完成文件。
- **每批最多 5 个文件**。超过 5 个应拆批，分批报告进度。
- **不要并行转录**：large-v3 需要占用 Apple Silicon 的统一内存和 Metal GPU。并发加载多个实例会争抢资源，通常更慢，还可能引发内存压力。

### 其他执行规则

- 视频直接传：脚本自动抽音频，无需手动转
- 语言默认中文（`--language zh`）。内容明显是外语时（用户说明了，或从文件名/上下文能判断），主动用对应的 `--language`（如 `en`/`ja`/`yue`）；不额外弹窗问语言
- 不要输出 TXT 格式
- 要笔记 -> `zimu-to-note`；要烧字幕 -> `ffmpeg-usage`

## 常见问题

- **FileMetadataError / LocalEntryNotFoundError**：`huggingface_hub 1.23` 在线模式对小文件 head call 的已知 bug。大文件能下、小文件（config.json 等）没存。用 curl 从 hf-mirror 补到 snapshot 目录即可：
  ```bash
  SNAP=~/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-mlx/snapshots/*/
  curl -sL https://hf-mirror.com/mlx-community/whisper-large-v3-mlx/resolve/main/config.json -o "$SNAP/config.json"
  ```
  补完后脚本默认离线模式即可运行
- **内存不足**：换 `--model mlx-community/whisper-large-v3-mlx-4bit`
- **识别语言不对**：`--language auto` 自动检测，或指定 `--language en`/`ja` 等
