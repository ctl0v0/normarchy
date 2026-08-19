#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from catalog_lib import (
    atomic_write_json,
    canonical_url,
    inspect_video,
    now_iso,
    read_json,
    today,
    validate_candidates,
    validate_catalog,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = ROOT / "catalog" / "norm-clips.json"
DEFAULT_CANDIDATES = ROOT / "catalog" / "candidates.json"
DEFAULT_SOURCES = ROOT / "catalog" / "discovery-sources.json"
DEFAULT_CHANNELS = ROOT / "catalog" / "known-channels.json"

HARD_EXCLUSIONS = (
    "reaction to norm", "reacting to norm", "reacts to norm",
    "norm macdonald ai", "ai norm macdonald", "deepfake", "voice clone",
    "norm macdonald tribute", "remembering norm macdonald",
    "rip norm macdonald", "norm macdonald obituary",
    "norm macdonald died", "death of norm macdonald", "cause of death",
    "comedians remember norm", "talks about norm macdonald",
    "story about norm macdonald",
)
SOFT_EXCLUSIONS = (
    "tribute", "rip ", "remembering", "legacy", "explained", "analysis",
    "documentary", "obituary", "cause of death", "deepfake", "impression",
)


def load_channels(path):
    data = read_json(path)
    by_id = {}
    by_name = {}
    for channel in data.get("channels", []):
        if channel.get("id"):
            by_id[str(channel["id"])] = channel
        if channel.get("name"):
            by_name[str(channel["name"]).lower()] = channel
    return by_id, by_name


def channel_tier(info, by_id, by_name):
    channel_id = str(info.get("channel_id") or info.get("uploader_id") or "")
    if channel_id in by_id:
        return by_id[channel_id]["tier"]
    channel_name = str(info.get("channel") or info.get("uploader") or "").lower()
    if channel_name in by_name:
        return by_name[channel_name]["tier"]
    return "fan"


def candidate_score(info, source, tier):
    title = str(info.get("title") or "")
    lowered = title.lower()
    score = min(10, max(0, int(source.get("priority", 0))))
    if "norm macdonald" in lowered or "norm macdonald" in lowered.replace("’", "'"):
        score += 40
    elif "norm" in lowered:
        score += 18
    if tier == "official":
        score += 25
    elif tier == "archive":
        score += 15
    if any(term in lowered for term in ("full", "uncut", "complete", "interview", "stand-up", "standup")):
        score += 7
    if info.get("duration"):
        score += 5
    if any(term in lowered for term in SOFT_EXCLUSIONS):
        score -= 25
    return max(0, min(100, score))


def automated_rejection(title):
    lowered = str(title or "").lower()
    for phrase in HARD_EXCLUSIONS:
        if phrase in lowered:
            return f"automated exclusion: {phrase}"
    if "norm macdonald" not in lowered and "norm" not in lowered:
        return "automated exclusion: Norm is not named in the title"
    return ""


def search_query(source, max_results):
    limit = max(1, min(int(max_results), 100))
    command = [
        "yt-dlp",
        "--ignore-config",
        "--flat-playlist",
        "--no-warnings",
        "--dump-json",
        f"ytsearch{limit}:{source['query']}",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=90, check=False)
    rows = []
    for line in result.stdout.splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return source, rows, result.stderr.strip()


def command_discover(args):
    catalog = read_json(args.catalog)
    sources = read_json(args.sources)
    by_id, by_name = load_channels(args.channels)
    if args.candidates.exists():
        data = read_json(args.candidates)
    else:
        data = {"schema_version": 1, "updated_at": now_iso(), "candidates": []}

    production_ids = {str(item["id"]) for item in catalog.get("items", [])}
    existing = {str(item["id"]): item for item in data.get("candidates", [])}
    queries = sources.get("queries", [])
    default_limit = int(sources.get("default_max_results", 20))
    max_results = args.max_per_query or default_limit
    found = 0
    added = 0

    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 4))) as executor:
        futures = [executor.submit(search_query, source, max_results) for source in queries]
        for future in as_completed(futures):
            source, rows, error = future.result()
            print(f"{source['category']}: {len(rows)} results")
            if not rows and error:
                print(f"  {error.splitlines()[-1]}", file=sys.stderr)
            for info in rows:
                video_id = str(info.get("id") or "")
                if len(video_id) != 11 or video_id in production_ids:
                    continue
                found += 1
                title = str(info.get("title") or "").strip()[:300]
                tier = channel_tier(info, by_id, by_name)
                rejection = automated_rejection(title)
                score = candidate_score(info, source, tier)
                query = str(source["query"])
                if video_id in existing:
                    candidate = existing[video_id]
                    candidate["title"] = title or candidate.get("title", "")
                    candidate["channel"] = str(info.get("channel") or info.get("uploader") or candidate.get("channel", ""))[:200]
                    candidate["channel_id"] = str(info.get("channel_id") or info.get("uploader_id") or candidate.get("channel_id", ""))[:100]
                    if info.get("duration"):
                        candidate["duration_seconds"] = max(1, round(float(info["duration"])))
                    candidate["score"] = max(int(candidate.get("score", 0)), score)
                    query_list = candidate.setdefault("queries", [])
                    if query not in query_list:
                        query_list.append(query)
                    continue

                status = "rejected" if rejection else "pending"
                existing[video_id] = {
                    "id": video_id,
                    "url": canonical_url(video_id),
                    "title": title,
                    "channel": str(info.get("channel") or info.get("uploader") or "")[:200],
                    "channel_id": str(info.get("channel_id") or info.get("uploader_id") or "")[:100],
                    "duration_seconds": max(1, round(float(info["duration"]))) if info.get("duration") else None,
                    "category": str(source["category"]),
                    "source_tier": tier,
                    "score": score,
                    "queries": [query],
                    "discovered_at": now_iso(),
                    "status": status,
                    "review_reason": rejection,
                    "reviewed_by": "automation" if rejection else "",
                    "reviewed_at": now_iso() if rejection else "",
                    "promoted_in_version": None,
                }
                added += 1

    status_order = {"accepted": 0, "pending": 1, "rejected": 2, "promoted": 3}
    data["schema_version"] = 1
    data["updated_at"] = now_iso()
    data["candidates"] = sorted(
        existing.values(),
        key=lambda item: (status_order.get(item.get("status"), 9), -int(item.get("score", 0)), item["id"]),
    )
    errors = validate_candidates(data)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    atomic_write_json(args.candidates, data)
    pending = sum(1 for item in data["candidates"] if item["status"] == "pending")
    print(f"Discovered {found} non-production results; added {added}; {pending} pending review")
    return 0


def read_ids(path):
    if not path:
        return []
    text = Path(path).read_text(encoding="utf-8")
    try:
        value = json.loads(text)
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, dict):
            return [str(item) for item in value.get("ids", [])]
    except json.JSONDecodeError:
        pass
    return [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]


def command_review(args):
    data = read_json(args.candidates)
    candidates = {item["id"]: item for item in data.get("candidates", [])}
    accepted = set(args.accept or []) | set(read_ids(args.accept_file))
    rejected = set(args.reject or []) | set(read_ids(args.reject_file))
    accepted_reasons = {}
    rejected_reasons = {}
    if args.decisions:
        decisions = read_json(args.decisions)
        for entry in decisions.get("accepted", []):
            if isinstance(entry, str):
                video_id = entry
            else:
                video_id = str(entry.get("id", ""))
                if video_id in candidates:
                    for field in ("title", "category", "source_tier"):
                        if entry.get(field):
                            candidates[video_id][field] = entry[field]
                    accepted_reasons[video_id] = str(entry.get("reason", ""))
            if video_id:
                accepted.add(video_id)
        for entry in decisions.get("rejected", []):
            if isinstance(entry, str):
                video_id = entry
            else:
                video_id = str(entry.get("id", ""))
                rejected_reasons[video_id] = str(entry.get("reason", ""))
            if video_id:
                rejected.add(video_id)
    if args.accept_above is not None:
        tiers = set(args.tiers.split(",")) if args.tiers else {"official", "archive", "fan"}
        accepted.update(
            item["id"] for item in candidates.values()
            if item.get("status") == "pending"
            and int(item.get("score", 0)) >= args.accept_above
            and item.get("source_tier") in tiers
        )
    overlap = accepted & rejected
    if overlap:
        print(f"ids cannot be both accepted and rejected: {', '.join(sorted(overlap))}", file=sys.stderr)
        return 1
    unknown = (accepted | rejected) - set(candidates)
    if unknown:
        print(f"unknown candidate ids: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 1

    timestamp = now_iso()
    for video_id in accepted:
        candidate = candidates[video_id]
        if candidate.get("status") != "promoted":
            candidate["status"] = "accepted"
            candidate["review_reason"] = accepted_reasons.get(video_id) or args.reason or "accepted for runtime verification"
            candidate["reviewed_by"] = args.reviewer
            candidate["reviewed_at"] = timestamp
    for video_id in rejected:
        candidate = candidates[video_id]
        if candidate.get("status") != "promoted":
            candidate["status"] = "rejected"
            candidate["review_reason"] = rejected_reasons.get(video_id) or args.reason or "rejected during editorial review"
            candidate["reviewed_by"] = args.reviewer
            candidate["reviewed_at"] = timestamp
    data["updated_at"] = timestamp
    atomic_write_json(args.candidates, data)
    print(f"Accepted {len(accepted)} and rejected {len(rejected)} candidates")
    return 0


def promotion_item(candidate):
    info = inspect_video(candidate["id"], probe_stream=True)
    duration = max(1, round(float(info.get("duration") or candidate.get("duration_seconds") or 0)))
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    if width <= 0 or height <= 0:
        raise RuntimeError("video dimensions are unavailable")
    kind = "short" if duration < 180 and height > width else ("source" if duration >= 900 else "clip")
    item = {
        "id": candidate["id"],
        "title": candidate["title"],
        "url": canonical_url(candidate["id"]),
        "kind": kind,
        "category": candidate["category"],
        "source_tier": candidate["source_tier"],
        "enabled": True,
        "verified_on": today(),
        "duration_seconds": duration,
        "width": width,
        "height": height,
    }
    if candidate.get("channel_id"):
        item["source_channel_id"] = candidate["channel_id"]
    if candidate.get("channel"):
        item["source_channel"] = candidate["channel"]
    if info.get("upload_date"):
        value = str(info["upload_date"])
        if len(value) == 8:
            item["uploaded_on"] = f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return item


def command_promote(args):
    catalog = read_json(args.catalog)
    data = read_json(args.candidates)
    production_ids = {item["id"] for item in catalog.get("items", [])}
    selected_ids = set(args.ids or []) | set(read_ids(args.ids_file))
    accepted = [
        item for item in data.get("candidates", [])
        if item.get("status") == "accepted"
        and item["id"] not in production_ids
        and (not selected_ids or item["id"] in selected_ids)
    ]
    accepted.sort(key=lambda item: (-int(item.get("score", 0)), item["id"]))
    if args.limit:
        accepted = accepted[: args.limit]
    if not accepted:
        print("No accepted candidates selected", file=sys.stderr)
        return 1

    promoted = []
    failures = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 3))) as executor:
        futures = {executor.submit(promotion_item, item): item for item in accepted}
        for future in as_completed(futures):
            candidate = futures[future]
            try:
                item = future.result()
                promoted.append(item)
                print(f"verified {item['id']}: {item['title']}")
            except Exception as error:
                failures.append((candidate["id"], str(error)))
                print(f"failed {candidate['id']}: {error}", file=sys.stderr)
    if failures and not args.allow_failures:
        print("Promotion aborted; no catalog files were changed", file=sys.stderr)
        return 1
    if failures:
        print(f"Skipping {len(failures)} candidates that failed runtime verification", file=sys.stderr)
    if not promoted:
        print("No candidates passed runtime verification", file=sys.stderr)
        return 1

    next_version = int(catalog.get("catalog_version", 0)) + 1
    catalog["$schema"] = "./catalog.schema.json"
    catalog["schema_version"] = 1
    catalog["catalog_version"] = next_version
    catalog["generated_on"] = today()
    catalog["items"].extend(sorted(promoted, key=lambda item: item["id"]))
    candidate_map = {item["id"]: item for item in data["candidates"]}
    for video_id, error in failures:
        candidate = candidate_map[video_id]
        candidate["status"] = "pending"
        candidate["review_reason"] = "runtime verification failed: " + error[:240]
    for item in promoted:
        candidate = candidate_map[item["id"]]
        candidate["status"] = "promoted"
        candidate["promoted_in_version"] = next_version
        candidate["review_reason"] = "runtime format and range probes passed"
    data["updated_at"] = now_iso()

    errors = validate_catalog(catalog) + validate_candidates(data)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    atomic_write_json(args.catalog, catalog)
    atomic_write_json(args.candidates, data)
    print(f"Promoted {len(promoted)} videos in catalog version {next_version}")
    return 0


def health_item(item):
    try:
        info = inspect_video(item["id"], probe_stream=True)
        return {
            "id": item["id"],
            "status": "healthy",
            "duration_seconds": max(1, round(float(info.get("duration") or 0))),
            "width": int(info.get("width") or 0),
            "height": int(info.get("height") or 0),
            "error": "",
        }
    except Exception as error:
        return {"id": item["id"], "status": "failed", "error": str(error)[:300]}


def command_health(args):
    catalog = read_json(args.catalog)
    items = [item for item in catalog.get("items", []) if item.get("enabled")]
    if args.limit:
        items = items[: args.limit]
    results = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 3))) as executor:
        futures = {executor.submit(health_item, item): item for item in items}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"{result['id']}: {result['status']}")
    results.sort(key=lambda item: item["id"])
    healthy = sum(1 for item in results if item["status"] == "healthy")
    report = {
        "schema_version": 1,
        "catalog_version": catalog.get("catalog_version", 0),
        "checked_at": now_iso(),
        "format_policy": "combined HTTPS audio/video up to 720p; bounded range probes",
        "summary": {"checked": len(results), "healthy": healthy, "failed": len(results) - healthy},
        "items": results,
    }
    atomic_write_json(args.output, report)
    print(f"Health report: {healthy}/{len(results)} healthy")
    return 0


def command_validate(args):
    catalog = read_json(args.catalog)
    errors = validate_catalog(catalog)
    if args.candidates.exists():
        candidates = read_json(args.candidates)
        errors.extend(validate_candidates(candidates))
        production_ids = {item["id"] for item in catalog["items"]}
        for candidate in candidates.get("candidates", []):
            if candidate["status"] != "promoted" and candidate["id"] in production_ids:
                errors.append(f"candidate {candidate['id']}: production id must be marked promoted")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Catalog valid: {len(catalog['items'])} production videos")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Normarchy catalog discovery and release pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    validate.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    validate.set_defaults(handler=command_validate)

    discover = subparsers.add_parser("discover")
    discover.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    discover.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    discover.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    discover.add_argument("--channels", type=Path, default=DEFAULT_CHANNELS)
    discover.add_argument("--max-per-query", type=int)
    discover.add_argument("--workers", type=int, default=2)
    discover.set_defaults(handler=command_discover)

    review = subparsers.add_parser("review")
    review.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    review.add_argument("--accept", nargs="*")
    review.add_argument("--reject", nargs="*")
    review.add_argument("--accept-file", type=Path)
    review.add_argument("--reject-file", type=Path)
    review.add_argument("--accept-above", type=int)
    review.add_argument("--tiers", help="comma-separated tiers used with --accept-above")
    review.add_argument("--decisions", type=Path, help="JSON file with accepted/rejected entries and metadata corrections")
    review.add_argument("--reviewer", required=True)
    review.add_argument("--reason", default="")
    review.set_defaults(handler=command_review)

    promote = subparsers.add_parser("promote")
    promote.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    promote.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    promote.add_argument("--ids", nargs="*")
    promote.add_argument("--ids-file", type=Path)
    promote.add_argument("--limit", type=int)
    promote.add_argument("--workers", type=int, default=2)
    promote.add_argument("--allow-failures", action="store_true", help="promote passing candidates and return failures to pending")
    promote.set_defaults(handler=command_promote)

    health = subparsers.add_parser("health")
    health.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    health.add_argument("--output", type=Path, default=ROOT / "reports" / "catalog-health.json")
    health.add_argument("--limit", type=int)
    health.add_argument("--workers", type=int, default=2)
    health.set_defaults(handler=command_health)
    return parser


def main():
    args = build_parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
