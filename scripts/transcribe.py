#!/usr/bin/env python3
"""
mlx-whisper 本地语音转文字（Apple Silicon Metal GPU 加速）。
默认 large-v3 模型，输出带时间戳的 SRT 字幕 / 纯文本。

用法:
  transcribe.py <音频或视频文件> [--model MODEL] [--language LANG] \
                [--format srt|txt|all] [--output-dir DIR] [--output-name NAME]
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_MODEL = "mlx-community/whisper-large-v3-mlx"

# 视频扩展名：需要先用 ffmpeg 抽音频
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".flv", ".webm", ".m4v", ".wmv", ".ts", ".mts"}


def video_to_audio(video_path: str) -> str:
    """ffmpeg 抽成 16kHz 单声道 wav（whisper 最佳输入，避免重采样）。"""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", tmp.name],
        check=True, capture_output=True,
    )
    return tmp.name


def format_ts(seconds: float) -> str:
    """秒 -> SRT 时间戳 HH:MM:SS,mmm"""
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_srt(segments) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{format_ts(seg['start'])} --> {format_ts(seg['end'])}")
        lines.append(seg["text"].strip())
        lines.append("")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="mlx-whisper 本地语音转文字")
    p.add_argument("input", help="音频或视频文件路径")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"模型 (默认 {DEFAULT_MODEL})")
    p.add_argument("--language", default="zh",
                   help="语言代码 zh/en/ja/yue...，auto=自动检测 (默认 zh)")
    p.add_argument("--format", default="md", choices=["md", "srt", "all"],
                   help="输出格式 (md=逐句逐字稿, srt=带时间戳字幕, all=md+srt)")
    p.add_argument("--output-dir", default=None, help="输出目录 (默认与输入同目录)")
    p.add_argument("--output-name", default=None, help="输出文件名 (不含扩展名)")
    args = p.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"❌ 文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else input_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = args.output_name or input_path.stem

    audio_path = str(input_path)
    temp_audio = None
    if input_path.suffix.lower() in VIDEO_EXTS:
        print(f"🎬 抽取音频: {input_path.name}", file=sys.stderr)
        audio_path = video_to_audio(str(input_path))
        temp_audio = audio_path

    # 默认离线：模型已在 HF cache。huggingface_hub 1.23 在线模式对小文件 head call 有
    # FileMetadataError bug。换新模型首次下载时：
    #   HF_ENDPOINT=https://hf-mirror.com HF_HUB_OFFLINE=0 <venv>/python transcribe.py ...
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

    try:
        import mlx_whisper
        lang = args.language if args.language and args.language != "auto" else None
        print(f"🎙️  转写中... 模型={args.model} 语言={args.language}", file=sys.stderr)
        result = mlx_whisper.transcribe(
            audio_path,
            path_or_hf_repo=args.model,
            language=lang,
        )
    except ImportError:
        print("❌ mlx-whisper 未安装，请在 skill venv 里: pip install mlx-whisper", file=sys.stderr)
        sys.exit(2)
    finally:
        if temp_audio and os.path.exists(temp_audio):
            os.unlink(temp_audio)

    segments = result.get("segments", [])

    if args.format in ("md", "all"):
        # 逐句分行（口播逐字稿格式）：每个 segment 一行，无时间戳无序号
        md_content = "\n".join(s["text"].strip() for s in segments if s["text"].strip())
        md_path = output_dir / f"{base_name}.md"
        md_path.write_text(md_content + "\n", encoding="utf-8")
        print(f"✅ MD: {md_path}", file=sys.stderr)
    if args.format in ("srt", "all"):
        srt_path = output_dir / f"{base_name}.srt"
        srt_path.write_text(segments_to_srt(segments), encoding="utf-8")
        print(f"✅ SRT: {srt_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
