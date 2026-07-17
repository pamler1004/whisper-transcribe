# Whisper Transcribe · macOS 本地语音转文字 Skill

> Local speech-to-text for macOS Apple Silicon — works in both **Claude Code** and **Codex** (shared `SKILL.md` format).

基于 [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) 的本地语音转文字，Apple Silicon 原生 **Metal GPU 加速**，默认 **large-v3** 模型。封装成一个 Skill在对话里丢个音频/视频文件就能转，完全本地、不上云。

## ✨ 特性

- 🚀 **Metal GPU 加速**：large-v3 在 M1 Pro 上约 **4.7x 实时**（1 小时音频 ≈ 13 分钟），接近 RTX 4060 的 5.6x
- 🎬 **音视频通吃**：视频自动 ffmpeg 抽音频，不用手动转
- 📝 **两种输出**：逐句逐字稿（`md`，每行一句）/ 带时间戳字幕（`srt`）
- ✨ **快速上下文校对（可选）**：转录前可选择是否校对。开启则通读一次，只修正能明确判断的错字、专名和断词，不改写口语，结果另存为「-校对版」文件、原始 ASR 稿保留；关闭则只出原始稿，最快
- 🔇 **可选 VAD 去静音**：`--vad` 用 silero-vad 切掉静音段，适合会议 / podcast / 采访等长静音音频（提速 + 减少 "you you" 幻觉）；口播类默认不开
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

`install.sh` 会自动装好 ffmpeg、Python 3.12、虚拟环境和所有依赖，并**预下载 large-v3 模型（约 3GB）+ 离线加载验证**——跑完即可直接转录。下载走三级 fallback（huggingface.co 直连 → hf-mirror → curl 兜底），国内网络也能成；不想在安装时下模型可用 `SKIP_MODEL_DOWNLOAD=1 bash install.sh`。

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

# 长音频/会议录音去静音（减少幻觉、提速）
.venv/bin/python scripts/transcribe.py meeting.mp3 --vad
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `--model` | 模型 repo | `mlx-community/whisper-large-v3-mlx` |
| `--language` | `zh`/`en`/`ja`/`auto` 等 | `zh` |
| `--format` | `md` / `srt` / `all` | `md` |
| `--output-dir` | 输出目录 | 原文件同目录 |
| `--vad` | silero VAD 去静音（长音频/会议推荐） | 关 |

### 作为 Skill（Claude Code / Codex）

安装到 `~/.claude/skills/`（Claude Code）或 `~/.codex/skills/`（Codex）后，直接在对话里把音频/视频文件丢进去，或说「转字幕」「转写音频」，agent 会自动调用。两个平台共用同一个 `SKILL.md`。

### 批量处理与性能

批量任务按文件**顺序处理**：每个文件依次转录、快速校对、写入源文件旁边，过程中报告 `n/总数` 进度。不要并发跑多个 large-v3 实例——它们会争抢 Apple Silicon 的统一内存与 Metal GPU，通常更慢，也可能造成内存压力。

建议每批最多 **5 个文件**。M1 Pro 16GB 实测约 4.7x 实时；更多文件请拆批，分批报告进度。

### 支持的格式

- **视频**：mp4 / mov / mkv / avi / flv / webm / m4v / wmv / ts / mts
- **音频**：mp3 / wav / m4a / flac / aac / ogg / aiff / wma / opus 等（ffmpeg 能解的都行）

## 📝 搭配 zimu-to-note（字幕转笔记）

转录出的逐字稿是口语化的。想进一步变成结构化知识笔记（按逻辑主题重组、去口播填充词、保留金句、底部折叠原文对照），衔接姊妹项目 [zimu-to-note](https://github.com/pamler1004/zimu-to-note)：

```bash
git clone https://github.com/pamler1004/zimu-to-note.git ~/.claude/skills/zimu-to-note   # Codex 换 ~/.codex/skills/
```

装好后，对转录出的 md 说「整理这篇」「字幕转笔记」即可。

## ⚠️ 已知坑：模型下载

下载 large-v3 可能撞两类问题，`install.sh` 已自动处理，了解即可：

1. **huggingface_hub 1.22+ 小文件 bug**：1.22 重写了下载路径（PR#4394），在线下载会让 config.json 等小文件报 `FileMetadataError`。已通过 `requirements.txt` pin `huggingface_hub==1.21.0` 规避（mlx-whisper 对该包无版本约束）。
2. **国内 hf_hub HEAD→xet 链不通**：任何版本都可能，症状 `LocalEntryNotFoundError`。`install.sh` 会自动 curl 兜底（hf-mirror 直下文件并构造 HF cache）。

两条路都失败时手动补模型：
```bash
CACHE=~/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-mlx
HASH=49e6aa286ad60c14352c404340ded53710378a11
SNAP="$CACHE/snapshots/$HASH"
mkdir -p "$SNAP" "$CACHE/refs"; printf '%s' "$HASH" > "$CACHE/refs/main"
curl -L -C - https://hf-mirror.com/mlx-community/whisper-large-v3-mlx/resolve/main/config.json -o "$SNAP/config.json"
curl -L -C - https://hf-mirror.com/mlx-community/whisper-large-v3-mlx/resolve/main/weights.npz -o "$SNAP/weights.npz"
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
