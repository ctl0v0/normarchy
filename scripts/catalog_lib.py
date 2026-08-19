#!/usr/bin/env python3

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse


VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
CATEGORY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FORMAT = (
    "best[height<=720][ext=mp4][protocol=https][vcodec!=none][acodec!=none]/"
    "best[height<=720][protocol=https][vcodec!=none][acodec!=none]/"
    "best[protocol=https][vcodec!=none][acodec!=none]"
)
EXTRACTOR_ARGS = {"youtube": {"player_client": ["android"]}}


def now_iso():
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today():
    return datetime.now(UTC).date().isoformat()


def canonical_url(video_id):
    if not VIDEO_ID_RE.fullmatch(str(video_id or "")):
        raise ValueError(f"invalid YouTube id: {video_id}")
    return f"https://www.youtube.com/watch?v={video_id}"


def video_id_from_url(value):
    text = str(value or "").strip()
    if VIDEO_ID_RE.fullmatch(text):
        return text
    parsed = urlparse(text)
    host = parsed.hostname.lower() if parsed.hostname else ""
    candidate = ""
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith(("/shorts/", "/embed/", "/live/")):
            candidate = parsed.path.split("/")[2]
    elif host == "youtu.be":
        candidate = parsed.path.strip("/").split("/", 1)[0]
    return candidate if VIDEO_ID_RE.fullmatch(candidate) else ""


def atomic_write_json(path, data):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, destination)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def exact_content_length(info):
    query_size = parse_qs(urlparse(info["url"]).query).get("clen", [])
    if query_size and query_size[0].isdigit():
        return int(query_size[0])
    if info.get("filesize"):
        return int(info["filesize"])
    result = _curl_range(info, 0, 0, include_headers=True)
    match = re.search(
        r"^content-range:\s*bytes\s+\d+-\d+/(\d+)\s*$",
        result.stdout,
        re.IGNORECASE | re.MULTILINE,
    )
    return int(match.group(1)) if match else 0


def _curl_range(info, start, end, include_headers=False):
    command = [
        "curl",
        "--fail",
        "--silent",
        "--show-error",
        "--max-time",
        "20",
        "--user-agent",
        info.get("http_headers", {}).get("User-Agent", "curl"),
        "--range",
        f"{start}-{end}",
    ]
    if include_headers:
        command.extend(["--dump-header", "-"])
    command.extend(["--output", "/dev/null", info["url"]])
    return subprocess.run(command, capture_output=True, text=True, check=False)


def inspect_video(video_id, probe_stream=True):
    from yt_dlp import YoutubeDL

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 12,
        "retries": 1,
        "extractor_args": EXTRACTOR_ARGS,
        "format": FORMAT,
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(canonical_url(video_id), download=False)
    if str(info.get("id", "")) != video_id:
        raise RuntimeError("YouTube returned a different video id")
    if probe_stream:
        size = exact_content_length(info)
        if size <= 0:
            raise RuntimeError("selected stream has no exact content length")
        first = _curl_range(info, 0, min(size - 1, 4095))
        if first.returncode != 0:
            raise RuntimeError(first.stderr.strip() or "initial media range failed")
        if size > 8192:
            middle_start = min(size - 4096, max(4096, size // 2))
            middle = _curl_range(info, middle_start, min(size - 1, middle_start + 4095))
            if middle.returncode != 0:
                raise RuntimeError(middle.stderr.strip() or "seek media range failed")
    return info


def validate_catalog(catalog):
    errors = []
    if not isinstance(catalog, dict):
        return ["catalog root must be an object"]
    items = catalog.get("items")
    if not isinstance(items, list) or not items:
        return ["catalog.items must be a non-empty array"]
    seen = set()
    required = {
        "id", "title", "url", "kind", "category", "source_tier",
        "enabled", "verified_on", "duration_seconds", "width", "height",
    }
    for index, item in enumerate(items):
        prefix = f"item {index + 1}"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        missing = sorted(required - set(item))
        if missing:
            errors.append(f"{prefix}: missing {', '.join(missing)}")
        video_id = str(item.get("id", ""))
        if not VIDEO_ID_RE.fullmatch(video_id):
            errors.append(f"{prefix}: invalid id")
        elif video_id in seen:
            errors.append(f"{prefix}: duplicate id {video_id}")
        seen.add(video_id)
        if video_id_from_url(item.get("url")) != video_id:
            errors.append(f"{prefix}: URL does not match id")
        if not str(item.get("title", "")).strip():
            errors.append(f"{prefix}: title is required")
        if item.get("kind") not in {"short", "clip", "source"}:
            errors.append(f"{prefix}: invalid kind")
        if item.get("source_tier") not in {"official", "archive", "fan"}:
            errors.append(f"{prefix}: invalid source_tier")
        if not CATEGORY_RE.fullmatch(str(item.get("category", ""))):
            errors.append(f"{prefix}: invalid category")
        if not isinstance(item.get("enabled"), bool):
            errors.append(f"{prefix}: enabled must be boolean")
        for field in ("duration_seconds", "width", "height"):
            value = item.get(field)
            if not isinstance(value, int) or value <= 0:
                errors.append(f"{prefix}: {field} must be a positive integer")
    return errors


def validate_candidates(data):
    errors = []
    candidates = data.get("candidates") if isinstance(data, dict) else None
    if not isinstance(candidates, list):
        return ["candidates.candidates must be an array"]
    seen = set()
    for index, candidate in enumerate(candidates):
        prefix = f"candidate {index + 1}"
        video_id = str(candidate.get("id", ""))
        if not VIDEO_ID_RE.fullmatch(video_id):
            errors.append(f"{prefix}: invalid id")
        elif video_id in seen:
            errors.append(f"{prefix}: duplicate id {video_id}")
        seen.add(video_id)
        if video_id_from_url(candidate.get("url")) != video_id:
            errors.append(f"{prefix}: URL does not match id")
        if candidate.get("status") not in {"pending", "accepted", "rejected", "promoted"}:
            errors.append(f"{prefix}: invalid status")
        if not CATEGORY_RE.fullmatch(str(candidate.get("category", ""))):
            errors.append(f"{prefix}: invalid category")
        if candidate.get("source_tier") not in {"official", "archive", "fan"}:
            errors.append(f"{prefix}: invalid source_tier")
    return errors
