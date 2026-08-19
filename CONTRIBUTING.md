# Contributing Norm content

Normarchy stores links and metadata only. Never submit downloaded video,
mirrors, cookies, signed media URLs, or credentials.

## Suggest one video

Use the `Suggest a Norm clip` issue form. Include the original YouTube URL and
enough context to establish that Norm is central to the video. Maintainers add
suggestions to the candidate ledger before anything reaches production.

## Discovery pipeline

The production catalog and candidate queue are intentionally separate:

```text
targeted discovery -> candidate ledger -> editorial review -> runtime probe -> production
```

Run the configured discovery campaign:

```bash
python3 scripts/catalog_pipeline.py discover --workers 2
```

Discovery deduplicates by YouTube ID against both production and prior
candidates. Rejections remain in `catalog/candidates.json` as tombstones so the
same reaction, AI recreation, tribute, or duplicate is not repeatedly proposed.

Review decisions are auditable JSON files under `catalog/reviews/`:

```bash
python3 scripts/catalog_pipeline.py review \
  --decisions catalog/reviews/batch-001.json \
  --reviewer "Your name"
```

Only `accepted` candidates can be promoted. Promotion re-extracts metadata,
selects the exact combined format used by the plugin, and probes initial and
seeked byte ranges before changing production:

```bash
python3 scripts/catalog_pipeline.py promote --workers 2
```

Do not use `--allow-failures` for small release batches. It is intended for
large migrations where passing entries may ship while failures return to
pending review.

## Editorial policy

Accept material where Norm is the central performer, host, guest, or voice.
Prefer official rights-holder uploads, then established archives. Use ordinary
fan uploads when they preserve otherwise unavailable material.

Reject reactions, AI voice recreations, posthumous discussions without Norm,
misleading titles, low-context fragments, and redundant alternate uploads.
Retain both a complete appearance and a distinct official excerpt only when
they serve meaningfully different viewing modes.

## Health checks

Health checks never disable or delete production entries automatically:

```bash
python3 scripts/catalog_pipeline.py health --workers 2
```

Review repeated failures manually. A single timeout, regional error, or bot
check is not enough evidence to remove a link.

## Validation

```bash
python3 scripts/catalog_pipeline.py validate
bash tests/static.sh
```
