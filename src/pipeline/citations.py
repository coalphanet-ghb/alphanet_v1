"""
Run-scoped citation labels (2026-07-22).

An evidence UUID is the DB's identity for a passage and stays that way:
`claims.evidence_ids` is uuid[] and the schema is FROZEN (DB_SCHEMA.md
invariant #8). It is a terrible thing to put in front of a model or a
reader, though — 36 hex chars are unreadable in prose, and models
transpose their digits (~1 mangled citation per run; HANDOFF4 §6 watch
#3).

So every passage in a run's pool gets a short human-readable LABEL —
`AR.17`, `CC-May26.4`, `IP.9`, `CR.2`, `S-MARUTI` for the company
primaries, and a plain running `47` for the long tail of news / sector /
macro links. Nodes SEE and CITE labels; this module maps them back to
UUIDs before anything is persisted or verified. The UUID paths are kept
everywhere as a fallback (they still resolve) and can be deleted once
the label scheme is proven over a few runs.

The map is RUN-SCOPED by design: a label depends on the whole pool
(including the macro/industry rows rehydrated from storage), so it is
never stored per-document — that would go stale the moment the next run
pools a different set. The composer persists the run's map into
`report_versions.sections_json["citation_map"]`, which keeps a report
reconstructible and gives the future UI its footnote markers without
re-deriving anything.
"""

import re

# doc_class -> (mnemonic, sort priority). Classes NOT listed here are the
# numbered tail: news_batch, sector_page, industry_page, macro_page and
# anything new all get plain [1], [2], [3] ... in document order.
_NAMED = {
    "annual_report":         ("AR", 0),
    "investor_presentation": ("IP", 1),
    "concall":               ("CC", 2),
    "rating_rationale":      ("CR", 3),
    "screener_page":         ("S",  4),
}
_TAIL_PRIORITY = 9

# "Concall transcript (May 2026)" -> CC-May26
_MONTH_RE = re.compile(r"\(([A-Z][a-z]{2})[a-z]*\s+(\d{4})\)")
_MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
           "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
_SLUG_RE = re.compile(r"/company/([^/]+)", re.I)

# citation prefixes that are NOT evidence — they resolve against the
# calc / upstream-section / graph namespaces, not the label map
NON_EVIDENCE_PREFIXES = ("calc:", "sec:", "edge:", "trail:", "event:")


def _doc_mnemonic(doc_class: str, title: str, url: str) -> str | None:
    """The mnemonic for one document, before uniquification. None means
    this document belongs in the numbered tail."""
    named = _NAMED.get(doc_class)
    if not named:
        return None
    if doc_class == "concall":
        # the quarter belongs IN the label: two of M&M's verifier
        # verdicts were period mis-attributions between transcripts
        m = _MONTH_RE.search(title or "")
        return f"CC-{m.group(1)}{m.group(2)[2:]}" if m else "CC"
    if doc_class == "screener_page":
        slug = None
        if (title or "").lower().startswith("screener:"):
            slug = title.split(":", 1)[1]
        else:
            m = _SLUG_RE.search(url or "")
            slug = m.group(1) if m else None
        if slug:
            return "S-" + re.sub(r"[^A-Za-z0-9]+", "", slug).upper()[:12]
    return named[0]


def _recency(doc: dict) -> int:
    """Bigger = newer. Concalls sort newest-first so the K legend reads
    in the order an analyst thinks about them."""
    m = _MONTH_RE.search(doc.get("title") or "")
    if m:
        return int(m.group(2)) * 100 + _MONTHS.get(m.group(1), 0)
    d = str(doc.get("date") or "")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        return int(d[:4]) * 100 + int(d[5:7])
    return 0


def build_label_map(pool: list) -> tuple[dict, list]:
    """Stamp `label` on every pool row. Returns (label -> evidence uuid,
    ordered document index). Call ONCE, after the pool is final — the
    macro/industry rehydration appends rows, and stamping before it would
    leave those passages unlabelled and therefore uncitable."""
    docs: dict = {}
    for e in pool:
        key = (e.get("doc_class"), e.get("url"))
        d = docs.setdefault(key, {
            "doc_class": e.get("doc_class"), "title": e.get("title"),
            "url": e.get("url"), "date": e.get("date"), "rows": []})
        d["rows"].append(e)

    def _sort_key(d):
        named = _NAMED.get(d["doc_class"])
        prio = named[1] if named else _TAIL_PRIORITY
        return (prio, -_recency(d), str(d.get("url") or ""))

    by_label: dict = {}
    index: list = []
    used: set = set()
    tail_n = 0
    for d in sorted(docs.values(), key=_sort_key):
        base = _doc_mnemonic(d["doc_class"], d["title"], d["url"])
        if base:
            label = base
            if label in used:          # two ARs, two same-month calls
                i = 2
                while f"{base}{i}" in used:
                    i += 1
                label = f"{base}{i}"
            used.add(label)
            for n, e in enumerate(d["rows"], start=1):
                # a one-passage document needs no index (S-MARUTI, not
                # S-MARUTI.1)
                e["label"] = label if len(d["rows"]) == 1 else f"{label}.{n}"
                by_label[e["label"]] = e["id"]
        else:
            for e in d["rows"]:
                tail_n += 1
                e["label"] = str(tail_n)
                by_label[e["label"]] = e["id"]
        labels = [e["label"] for e in d["rows"]]
        index.append({"label": labels[0] if len(labels) == 1
                      else f"{labels[0]}–{labels[-1]}",
                      "doc_class": d["doc_class"], "title": d["title"],
                      "url": d["url"], "rows": len(labels)})
    return by_label, index


def to_uuid(cite, by_label: dict, pool_ids=None) -> str | None:
    """One citation -> the evidence uuid it names, or None. Accepts a
    label ("AR.17", "47"), an "evidence:"-prefixed label, and — as the
    retained fallback — a raw uuid that is present in the run's pool."""
    c = str(cite).strip().strip("[]")
    if c in by_label:
        return by_label[c]
    if c.startswith("evidence:"):
        body = c.split(":", 1)[1]
        if body in by_label:
            return by_label[body]
        c = body
    if pool_ids is not None and c in pool_ids:
        return c                       # legacy uuid citation
    return None


def is_evidence_shaped(cite) -> bool:
    """True when a citation was MEANT to name a passage — i.e. it is not
    one of the calc:/sec:/edge:/trail:/event: namespaces. Used to count
    genuine bad citations (an invented label) separately from claims that
    cited a computed value where the contract requires evidence."""
    c = str(cite).strip().strip("[]")
    return not c.startswith(NON_EVIDENCE_PREFIXES)
