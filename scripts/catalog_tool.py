#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ALLOWED_KINDS = {"short", "clip", "source"}
ALLOWED_TIERS = {"official", "archive", "fan"}


def validate(catalog):
    errors = []
    seen = set()
    for index, item in enumerate(catalog.get("items", [])):
        prefix = f"item {index + 1}"
        video_id = str(item.get("id", ""))
        if not video_id:
            errors.append(f"{prefix}: missing id")
        elif video_id in seen:
            errors.append(f"{prefix}: duplicate id {video_id}")
        seen.add(video_id)
        if item.get("kind") not in ALLOWED_KINDS:
            errors.append(f"{prefix}: invalid kind")
        if item.get("source_tier") not in ALLOWED_TIERS:
            errors.append(f"{prefix}: invalid source_tier")
        if not str(item.get("url", "")).startswith(("https://www.youtube.com/", "https://youtu.be/")):
            errors.append(f"{prefix}: unsupported URL")
        duration = item.get("duration_seconds")
        if duration is not None and (not isinstance(duration, int) or duration <= 0):
            errors.append(f"{prefix}: duration_seconds must be a positive integer")
    return errors


def inspect_item(item):
    command = [
        "yt-dlp",
        "--simulate",
        "--no-playlist",
        "--no-warnings",
        "--socket-timeout",
        "10",
        "--retries",
        "1",
        "--print",
        "%(.{id,duration,width,height})j",
        item["url"],
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=40, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return item["id"], None, result.stderr.strip() or "metadata lookup failed"
    metadata = json.loads(result.stdout.strip().splitlines()[-1])
    return item["id"], metadata, ""


def enrich(catalog, workers):
    items = catalog.get("items", [])
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(inspect_item, item): item for item in items}
        for future in as_completed(futures):
            item = futures[future]
            completed += 1
            try:
                video_id, metadata, error = future.result()
            except Exception as exception:
                video_id, metadata, error = item["id"], None, str(exception)
            if metadata and metadata.get("id") == video_id and metadata.get("duration"):
                item["duration_seconds"] = max(1, round(float(metadata["duration"])))
                if metadata.get("width"):
                    item["width"] = int(metadata["width"])
                if metadata.get("height"):
                    item["height"] = int(metadata["height"])
                print(f"[{completed}/{len(items)}] {video_id}: {item['duration_seconds']}s")
            else:
                print(f"[{completed}/{len(items)}] {video_id}: {error}", file=sys.stderr)


def write_atomic(path, catalog):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser(description="Validate and enrich the Normarchy catalog")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    catalog = json.loads(args.input.read_text(encoding="utf-8"))
    errors = validate(catalog)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    if args.validate_only:
        durations = sum(1 for item in catalog.get("items", []) if item.get("duration_seconds"))
        print(f"Catalog valid: {len(catalog.get('items', []))} items, {durations} durations")
        return 0
    if args.output is None:
        parser.error("output is required unless --validate-only is used")

    enrich(catalog, max(1, min(args.workers, 8)))
    catalog["catalog_version"] = int(catalog.get("catalog_version", 0)) + 1
    write_atomic(args.output, catalog)
    missing = sum(1 for item in catalog["items"] if not item.get("duration_seconds"))
    print(f"Wrote {len(catalog['items'])} entries to {args.output} ({missing} without duration)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
