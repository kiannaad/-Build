"""大肥鱼语音引擎：调用本地 GPT-SoVITS api_v2.py 生成 WAV。

设计：
- GPT-SoVITS 作为独立 HTTP 服务跑在 127.0.0.1:9880；
- 本模块只负责选参考音频、发请求、落盘、读时长；
- RVC 先不接，等 GPT-SoVITS 音色确认后再加。
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import wave
from datetime import datetime
from pathlib import Path

DEFAULT_API = "http://127.0.0.1:9880"
DEFAULT_REFS = Path(r"D:\大肥鱼\Voice\refs")
DEFAULT_OUT = Path(r"D:\大肥鱼\Voice\output")
DEFAULT_RVC = Path(r"D:\RVC")
DEFAULT_RVC_MODEL = r"D:\RVC\assets\weights\feiyu_v2.pth"

# 情绪 -> (参考文件, 参考文本, 说明)
REF_MAP = {
    "neutral": ("neutral.wav", "嗯，我在。今天过得怎么样？不用急着说，慢慢来就好。"),
    "neutral_2": ("neutral_2.wav", "今天早上有点凉，我把窗户关小了一点，又给自己倒了杯温水。"),
    "happy": ("happy.wav", "你回来啦。我刚还在想，今天要不要偷偷多吃一块小饼干。"),
    "tender": ("tender.wav", "先歇一会儿吧。事情做不完也没关系，我陪你坐一会儿。"),
    "sad": ("sad.wav", "其实我也有点闷。不过没关系，今天不想说话的话，我们就安静待着。"),
}


def _ref_path(emotion: str, refs: Path) -> tuple[Path, str]:
    name, text = REF_MAP.get(emotion, REF_MAP["neutral"])
    path = refs / name
    if not path.exists():
        raise FileNotFoundError(f"参考音频不存在: {path}")
    return path, text


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def rvc_convert(
    input_wav: Path,
    output_wav: Path,
    *,
    model: str | None = None,
    index: str | None = None,
    pitch: int = 0,
    index_rate: float = 0.75,
    protect: float = 0.33,
    rms_mix_rate: float = 1.0,
    rvc_dir: Path | None = None,
) -> dict:
    """调用 RVC 的 infer/cli.py 做音色转换；没有权重/环境时明确报错。"""
    rvc_dir = Path(rvc_dir or os.environ.get("RVC_DIR", DEFAULT_RVC))
    model = model or os.environ.get("RVC_MODEL", DEFAULT_RVC_MODEL)
    py = rvc_dir / ".venv" / "Scripts" / "python.exe"
    cli = rvc_dir / "infer" / "cli.py"
    if not py.exists():
        raise RuntimeError(f"RVC Python 环境不存在: {py}（先装 RVC 依赖）")
    if not cli.exists():
        raise RuntimeError(f"RVC CLI 不存在: {cli}")
    if not Path(model).exists():
        raise RuntimeError(f"RVC 权重不存在: {model}（把 feiyu_v2.pth 放到 assets/weights）")
    cmd = [
        str(py), str(cli),
        "--model", str(model),
        "--input", str(input_wav),
        "--output", str(output_wav),
        "--f0-method", "rmvpe",
        "--pitch", str(int(pitch)),
        "--index-rate", str(float(index_rate)),
        "--protect", str(float(protect)),
        "--rms-mix-rate", str(float(rms_mix_rate)),
        "--format", "wav",
        "--overwrite",
    ]
    if index:
        cmd += ["--index", str(index)]
    started = time.perf_counter()
    proc = subprocess.run(
        cmd, cwd=str(rvc_dir), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-1200:]
        raise RuntimeError(f"RVC 转换失败（exit {proc.returncode}）: {tail}")
    return {
        "path": str(output_wav),
        "duration_sec": round(_wav_duration(output_wav), 2),
        "elapsed_sec": round(time.perf_counter() - started, 2),
        "model": Path(model).name,
    }


def synthesize(
    text: str,
    *,
    emotion: str = "neutral",
    speed: float = 1.0,
    use_rvc: bool = False,
    rvc_model: str | None = None,
    api_base: str | None = None,
    refs: Path | None = None,
    out_dir: Path | None = None,
) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("text 不能为空")
    api_base = (api_base or os.environ.get("GPT_SOVITS_API", DEFAULT_API)).rstrip("/")
    refs = Path(refs or os.environ.get("VOICE_REFS", DEFAULT_REFS))
    out_dir = Path(out_dir or os.environ.get("VOICE_OUT", DEFAULT_OUT))
    out_dir.mkdir(parents=True, exist_ok=True)
    ref, prompt_text = _ref_path(emotion, refs)

    payload = {
        "text": text,
        "text_lang": "zh",
        "ref_audio_path": str(ref),
        "prompt_text": prompt_text,
        "prompt_lang": "zh",
        "text_split_method": "cut5",
        "batch_size": 1,
        "media_type": "wav",
        "streaming_mode": False,
        "speed_factor": float(speed),
        "parallel_infer": True,
        "seed": -1,
    }
    req = urllib.request.Request(
        f"{api_base}/tts",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"GPT-SoVITS 返回 HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"连不上 GPT-SoVITS API {api_base}: {exc}") from exc

    if "json" in content_type.lower():
        raise RuntimeError(f"GPT-SoVITS 返回 JSON 而不是音频: {body[:500]}")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = out_dir / f"voice-{stamp}.wav"
    out.write_bytes(body)
    elapsed = round(time.perf_counter() - started, 2)
    result = {
        "path": str(out),
        "duration_sec": round(_wav_duration(out), 2),
        "emotion": emotion,
        "reference": ref.name,
        "elapsed_sec": elapsed,
        "rvc": False,
    }
    if use_rvc:
        rvc_out = out.with_name(f"{out.stem}-rvc.wav")
        converted = rvc_convert(out, rvc_out, model=rvc_model)
        result.update({
            "source": str(out),
            "path": converted["path"],
            "duration_sec": converted["duration_sec"],
            "rvc": True,
            "rvc_elapsed_sec": converted["elapsed_sec"],
        })
    return result


def status() -> dict:
    api_base = os.environ.get("GPT_SOVITS_API", DEFAULT_API).rstrip("/")
    refs = Path(os.environ.get("VOICE_REFS", DEFAULT_REFS))
    out_dir = Path(os.environ.get("VOICE_OUT", DEFAULT_OUT))
    refs_ready = {k: (refs / v[0]).exists() for k, v in REF_MAP.items()}
    api_ok = False
    api_error = ""
    try:
        with urllib.request.urlopen(f"{api_base}/docs", timeout=3) as resp:
            api_ok = resp.status == 200
    except Exception as exc:  # noqa: BLE001
        api_error = str(exc)
    rvc_dir = Path(os.environ.get("RVC_DIR", DEFAULT_RVC))
    rvc_py = rvc_dir / ".venv" / "Scripts" / "python.exe"
    rvc_cli = rvc_dir / "infer" / "cli.py"
    rvc_model = os.environ.get("RVC_MODEL", DEFAULT_RVC_MODEL)
    rvc_missing = []
    if not rvc_py.exists():
        rvc_missing.append(f"python: {rvc_py}")
    if not rvc_cli.exists():
        rvc_missing.append(f"cli: {rvc_cli}")
    if not Path(rvc_model).exists():
        rvc_missing.append(f"model: {rvc_model}")
    return {
        "api": api_base,
        "api_ok": api_ok,
        "api_error": api_error,
        "refs_dir": str(refs),
        "refs_ready": refs_ready,
        "output_dir": str(out_dir),
        "rvc_ready": not rvc_missing,
        "rvc_model": rvc_model,
        "rvc_missing": rvc_missing,
    }
