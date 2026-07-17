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

```bash
VENV=~/.claude/skills/whisper-transcribe/.venv/bin/python
SCRIPT=~/.claude/skills/whisper-transcribe/scripts/transcribe.py
for f in /path/to/dir/*.mp3; do
  "$VENV" "$SCRIPT" "$f"
done
```

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

0. **先问导出格式**：调用前用 AskUserQuestion 问用户要哪种——① **只要 MD**（逐句逐字稿，`--format md`）；② **SRT + MD**（字幕+逐字稿，`--format all`）。**不要 TXT**。输出默认导出到音频/视频文件**旁边**（同目录），无需改 `--output-dir`
1. **确认输入存在**：Read 或 `ls` 检查文件路径
2. **视频直接传**：脚本自动抽音频，无需手动转
3. **转完报告**：告诉用户输出的 md/srt 路径
4. **衔接下游**：要笔记 -> `zimu-to-note`；要烧字幕 -> `ffmpeg-usage`
5. **长音频耐心等**：large-v3 约 4.7x 实时，1 小时音频约 13 分钟。批量时逐个处理并报告进度

## 常见问题

- **FileMetadataError / LocalEntryNotFoundError**：`huggingface_hub 1.23` 在线模式对小文件 head call 的已知 bug。大文件能下、小文件（config.json 等）没存。用 curl 从 hf-mirror 补到 snapshot 目录即可：
  ```bash
  SNAP=~/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-mlx/snapshots/*/
  curl -sL https://hf-mirror.com/mlx-community/whisper-large-v3-mlx/resolve/main/config.json -o "$SNAP/config.json"
  ```
  补完后脚本默认离线模式即可运行
- **内存不足**：换 `--model mlx-community/whisper-large-v3-mlx-4bit`
- **识别语言不对**：`--language auto` 自动检测，或指定 `--language en`/`ja` 等
