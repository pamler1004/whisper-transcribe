# Whisper Transcribe · macOS 本地语音转文字 Skill

> Local speech-to-text for macOS Apple Silicon — works in both **Claude Code** and **Codex** (shared `SKILL.md` format).

基于 [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) 的本地语音转文字，Apple Silicon 原生 **Metal GPU 加速**，默认 **large-v3** 模型。封装成一个 Skill在对话里丢个音频/视频文件就能转，完全本地、不上云。

## ✨ 特性

- 🚀 **Metal GPU 加速**：large-v3 在 M1 Pro 上约 **4.7x 实时**（1 小时音频 ≈ 13 分钟），接近 RTX 4060 的 5.6x
- 🎬 **音视频通吃**：视频自动 ffmpeg 抽音频，不用手动转
- 📝 **两种输出**：逐句逐字稿（`md`，每行一句）/ 带时间戳字幕（`srt`）
- ✨ **快速上下文校对**：转录后通读一次，只修正能明确判断的错字、专名和断词；不改写口语。校对结果另存为「-校对版」文件，原始 ASR 稿保留
- 🇨🇳 **中文友好**：中英混排识别好，标点、时间戳精确
- 🔒 **完全本地**：音频不出机器，无 API 费用

## 📊 性能对比

| 方案 | 速度 | 说明 |
|------|------|------|
| **本工具** mlx-whisper large-v3 (M1 Pro) | **~4.7x 实时** | 本仓库 |
| faster-whisper large-v3 (Windows RTX 4060) | 5.6x 实时 | 参照 |
| openai-whisper CPU (Mac) | <1x 实时 | MPS 模式有 bug 不可用，CPU 太慢 |

## 📦 安装

**推荐：一行命令**（macOS Apple Silicon + [Homebrew](https://brew.sh)）。Claude Code 和 Codex 用同一个仓库，只是 clone 的目标目录不同：

**Claude Code：**
```bash
git clone https://github.com/pamler1004/whisper-transcribe.git ~/.claude/skills/whisper-transcribe && ~/.claude/skills/whisper-transcribe/install.sh
```

**Codex：**
```bash
git clone https://github.com/pamler1004/whisper-transcribe.git ~/.codex/skills/whisper-transcribe && ~/.codex/skills/whisper-transcribe/install.sh
```

`install.sh` 会自动装好 ffmpeg、Python 3.12、虚拟环境和所有 Python 依赖。首次转录时自动下载 large-v3 模型（约 3GB）；国内下载慢可先设镜像 `export HF_ENDPOINT=https://hf-mirror.com`。

<details>
<summary>手动安装（不想用脚本时）</summary>

把仓库 clone 到 `~/.claude/skills/`（Claude Code）或 `~/.codex/skills/`（Codex）：

```bash
git clone https://github.com/pamler1004/whisper-transcribe.git ~/.claude/skills/whisper-transcribe   # Codex 把路径换成 ~/.codex/skills/
cd ~/.claude/skills/whisper-transcribe
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

需要：macOS Apple Silicon · Python 3.12 · ffmpeg。

</details>

## 🎯 用法

### 命令行

```bash
# 默认：中文 + large-v3 + 输出 md 逐字稿到原文件旁边
.venv/bin/python scripts/transcribe.py /path/to/audio.mp3

# 视频直接传（自动抽音频）
.venv/bin/python scripts/transcribe.py /path/to/video.mp4

# 同时输出 md + srt
.venv/bin/python scripts/transcribe.py audio.mp3 --format all

# 指定语言
.venv/bin/python scripts/transcribe.py audio.mp3 --language en
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `--model` | 模型 repo | `mlx-community/whisper-large-v3-mlx` |
| `--language` | `zh`/`en`/`ja`/`auto` 等 | `zh` |
| `--format` | `md` / `srt` / `all` | `md` |
| `--output-dir` | 输出目录 | 原文件同目录 |

### 作为 Skill（Claude Code / Codex）

安装到 `~/.claude/skills/`（Claude Code）或 `~/.codex/skills/`（Codex）后，直接在对话里把音频/视频文件丢进去，或说「转字幕」「转写音频」，agent 会自动调用。两个平台共用同一个 `SKILL.md`。

### 批量处理与性能

批量任务按文件**顺序处理**：每个文件依次转录、快速校对、写入源文件旁边，过程中报告 `n/总数` 进度。不要并发跑多个 large-v3 实例——它们会争抢 Apple Silicon 的统一内存与 Metal GPU，通常更慢，也可能造成内存压力。

建议每批最多 **5 个文件**。M1 Pro 16GB 实测约 4.7x 实时；更多文件请拆批，分批报告进度。

### 支持的格式

- **视频**：mp4 / mov / mkv / avi / flv / webm / m4v / wmv / ts / mts
- **音频**：mp3 / wav / m4a / flac / aac / ogg / aiff / wma / opus 等（ffmpeg 能解的都行）

## ⚠️ 已知坑：huggingface_hub 1.23 下载报错

`huggingface_hub 1.23` 在线模式对小文件（config.json 等）的 head call 有 bug，会报 `FileMetadataError`——大文件能下、小文件没存。解决办法：

```bash
# 用 curl 从镜像补 snapshot 目录下的小文件
SNAP=~/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-mlx/snapshots/*/
curl -sL https://hf-mirror.com/mlx-community/whisper-large-v3-mlx/resolve/main/config.json -o "$SNAP/config.json"

# 之后用离线模式运行（脚本默认已设 HF_HUB_OFFLINE=1）
.venv/bin/python scripts/transcribe.py audio.mp3
```

## 🧠 为什么不用 openai-whisper / faster-whisper？

- **openai-whisper**：Mac 上 MPS 模式 `model.to("mps")` 崩溃（torch + whisper 已知 bug），只能 CPU，large-v3 <1x 实时，不可用
- **faster-whisper**：底层 ctranslate2 在 Mac 上只有 CPU 后端，**不支持 Apple Metal**，没意义
- **mlx-whisper**：Apple 官方 MLX 框架，Metal 原生，是 Mac 上唯一能吃满 GPU 的 whisper 方案

## 🙏 致谢

- [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) · Apple MLX 团队
- [Whisper large-v3](https://github.com/openai/whisper) · OpenAI
- [mlx-community](https://huggingface.co/mlx-community) · 预转换的 MLX 模型

## 📄 License

MIT
