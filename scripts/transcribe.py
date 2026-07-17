#!/usr/bin/env python3
"""
mlx-whisper 本地语音转文字（Apple Silicon Metal GPU 加速）。
默认 large-v3 模型，输出逐句分行的 Markdown 逐字稿 / 带时间戳的 SRT 字幕。

用法:
  transcribe.py <音频或视频文件> [--model MODEL] [--language LANG] \
                [--format md|srt|all] [--output-dir DIR] [--output-name NAME] [--vad]
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
    fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", tmp_path],
            check=True, capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        # 失败时清理临时文件，并把 ffmpeg 的 stderr 暴露给用户（默认会被吞掉）
        os.unlink(tmp_path)
        stderr = e.stderr.decode("utf-8", "ignore").strip() if e.stderr else ""
        tail = "\n".join(stderr.splitlines()[-8:])
        raise RuntimeError(
            f"ffmpeg 抽音频失败（确认已装 ffmpeg 且文件可读）:\n{tail}"
        ) from None
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    return tmp_path


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


def transcribe_with_vad(audio_path: str, model: str, language):
    """silero-vad 检测语音段，逐段转录并按时间偏移拼回。

    适合长音频/会议录音：跳过静音段（提速 + 减少 "you you you" 类幻觉）。
    对口播类高密度语音收益小，故默认不开（由 --vad 触发）。
    """
    import numpy as np
    import torch
    from silero_vad import load_silero_vad, get_speech_timestamps
    from mlx_whisper.audio import load_audio, SAMPLE_RATE

    print("🔊 VAD 分析中...", file=sys.stderr)
    wav = np.asarray(load_audio(audio_path, sr=SAMPLE_RATE))
    vad = load_silero_vad()
    ts = get_speech_timestamps(
        torch.from_numpy(wav), vad, return_seconds=True,
        min_speech_duration_ms=250, min_silence_duration_ms=500, speech_pad_ms=200,
    )
    if not ts:
        return {"segments": [], "text": ""}

    # 合并相邻近段（gap ≤ 1.0s）：减少 whisper 调用次数，保留自然停顿
    merged = [dict(ts[0])]
    for seg in ts[1:]:
        if seg["start"] - merged[-1]["end"] <= 1.0:
            merged[-1]["end"] = seg["end"]
        else:
            merged.append(dict(seg))

    dur = wav.shape[0] / SAMPLE_RATE
    speech = sum(s["end"] - s["start"] for s in merged)
    print(f"   音频 {dur:.0f}s，VAD 识别语音 {speech:.0f}s（{speech/dur*100:.0f}%），分 {len(merged)} 段转录",
          file=sys.stderr)

    import mlx_whisper
    all_segments = []
    idx = 0
    for i, seg in enumerate(merged, 1):
        s_i = int(seg["start"] * SAMPLE_RATE)
        e_i = int(seg["end"] * SAMPLE_RATE)
        chunk = wav[s_i:e_i]
        if len(chunk) < int(SAMPLE_RATE * 0.1):
            continue
        print(f"   [{i}/{len(merged)}] 转录 {seg['start']:.1f}–{seg['end']:.1f}s", file=sys.stderr)
        res = mlx_whisper.transcribe(chunk, path_or_hf_repo=model, language=language)
        for r in res.get("segments", []):
            r["start"] = round(r["start"] + seg["start"], 3)
            r["end"] = round(r["end"] + seg["start"], 3)
            r["id"] = idx
            all_segments.append(r)
            idx += 1
    return {"segments": all_segments, "text": "".join(s["text"] for s in all_segments)}


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
    p.add_argument("--vad", action="store_true",
                   help="开启 silero VAD 去静音（长音频/会议录音推荐；口播类默认无需）")
    args = p.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"❌ 文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)
    if not input_path.is_file():
        print(f"❌ 路径不是文件（可能是目录）: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else input_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = args.output_name or input_path.stem

    audio_path = str(input_path)
    temp_audio = None
    if input_path.suffix.lower() in VIDEO_EXTS:
        print(f"🎬 抽取音频: {input_path.name}", file=sys.stderr)
        try:
            audio_path = video_to_audio(str(input_path))
            temp_audio = audio_path
        except RuntimeError as e:
            print(f"❌ {e}", file=sys.stderr)
            sys.exit(1)

    # 默认离线：模型已在 HF cache。huggingface_hub 1.23 在线模式对小文件 head call 有
    # FileMetadataError bug。换新模型首次下载时：
    #   HF_ENDPOINT=https://hf-mirror.com HF_HUB_OFFLINE=0 <venv>/python transcribe.py ...
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

    try:
        import mlx_whisper
    except ImportError:
        print("❌ mlx-whisper 未安装，请在 skill venv 里: pip install mlx-whisper", file=sys.stderr)
        if temp_audio and os.path.exists(temp_audio):
            os.unlink(temp_audio)
        sys.exit(2)

    lang = args.language if args.language and args.language != "auto" else None
    print(f"🎙️  转写中... 模型={args.model} 语言={args.language}{' [VAD]' if args.vad else ''}",
          file=sys.stderr)
    try:
        if args.vad:
            result = transcribe_with_vad(str(audio_path), args.model, lang)
        else:
            result = mlx_whisper.transcribe(
                audio_path,
                path_or_hf_repo=args.model,
                language=lang,
            )
    except ImportError:
        print("❌ --vad 需要 silero-vad，请在 skill venv 里: pip install silero-vad", file=sys.stderr)
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
