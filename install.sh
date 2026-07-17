#!/usr/bin/env bash
# whisper-transcribe 一键安装：自动准备 ffmpeg、Python 3.12、venv、依赖，并预下载 large-v3 模型。
# 跑完即可直接用 scripts/transcribe.py 转录。跳过模型下载：SKIP_MODEL_DOWNLOAD=1 bash install.sh
set -e
cd "$(dirname "$0")"
SKILL_DIR="$PWD"
PY_VENV="$SKILL_DIR/.venv/bin/python"
MODEL_REPO="mlx-community/whisper-large-v3-mlx"
# large-v3-mlx 的 main commit；模型极少更新，若某天失效改这里，或手动 snapshot_download 一次
MODEL_HASH="49e6aa286ad60c14352c404340ded53710378a11"
HF_CACHE="$HOME/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-mlx"

# ---- 模型下载函数 ----
# 三级 fallback：snapshot_download 直连 → snapshot_download 镜像 → curl 直下并构造 HF cache。
# 前两级对海外/正常网络生效；curl 兜底专治国内 HEAD→xet 链 hf_hub 走不通的情况。
# 三条路径最终都把模型放进同一个 HF cache 结构，transcribe.py 用 repo id + 离线模式即可命中。

curl_fallback() {
  # 直接 curl 文件到标准 HF cache 目录，绕开 hf_hub 的 HEAD/校验问题
  local SNAP="$HF_CACHE/snapshots/$MODEL_HASH"
  mkdir -p "$SNAP" "$HF_CACHE/refs"
  printf '%s' "$MODEL_HASH" > "$HF_CACHE/refs/main"
  local f
  for f in config.json weights.npz; do
    if [ -s "$SNAP/$f" ]; then echo "   ✓ $f 已存在，跳过"; continue; fi
    echo "   ↓ $f ..."
    curl -L -C - --fail -m 3600 \
      "https://hf-mirror.com/$MODEL_REPO/resolve/main/$f" -o "$SNAP/$f" || return 1
  done
  [ -s "$SNAP/weights.npz" ] && [ -s "$SNAP/config.json" ] || return 1
  echo "   ✅ curl 下载完成，HF 缓存已构造"
}

verify_model() {
  # 离线加载验证：确认模型真能用，不是只下了文件
  echo "🧪 验证模型可离线加载（约 10-20s）..."
  if HF_HUB_OFFLINE=1 "$PY_VENV" -c "
import mlx_whisper.load_models as lm
lm.load_model('$MODEL_REPO')
print('LOAD_OK')
" 2>/dev/null | grep -q LOAD_OK; then
    echo "   ✅ 模型可正常离线加载，开箱即用"
  else
    echo "   ⚠️ 加载验证未通过（文件已下载到缓存）。可手动排查："
    echo "      HF_HUB_OFFLINE=1 .venv/bin/python scripts/transcribe.py 你的音频.mp3"
  fi
}

download_model() {
  echo "⬇️  下载 large-v3 模型（约 3GB，首次最久，之后秒载）..."
  echo "    国内若长时间卡住可 Ctrl+C，export HF_ENDPOINT=https://hf-mirror.com 后重跑 install.sh"
  local ok=0 ep
  for ep in "https://huggingface.co" "https://hf-mirror.com"; do
    echo "   尝试 snapshot_download（$ep）..."
    if HF_HUB_OFFLINE=0 HF_ENDPOINT="$ep" HF_HUB_DOWNLOAD_TIMEOUT=30 \
       "$PY_VENV" -c "
from huggingface_hub import snapshot_download
snapshot_download('$MODEL_REPO')
print('SNAPSHOT_OK')
" 2>/dev/null | grep -q SNAPSHOT_OK; then
      ok=1; echo "   ✅ snapshot_download 成功"; break
    fi
    echo "   ($ep 不通)"
  done
  if [ "$ok" != "1" ]; then
    echo "   snapshot_download 均失败，改用 curl 直下并构造本地缓存..."
    curl_fallback || { echo "❌ 模型下载失败。请检查网络（国内务必先 export HF_ENDPOINT=https://hf-mirror.com 再重跑）"; exit 1; }
  fi
  verify_model
}

# ---- 主流程 ----
echo "🚀 whisper-transcribe 安装中..."

# 1. 仅支持 Apple Silicon
if [ "$(uname -m)" != "arm64" ]; then
  echo "❌ 仅支持 Apple Silicon（M1/M2/M3/M4），当前架构: $(uname -m)"
  exit 1
fi

# 2. 需要 Homebrew（装 ffmpeg / python@3.12）
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

# 5. venv + 依赖（requirements.txt 已 pin huggingface_hub==1.21.0 规避 1.22+ 下载 bug）
echo "📦 创建虚拟环境并安装依赖（含 mlx-whisper、torch 等，约 200MB）..."
"$PY" -m venv .venv
.venv/bin/pip install -U pip -q
.venv/bin/pip install -q -r requirements.txt

# 6. 预下载模型
echo ""
if [ "${SKIP_MODEL_DOWNLOAD:-0}" = "1" ]; then
  echo "⏭️  SKIP_MODEL_DOWNLOAD=1，跳过模型下载。首次转录时会再尝试下载（~3GB）。"
else
  download_model
fi

echo ""
echo "✅ 安装完成！"
echo "   试用: .venv/bin/python scripts/transcribe.py /path/to/audio.mp3"
