#!/usr/bin/env bash
# whisper-transcribe 一键安装：自动准备 ffmpeg、Python 3.12、venv 和所有 Python 依赖。
# 运行后即可直接用 scripts/transcribe.py 转录（首次会自动下载 large-v3 模型约 3GB）。
set -e
cd "$(dirname "$0")"

echo "🚀 whisper-transcribe 安装中..."

# 1. 仅支持 Apple Silicon
if [ "$(uname -m)" != "arm64" ]; then
  echo "❌ 仅支持 Apple Silicon（M1/M2/M3/M4），当前架构: $(uname -m)"
  exit 1
fi

# 2. 需要 Homebrew（用来装 ffmpeg / python@3.12）
if ! command -v brew >/dev/null 2>&1; then
  echo "❌ 需要 Homebrew，请先安装: https://brew.sh"
  exit 1
fi

# 3. ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "📦 安装 ffmpeg..."
  brew install ffmpeg
fi

# 4. Python 3.12
if command -v python3.12 >/dev/null 2>&1; then
  PY="$(command -v python3.12)"
elif [ -x /opt/homebrew/opt/python@3.12/bin/python3.12 ]; then
  PY="/opt/homebrew/opt/python@3.12/bin/python3.12"
else
  echo "📦 安装 python@3.12..."
  brew install python@3.12
  PY="/opt/homebrew/opt/python@3.12/bin/python3.12"
fi
echo "🐍 Python: $PY"

# 5. venv + 依赖
echo "📦 创建虚拟环境并安装依赖（含 mlx-whisper、torch 等，约 200MB）..."
"$PY" -m venv .venv
.venv/bin/pip install -U pip -q
.venv/bin/pip install -q -r requirements.txt

echo ""
echo "✅ 安装完成！"
echo "   首次转录会自动下载 large-v3 模型（约 3GB）到本机缓存，之后秒载。"
echo "   国内下载慢可先设镜像: export HF_ENDPOINT=https://hf-mirror.com"
echo ""
echo "   试用: .venv/bin/python scripts/transcribe.py /path/to/audio.mp3"
