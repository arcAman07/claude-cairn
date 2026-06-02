#!/usr/bin/env python3
"""Claude Cairn -- portable knowledge-continuity notes for Claude Code.

This is the *deterministic core* (stdlib only). It parses session transcripts,
redacts secrets, manages the note store, and powers list/find/show/load/rm.

The *judgment* -- distilling a transcript into a good note -- is NOT done here.
That is the LLM's job, driven by the command prompts in ../commands/. This CLI
gives the LLM a clean, redacted, distillation-ready `digest` and a `save` sink.

Important reality (verified against real transcripts): Claude Code does NOT
persist verbatim chain-of-thought to disk -- `thinking` blocks are always empty.
So the reasoning trace is reconstructed from assistant prose (`text` blocks),
the tool-action trail, tool results, and the human's instructions. All of this
survives in the JSONL even before compaction boundaries.
"""

import argparse
import glob
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone

SCHEMA_VERSION = 1
DEFAULT_BUDGET = 48000            # chars (~12k tokens) -- a digest's hard ceiling
# Per-block caps that bound the digest size (named, not magic numbers inline):
MAX_HUMAN_CHARS = 3000           # kept per human turn
MAX_CLAUDE_CHARS = 4000          # kept per assistant prose block
MAX_RESULT_CHARS = 200           # kept per tool result
MAX_TOOLREF_CHARS = 200          # kept per tool-use one-liner
PRE_BOUNDARY_TURNS = 12          # turns before a compaction marker to prioritise
FM_KEYS = ["id", "name", "created", "updated", "session_id", "cwd",
           "tags", "parent", "source", "summary", "last_timestamp",
           "scope", "pinned"]
SCOPE_CHOICES = ["full", "focused", "delta"]   # checkpoint breadth (see notes.md)

# --------------------------------------------------------------------------
# Store location
# --------------------------------------------------------------------------

def store_dir(args=None):
    """Resolve the cairn store: --store flag > CAIRN_HOME env > ~/.claude/cairn."""
    if args is not None and getattr(args, "store", None):
        return os.path.abspath(os.path.expanduser(args.store))
    env = os.environ.get("CAIRN_HOME")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.expanduser("~/.claude/cairn")


def notes_dir(store):
    return os.path.join(store, "notes")


def index_path(store):
    return os.path.join(store, "index.json")


def ensure_store(store):
    os.makedirs(notes_dir(store), exist_ok=True)
    return store


# --------------------------------------------------------------------------
# Time / slug helpers
# --------------------------------------------------------------------------

def now_iso():
    # millisecond precision matches real transcript timestamps (…265Z) and makes
    # same-second note ordering deterministic.
    dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (dt.microsecond // 1000)


def compact_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def slugify(name, maxlen=60):
    """Filesystem-safe slug. Unicode is transliterated to ascii; if nothing
    survives, fall back to a short hash so distinct names stay distinct."""
    if not name:
        return "note"
    n = unicodedata.normalize("NFKD", str(name))
    n = n.encode("ascii", "ignore").decode("ascii").lower()
    n = re.sub(r"[^a-z0-9]+", "-", n).strip("-")
    n = re.sub(r"-{2,}", "-", n)
    if len(n) > maxlen:
        n = n[:maxlen].rstrip("-")
    if not n:
        import hashlib
        n = "note-" + hashlib.sha1(str(name).encode("utf-8")).hexdigest()[:8]
    return n


def project_slug(path):
    """Derive the ~/.claude/projects/<slug> dir name from a cwd. NOTE: Claude
    Code truncates+hash-suffixes very long paths, so this is best-effort only;
    transcript resolution prefers globbing by session id."""
    return re.sub(r"[^A-Za-z0-9-]", "-", path)


# --------------------------------------------------------------------------
# Redaction (best-effort, conservative -- documented as shareable-with-review)
# --------------------------------------------------------------------------

# Order matters: most specific first so generic patterns don't pre-empt them.
_SECRET_PATTERNS = [
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}\b")),
    ("stripe_key",    re.compile(r"\b[rs]k_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("openai_key",    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}\b")),
    ("aws_key",       re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_pat",    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("github_token",  re.compile(r"\bgh[opsur]_[A-Za-z0-9]{20,}\b")),
    ("slack_token",   re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b")),
    ("google_key",    re.compile(r"\bAIza[0-9A-Za-z_\-]{35,}")),
    ("npm_token",     re.compile(r"\bnpm_[A-Za-z0-9]{30,}\b")),
    ("jwt",           re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b")),
    ("bearer",        re.compile(r"(?i)\b(?:bearer|authorization:\s*bearer)\s+[A-Za-z0-9._\-]{16,}")),
    ("basic_auth",    re.compile(r"(?i)\bauthorization:\s*basic\s+[A-Za-z0-9+/=]{8,}")),
    # gap bounded ({0,4096}) so unmatched BEGIN headers can't backtrack quadratically
    ("pem_key",       re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----[\s\S]{0,4096}?-----END (?:[A-Z ]+ )?PRIVATE KEY-----")),
]

# Password inside a connection string: scheme://user:PASSWORD@host. The scheme is
# length-bounded ({0,31}, RFC 3986 schemes are short) so a long dotted run with no
# "://" (stack traces, package names, minified JS) can't backtrack quadratically.
_URL_CRED = re.compile(r"(?i)\b([a-z][a-z0-9+.\-]{0,31}://[^\s:/@]+:)([^\s:/@]{3,})(@)")

# A `key = value` / `key: "value"` / JSON `"key": "value"` assignment. The key is
# a SHORT BOUNDED token with optional surrounding quotes (so JSON/quoted keys are
# caught too); the surroundings are preserved so prose isn't mangled. Whether the
# key names a secret is decided in the callback via _SECRET_KEY -- crucially NOT
# with nested quantifiers, which backtrack catastrophically (ReDoS) on word runs.
_ASSIGN = re.compile(
    r"""(?x)
    (["']?)                                   # 1: optional opening quote (JSON key)
    ([A-Za-z_][A-Za-z0-9_.\-]{0,39})          # 2: key (bounded -> no backtracking)
    (["']?)                                   # 3: optional closing quote (JSON key)
    ([ \t]*[:=][ \t]*)                        # 4: separator
    (?: "(?P<dq>[^"\n]{6,})"
      | '(?P<sq>[^'\n]{6,})'
      | (?P<uq>[^\s"'\#,;]{6,})
    )
    """
)
# The secret word must be a whole KEY COMPONENT (bounded by start/end or a
# _ . - separator), so "token" does NOT match inside "Tokenizer" and "secret"
# does NOT match inside "secretary", while "aws_secret_access_key" still does.
_SECRET_KEY = re.compile(
    r"(?i)(?:^|[_.\-])"
    r"(secret|password|passwd|pwd|api[_-]?key|access[_-]?key|"
    r"auth[_-]?token|client[_-]?secret|private[_-]?key|credential|token)"
    r"(?:$|[_.\-])")


def _looks_secret(v):
    """A value worth redacting LOOKS like a secret, not like prose. A real token
    has no spaces and some entropy; an English word/sentence is left alone (so we
    never destroy the reasoning prose this tool exists to store)."""
    if not v or " " in v:
        return False                     # multi-word => prose, not a secret
    if len(v) >= 20:
        return True                      # long opaque token
    if any(c.isdigit() for c in v):
        return True
    if any(c in "/+=" for c in v):
        return True
    if any(c.isupper() for c in v) and any(c.islower() for c in v):
        return True                      # mixed case
    return False                         # a plain lowercase word => leave it


def redact_text(s):
    if not s:
        return s
    for label, pat in _SECRET_PATTERNS:
        s = pat.sub("[REDACTED:%s]" % label, s)
    s = _URL_CRED.sub(r"\1[REDACTED:url_password]\3", s)

    def _assign(m):
        # the key must NAME a secret AND the value must LOOK like one
        if not _SECRET_KEY.search("_" + m.group(2) + "_"):
            return m.group(0)
        val = m.group("dq") or m.group("sq") or m.group("uq") or ""
        if "[REDACTED" in val or not _looks_secret(val):
            return m.group(0)
        vq = '"' if m.group("dq") else ("'" if m.group("sq") else "")
        return "%s%s%s%s%s[REDACTED:secret]%s" % (
            m.group(1), m.group(2), m.group(3), m.group(4), vq, vq)
    s = _ASSIGN.sub(_assign, s)
    return s


# --------------------------------------------------------------------------
# Transcript resolution (worktree-safe)
# --------------------------------------------------------------------------

def projects_root():
    return os.path.expanduser("~/.claude/projects")


def transcripts_for_cwd(cwd):
    """Every transcript whose first-line cwd == `cwd`, newest (by mtime) first.
    Many sessions can share a directory, so this can return several."""
    out = []
    for j in glob.glob(os.path.join(projects_root(), "*", "*.jsonl")):
        if os.path.isfile(j) and _first_cwd(j) == cwd:
            out.append(j)
    out.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return out


def resolve_transcript(transcript_path=None, session=None, cwd=None):
    """Return THIS session's real .jsonl path, or None. Strategy, in order:
      1. the given path, if it exists (the hook passes the authoritative path);
      2. by SESSION id -- the only reliable key when many sessions share a dir,
         because session ids are globally-unique UUIDs (one .jsonl). Defensively
         handles a multi-match by preferring the cwd-match, then newest;
      3. derive the slug from cwd + session id;
      4. cwd only (no session) -- newest cwd-matching transcript, with a warning
         that it is ambiguous. Callers that know the session id should ALWAYS
         pass it (the checkpoint command uses $CLAUDE_CODE_SESSION_ID)."""
    if transcript_path and os.path.isfile(transcript_path):
        return transcript_path

    if not session and transcript_path:
        base = os.path.basename(transcript_path)
        if base.endswith(".jsonl"):
            session = base[:-len(".jsonl")]

    root = projects_root()
    if session:
        hits = [h for h in glob.glob(os.path.join(root, "*", session + ".jsonl"))
                if os.path.isfile(h)]
        if len(hits) > 1 and cwd:                 # defensive: same id, two dirs
            cwd_hits = [h for h in hits if _first_cwd(h) == cwd]
            if cwd_hits:
                hits = cwd_hits
        if hits:
            hits.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            return hits[0]
        if cwd:
            cand = os.path.join(root, project_slug(cwd), session + ".jsonl")
            if os.path.isfile(cand):
                return cand
        return None       # a session id was given but no such transcript exists

    if cwd:
        matches = transcripts_for_cwd(cwd)
        if len(matches) > 1:
            sys.stderr.write(
                "cairn: %d transcripts share cwd %s; using the most recent. "
                "Pass --session $CLAUDE_CODE_SESSION_ID to target this session "
                "exactly (see `resolve --list`).\n" % (len(matches), cwd))
        if matches:
            return matches[0]
    return None


def _first_cwd(jsonl):
    try:
        with open(jsonl, "r", errors="replace") as f:
            for line in f:
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if isinstance(o, dict) and o.get("cwd"):
                    return o["cwd"]
    except OSError:
        return None
    return None


# --------------------------------------------------------------------------
# Transcript walking -> normalized reasoning-trace events (streaming)
# --------------------------------------------------------------------------

def iter_jsonl(path):
    with open(path, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


_WRAP_RE = [
    re.compile(r"<system-reminder>.*?</system-reminder>", re.S),
    re.compile(r"<local-command-stdout>.*?</local-command-stdout>", re.S),
    re.compile(r"<command-(name|message|args)>.*?</command-\1>", re.S),
    re.compile(r"</?(local-command-caveat|command-[a-z]+)>"),
]


def clean_human(s):
    for pat in _WRAP_RE:
        s = pat.sub("", s)
    return s.strip()


def _tool_files(inp):
    out = []
    if isinstance(inp, dict):
        for k in ("file_path", "path", "notebook_path"):
            v = inp.get(k)
            if isinstance(v, str) and v:
                out.append(v)
    return out


def tool_ref(name, inp):
    inp = inp or {}
    for k in ("file_path", "path", "notebook_path", "command", "pattern",
              "query", "url", "subagent_type", "prompt", "description"):
        v = inp.get(k) if isinstance(inp, dict) else None
        if isinstance(v, str) and v.strip():
            v = redact_text(re.sub(r"\s+", " ", v).strip())
            return "%s=%s" % (k, v[:MAX_TOOLREF_CHARS])
    try:
        return redact_text(json.dumps(inp))[:MAX_TOOLREF_CHARS]
    except Exception:
        return str(inp)[:MAX_TOOLREF_CHARS]


def _result_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if not isinstance(b, dict):
                continue
            t = b.get("type")
            if t == "text":
                parts.append(b.get("text") or "")
            elif t == "image":
                parts.append("[image]")
            elif t == "tool_reference":
                parts.append("[tool_reference %s]" % b.get("tool_name"))
            else:
                parts.append("[%s]" % t)
        return " ".join(p for p in parts if p)
    return ""


def walk_events(path, since=None):
    """Yield ordered events: human / claude / tool / result / compaction."""
    for o in iter_jsonl(path):
        if not isinstance(o, dict):
            continue
        if o.get("isSidechain"):
            continue
        ts = o.get("timestamp")
        if since and ts and ts <= since:
            continue
        t = o.get("type")
        if t == "system" and o.get("subtype") == "compact_boundary":
            cm = o.get("compactMetadata") or {}
            yield {"kind": "compaction", "ts": ts, "trigger": cm.get("trigger"),
                   "pre": cm.get("preTokens"), "post": cm.get("postTokens")}
            continue
        if t == "user":
            if o.get("isMeta"):
                continue
            msg = o.get("message") or {}
            c = msg.get("content")
            if isinstance(c, str):
                txt = clean_human(c)
                if txt:
                    yield {"kind": "human", "ts": ts, "text": txt}
            elif isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        yield {"kind": "result", "ts": ts,
                               "is_error": bool(b.get("is_error")),
                               "text": _result_text(b.get("content"))}
        elif t == "assistant":
            msg = o.get("message") or {}
            model = msg.get("model")
            for b in (msg.get("content") or []):
                if not isinstance(b, dict):
                    continue
                bt = b.get("type")
                if bt == "text":
                    tx = (b.get("text") or "").strip()
                    if tx:
                        yield {"kind": "claude", "ts": ts, "text": tx, "model": model}
                elif bt == "tool_use":
                    yield {"kind": "tool", "ts": ts, "name": b.get("name"),
                           "ref": tool_ref(b.get("name"), b.get("input")),
                           "files": _tool_files(b.get("input"))}
                # thinking blocks are empty on disk -> intentionally ignored


def collect(path, since=None):
    """Single pass -> (events, metadata, file_index)."""
    events = []
    files = []
    seen_files = set()
    models = set()
    first_ts = last_ts = None
    n_compact = 0
    for ev in walk_events(path, since=since):
        events.append(ev)
        ts = ev.get("ts")
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        if ev["kind"] == "claude" and ev.get("model"):
            models.add(ev["model"])
        if ev["kind"] == "compaction":
            n_compact += 1
        for fp in ev.get("files", []) or []:
            if fp not in seen_files:
                seen_files.add(fp)
                files.append(fp)
    counts = {}
    for ev in events:
        counts[ev["kind"]] = counts.get(ev["kind"], 0) + 1
    meta = {"models": sorted(models), "first_ts": first_ts, "last_ts": last_ts,
            "compactions": n_compact, "counts": counts}
    return events, meta, files


# --------------------------------------------------------------------------
# Digest (distillation-ready) with priority budgeting
# --------------------------------------------------------------------------

def _trunc(s, n, marker="…[truncated]"):
    s = s or ""
    return s if len(s) <= n else s[:n] + marker


def _render_event(ev, idx, pre_boundary):
    """Return (priority, text). Lower priority = keep harder.
       0 keep always · 1 pre-boundary survival · 2 tool/error · 3 plain result."""
    # Redact BEFORE truncating so a secret can't survive as a fragment whose
    # length anchor was cut off (the whole digest is redacted again at the end).
    k = ev["kind"]
    if k == "human":
        return 0, "\n[HUMAN] %s\n" % _trunc(redact_text(ev["text"]), MAX_HUMAN_CHARS)
    if k == "claude":
        return 0, "[CLAUDE] %s\n" % _trunc(redact_text(ev["text"]), MAX_CLAUDE_CHARS)
    if k == "compaction":
        return 0, ("\n--- COMPACTION (%s, %s->%s tokens): earlier context above "
                   "was dropped from the live window but is preserved here ---\n"
                   % (ev.get("trigger"), ev.get("pre"), ev.get("post")))
    if k == "tool":
        p = 1 if idx in pre_boundary else 2
        return p, "  · %s: %s\n" % (ev.get("name"), ev.get("ref"))
    if k == "result":
        txt = redact_text(ev["text"]).replace("\n", " ")
        if ev.get("is_error"):
            return 2, "    -> ERROR: %s\n" % _trunc(txt, MAX_RESULT_CHARS)
        return 3, "    -> %s\n" % _trunc(txt, MAX_RESULT_CHARS - 40)
    return 3, ""


def build_digest(path, session=None, cwd=None, since=None, budget=DEFAULT_BUDGET):
    events, meta, files = collect(path, since=since)

    # indices that sit just before a compaction get a survival boost
    pre_boundary = set()
    for i, ev in enumerate(events):
        if ev["kind"] == "compaction":
            for j in range(max(0, i - PRE_BOUNDARY_TURNS), i):
                pre_boundary.add(j)

    segs = []
    for i, ev in enumerate(events):
        prio, txt = _render_event(ev, i, pre_boundary)
        if txt:
            segs.append({"i": i, "prio": prio, "text": txt, "kind": ev["kind"],
                         "comp": ev["kind"] == "compaction", "pre": i in pre_boundary})

    # Bounded file-reference block (the pointer list) -- reserve room for it.
    file_cap = min(8000, max(500, budget // 5))   # proportional, so tiny budgets
    #                                                still keep (a few) pointers
    file_lines = ["", "## File & area references (from tool actions)"]
    flen, nfiles = 0, 0
    for f in files:
        line = "- %s" % f
        if flen + len(line) + 1 > file_cap:
            break
        file_lines.append(line)
        flen += len(line) + 1
        nfiles += 1
    if not files:
        file_lines.append("- (none)")
    elif nfiles < len(files):
        file_lines.append("- … %d more reference(s) omitted" % (len(files) - nfiles))
    file_block = "\n".join(file_lines)

    # Build the header now (minus the budget note) so we can CHARGE it to the
    # budget instead of guessing a constant. The budget note is added later.
    head_static = [
        "# Cairn digest",
        "# session: %s" % (session or "?"),
        "# cwd: %s" % (cwd or _first_cwd(path) or "?"),
        "# models: %s" % (", ".join(meta["models"]) or "?"),
        "# time: %s .. %s" % (meta["first_ts"], meta["last_ts"]),
        "# compactions: %d   events: %s" % (meta["compactions"], meta["counts"]),
        "# file references: %d" % len(files),
    ]
    head_tail = [
        "# NOTE: verbatim chain-of-thought is NOT stored by Claude Code; this",
        "#       trace is reconstructed from assistant prose, tool actions,",
        "#       results, and human instructions.",
        "",
        "## Reasoning trace (chronological)",
    ]
    header_len = len("\n".join(head_static + head_tail)) + 200   # +200 budget note
    # Reserve room for header + the (high-value) pointer block within the budget;
    # do NOT floor above the budget itself, or the final out[:budget] would cut the
    # pointer block (appended last). Floor at 0 so the body simply yields the room.
    text_budget = max(0, budget - len(file_block) - header_len)

    def total(items):
        return sum(len(s["text"]) for s in items)

    # Step 1: shed tool/result noise (priority 3 -> 2 -> 1) to fit.
    kept = segs
    dropped = {}
    for cutoff in (3, 2, 1):
        if total(kept) <= text_budget:
            break
        n = sum(1 for s in kept if s["prio"] >= cutoff)
        if n:
            dropped[cutoff] = n
        kept = [s for s in kept if s["prio"] < cutoff]

    # Step 2: if prose+markers still overflow, keep compaction markers (CAPPED
    # to a fraction of the budget, newest first -- they are otherwise unbounded),
    # then pre-boundary context, then most-recent turns.
    omitted_mid = dropped_markers = 0
    if total(kept) > text_budget:
        marker_cap = max(2000, text_budget // 3)
        marker_segs = [s for s in kept if s["comp"]]
        keep_markers, mu = set(), 0
        for s in reversed(marker_segs):          # newest markers first
            if mu + len(s["text"]) <= marker_cap:
                keep_markers.add(s["i"])
                mu += len(s["text"])
        dropped_markers = len(marker_segs) - len(keep_markers)

        keepset, used = set(), 0
        for s in kept:                           # capped markers
            if s["comp"] and s["i"] in keep_markers:
                keepset.add(s["i"])
                used += len(s["text"])
        for s in kept:                           # pre-boundary survival region
            if s["i"] not in keepset and s["pre"] and used + len(s["text"]) <= text_budget:
                keepset.add(s["i"])
                used += len(s["text"])
        for s in reversed(kept):                 # recency
            if s["i"] not in keepset and used + len(s["text"]) <= text_budget:
                keepset.add(s["i"])
                used += len(s["text"])
        final, skipped = [], 0
        for s in kept:
            if s["i"] in keepset:
                if skipped:
                    final.append({"text": "\n[… %d earlier turn(s) omitted to fit "
                                          "budget …]\n" % skipped})
                    omitted_mid += skipped
                    skipped = 0
                final.append(s)
            elif s["kind"] in ("human", "claude", "compaction"):
                skipped += 1
        if skipped:
            final.append({"text": "\n[… %d earlier turn(s) omitted …]\n" % skipped})
            omitted_mid += skipped
        kept = final

    body = "".join(s["text"] for s in kept)
    # Hard guarantee: omission markers between scattered kept segments can nudge
    # us over -- drop from the front (oldest) until the body fits the budget.
    while len(body) > text_budget and len(kept) > 1:
        kept.pop(0)
        body = "".join(s["text"] for s in kept)

    notes = []
    for cut, n in sorted(dropped.items()):
        names = {3: "non-error tool results", 2: "tool actions/errors",
                 1: "pre-boundary detail"}[cut]
        notes.append("%d %s omitted" % (n, names))
    if dropped_markers:
        notes.append("%d older compaction markers omitted" % dropped_markers)
    if omitted_mid:
        notes.append("%d older turns omitted (recent kept)" % omitted_mid)

    head_lines = list(head_static)
    if notes:
        head_lines.append("# budget: " + "; ".join(notes))
    head_lines += head_tail
    out = redact_text("\n".join(head_lines) + "\n" + body + "\n" + file_block + "\n")
    if len(out) > budget:        # hard ceiling: honour the caller's budget exactly
        out = out[:max(0, budget)]   # max(0,..) so a negative budget can't slice from the end
    return out


# --------------------------------------------------------------------------
# Mechanical extraction (for the PreCompact hook -- no LLM available)
# --------------------------------------------------------------------------

def build_extract(path, session=None, cwd=None, since=None, budget=DEFAULT_BUDGET):
    events, meta, files = collect(path, since=since)
    claude_txt = [e["text"] for e in events if e["kind"] == "claude"]
    humans = [e["text"] for e in events if e["kind"] == "human"]
    c = meta["counts"]
    span = "%s .. %s" % (meta["first_ts"], meta["last_ts"])

    last_step = _trunc(claude_txt[-1], 400) if claude_txt else "(none captured)"
    summary = ("Auto-captured at compaction. %d human turn(s), %d assistant "
               "message(s), %d tool action(s), %d compaction(s) over %s."
               % (c.get("human", 0), c.get("claude", 0), c.get("tool", 0),
                  meta["compactions"], span))

    lines = []
    lines.append("> **Auto-captured at compaction — raw, un-distilled.** "
                 "Run `/cairn:checkpoint update <name>` (or `/checkpoint update`) "
                 "to distill this into a clean note. A full digest is staged "
                 "alongside this file as `<name>.pending-digest.txt`.")
    lines.append("")
    lines.append("## Summary")
    lines.append(summary)
    lines.append("")
    # NOT "## Directions explored" -- this is raw narration, not identified
    # rejected paths. Reusing that header would put anti-signal in the section
    # the whole product trains readers to trust. Distillation fills it later.
    lines.append("## Raw narration (undistilled — distill with `update`)")
    lines.append("_Assistant narration, latest first-lines. Rejected directions "
                 "are NOT yet identified — do not read this as 'Directions explored'._")
    for t in reversed(claude_txt[-12:]):
        first = t.strip().splitlines()[0] if t.strip() else ""
        if first:
            lines.append("- " + _trunc(first, 240))
    lines.append("")
    lines.append("## Directions explored")
    lines.append("_(not distilled yet — run `update` to identify explored & "
                 "rejected paths from the staged digest)_")
    lines.append("")
    lines.append("## Decisions")
    lines.append("_(not distilled)_")
    lines.append("")
    lines.append("## Open questions / assumptions")
    lines.append("_(not distilled)_")
    lines.append("")
    lines.append("## Files & areas to look at")
    if files:
        for f in files[:100]:
            lines.append("- " + f)
    else:
        lines.append("- (none captured)")
    lines.append("")
    lines.append("## Next step")
    lines.append(last_step)
    lines.append("")
    if humans:
        lines.append("## Original ask (first human turn)")
        lines.append("> " + _trunc(humans[0].replace("\n", "\n> "), 1200))
        lines.append("")

    body = redact_text("\n".join(lines))
    return body, summary


# --------------------------------------------------------------------------
# Note files + index
# --------------------------------------------------------------------------

def write_frontmatter(meta):
    out = ["---"]
    for k in FM_KEYS:
        if k in meta:
            out.append("%s: %s" % (k, json.dumps(meta[k], ensure_ascii=False)))
    out.append("---")
    return "\n".join(out)


_FM_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def parse_note(path):
    with open(path, "r", errors="replace") as f:
        text = f.read()
    meta, body = {}, text
    m = _FM_RE.match(text)
    if m:
        fm, body = m.group(1), m.group(2)
        for line in fm.splitlines():
            if not line.strip() or ":" not in line:
                continue
            k, _, v = line.partition(":")
            k, v = k.strip(), v.strip()
            try:
                meta[k] = json.loads(v)
            except Exception:
                meta[k] = v.strip().strip('"')
    # Coerce types so a hand-edited note can't corrupt list/find/export output.
    if "tags" in meta:
        t = meta["tags"]
        t = t if isinstance(t, list) else ([t] if t else [])
        meta["tags"] = [str(x) for x in t]   # elements too (e.g. a numeric tag)
    # String-typed scalars must be strings: a numeric `created: 20260601` etc.
    # would otherwise crash date slicing / sorting in list/find.
    for k in ("id", "name", "created", "updated", "last_timestamp",
              "session_id", "cwd", "summary", "source", "scope"):
        if k in meta and meta[k] is not None and not isinstance(meta[k], str):
            meta[k] = str(meta[k])
    # `pinned` is a bool; a hand-edited "true"/"1"/"yes" must not read as truthy-string.
    if "pinned" in meta and not isinstance(meta["pinned"], bool):
        v = meta["pinned"]
        meta["pinned"] = str(v).strip().lower() in ("true", "1", "yes", "on")
    return meta, body


def _claim_note_file(store, base):
    """Atomically reserve a unique <base>.md (race-safe across concurrent
    sessions/hooks) via O_CREAT|O_EXCL, bumping a suffix on collision.
    Returns (note_id, path)."""
    nd = notes_dir(store)
    os.makedirs(nd, exist_ok=True)
    for attempt in range(10000):
        cand = base if attempt == 0 else "%s-%d" % (base, attempt + 1)
        path = os.path.join(nd, cand + ".md")
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.close(fd)
            return cand, path
        except FileExistsError:
            continue
    import binascii
    cand = "%s-%s" % (base, binascii.hexlify(os.urandom(3)).decode())
    return cand, os.path.join(nd, cand + ".md")


def atomic_write(path, data):
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class FileLock:
    """Advisory lock via O_CREAT|O_EXCL. Best-effort: steals stale locks and,
    if it cannot acquire within `timeout`, proceeds anyway (never deadlocks a
    session). `acquired` reports whether the lock was actually held."""

    def __init__(self, path, timeout=5.0, stale=30.0):
        self.path, self.timeout, self.stale = path, timeout, stale
        self.fd = None
        self.acquired = False

    def __enter__(self):
        start = time.time()
        while True:
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(self.fd, str(os.getpid()).encode())
                except OSError:
                    pass                 # pid is informational; never fail on it
                self.acquired = True
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.path) > self.stale:
                        os.unlink(self.path)
                        continue
                except FileNotFoundError:
                    continue
                if time.time() - start > self.timeout:
                    return self  # proceed without the lock
                time.sleep(0.05)

    def __exit__(self, *a):
        if self.fd is None:
            return
        try:
            # Only remove the lock file if it is still OURS. If another process
            # stale-stole our lock and created its own, the file at self.path now
            # has a different inode -- deleting it would free a successor's lock
            # and break mutual exclusion.
            if self.acquired:
                try:
                    if os.fstat(self.fd).st_ino == os.stat(self.path).st_ino:
                        os.unlink(self.path)
                except (FileNotFoundError, OSError):
                    pass
        finally:
            try:
                os.close(self.fd)
            except Exception:
                pass


def index_entry_from_meta(meta, fname):
    e = {k: meta.get(k) for k in
         ("id", "name", "created", "updated", "session_id", "cwd", "tags",
          "parent", "source", "summary", "last_timestamp", "scope", "pinned")}
    e["file"] = fname
    return e


def reindex_build(store):
    """Rebuild the index dict from note frontmatter. Pure -- does NOT write, so
    it is safe to call from inside a held index lock (e.g. via read_index)."""
    notes = []
    for p in sorted(glob.glob(os.path.join(notes_dir(store), "*.md"))):
        try:
            meta, _ = parse_note(p)
        except Exception:
            continue
        if meta.get("id"):
            notes.append(index_entry_from_meta(meta, os.path.basename(p)))
    return {"schema_version": SCHEMA_VERSION, "notes": notes}


def reindex(store):
    """Rebuild AND persist the index, under the lock (clobber-safe)."""
    idx = reindex_build(store)
    os.makedirs(store, exist_ok=True)
    with FileLock(index_path(store) + ".lock"):
        try:
            atomic_write(index_path(store), json.dumps(idx, indent=2, ensure_ascii=False))
        except OSError:
            pass
    return idx


def read_index(store, auto=True):
    # On missing/corrupt/version-mismatch, return a freshly BUILT index without
    # writing it (the next mutate_index/reindex persists it under the lock). This
    # avoids both a lock re-entry when called inside mutate_index and an unlocked
    # write that could clobber a concurrent locked update.
    try:
        with open(index_path(store)) as f:
            idx = json.load(f)
        if (not isinstance(idx, dict) or "notes" not in idx
                or not isinstance(idx["notes"], list)
                or idx.get("schema_version") != SCHEMA_VERSION):
            raise ValueError("bad index")
        return idx
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError):
        return reindex_build(store) if auto else {"schema_version": SCHEMA_VERSION, "notes": []}


def mutate_index(store, fn, best_effort=False):
    """Read-modify-write the index INSIDE the lock so a concurrent writer can't
    clobber a sibling's change (the read happens under the lock, not before it).
    `fn(idx)` mutates idx in place. Returns True on write, False if skipped."""
    os.makedirs(store, exist_ok=True)
    lock = FileLock(index_path(store) + ".lock")
    with lock:
        if best_effort and not lock.acquired:
            return False
        idx = read_index(store)
        fn(idx)
        atomic_write(index_path(store), json.dumps(idx, indent=2, ensure_ascii=False))
        return True


def upsert_index(store, meta, fname, best_effort=False):
    entry = index_entry_from_meta(meta, fname)

    def _mut(idx):
        idx["notes"] = [n for n in idx["notes"] if n.get("id") != meta["id"]]
        idx["notes"].append(entry)
    return mutate_index(store, _mut, best_effort=best_effort)


# --------------------------------------------------------------------------
# Note resolution + summary extraction
# --------------------------------------------------------------------------

def resolve_notes(store, query):
    """Return list of index entries matching `query`, best match first.
       Matches: exact id > exact name (ci) > substring of name/id."""
    idx = read_index(store)
    notes = idx["notes"]
    q = (query or "").strip()
    if not q:
        return []                 # an empty/blank query must NOT match the sole note
    ql = q.lower()
    exact_id = [n for n in notes if n.get("id") == q]
    if exact_id:
        return exact_id
    exact_name = [n for n in notes if (n.get("name") or "").lower() == ql]
    if exact_name:
        return _by_recency(exact_name)
    subs = [n for n in notes
            if ql in (n.get("name") or "").lower() or ql in (n.get("id") or "").lower()]
    return _by_recency(subs)


def _by_recency(notes):
    return sorted(notes, key=lambda n: str(n.get("updated") or n.get("created") or ""),
                  reverse=True)


def _by_pinned_recency(notes):
    """Pinned notes first, each group newest-first. Deterministic + stable."""
    return sorted(notes, key=lambda n: (1 if n.get("pinned") else 0,
                                        str(n.get("updated") or n.get("created") or "")),
                  reverse=True)


def _print_note_line(n):
    """One note's three-line block for `list` / `recent`. A note with no scope
    or pin renders exactly as it did in v1 (the markers only appear when set)."""
    tags = " ".join("#" + t for t in _safe_tags(n))
    src = " (auto)" if n.get("source") == "auto" else ""
    pin = "📌 " if n.get("pinned") else ""
    scope = " {%s}" % n.get("scope") if n.get("scope") else ""
    print("• %s%s%s   [%s]%s  %s"
          % (pin, n.get("name"), src, _fmt_date(n.get("updated")), scope, tags))
    print("    %s" % (n.get("summary") or ""))
    print("    id: %s" % n.get("id"))


def extract_summary(body):
    """One-line summary: the first paragraph of the Summary section, with
    hard-wrapped lines joined, cut at a sentence boundary near 240 chars."""
    m = re.search(r"(?im)^##\s*Summary\s*\n(.+?)(?=\n##\s|\Z)", body, re.S)
    para = m.group(1).strip() if m else body.strip()
    block = []
    for line in para.splitlines():
        s = line.strip()
        if not s:
            if block:
                break
            continue
        if s.startswith("_("):
            continue
        s = re.sub(r"^[-*>]\s+", "", s)        # a bullet/quote marker, not **bold**
        block.append(s.strip())
    text = re.sub(r"\s+", " ", " ".join(block)).strip()
    text = re.sub(r"^\*\*[^*\n]{1,40}\*\*\s*:?\s*", "", text).strip()  # drop **Now:** label
    if len(text) <= 240:
        return text
    cut = text[:240]
    dot = cut.rfind(". ")
    return cut[:dot + 1] if dot >= 120 else cut.rstrip() + "…"


# --------------------------------------------------------------------------
# Section helpers (for merge / diff) + edit-target resolution
# --------------------------------------------------------------------------

# Section parsing for merge/diff. These are FENCE-AWARE: a '## ...' line inside a
# ``` or ~~~ code block is NOT treated as a section header (a note may embed a
# code snippet), and ALL occurrences of a repeated header are handled, not just
# the first. A header must be '## ' + space (standard markdown) so the three
# helpers below agree on what a header is.
_FENCE_RE = re.compile(r"^(```+|~~~+)")
_H2_RE = re.compile(r"^##\s+(.+?)\s*$")


def _split_sections(body):
    """Parse a note body into [(title, header_line, content_lines)] split at
    level-2 ('## ') headers, ignoring headers inside fenced code blocks. The
    pre-first-header chunk has title=None, header_line=None."""
    out = [(None, None, [])]
    fence = None
    for line in (body or "").splitlines():
        s = line.lstrip()
        fm = _FENCE_RE.match(s)
        if fm:
            tok = fm.group(1)
            if fence and s.startswith(fence):
                fence = None                  # closing fence
            elif not fence:
                fence = tok                   # opening fence
            out[-1][2].append(line)
            continue
        if fence is None:
            hm = _H2_RE.match(line)
            if hm:
                out.append((hm.group(1).strip(), line, []))
                continue
        out[-1][2].append(line)
    return out


def _section_headers(body):
    """Set of level-2 section titles (outside code fences)."""
    return set(t for t, _, _ in _split_sections(body) if t)


def _section_lines(body, header):
    """Non-empty content lines under EVERY '## <header>' section (case-insensitive)."""
    h = header.lower()
    lines = []
    for t, _, content in _split_sections(body):
        if t and t.lower() == h:
            lines.extend(ln for ln in content if ln.strip())
    return lines


def _strip_section(body, header):
    """`body` with every '## <header>' section removed (for merge folding)."""
    h = header.lower()
    keep = []
    for t, hl, content in _split_sections(body):
        if t and t.lower() == h:
            continue
        if hl is not None:
            keep.append(hl)
        keep.extend(content)
    return "\n".join(keep).strip()


def _demote_headers(body):
    """Add one '#' to each markdown header (## -> ###) so a source note's sections
    sit cleanly UNDER a merged note's '## From ...' wrapper. Fence-aware: a '#'
    that begins a line INSIDE a code block (a comment) is left untouched."""
    out, fence = [], None
    for line in (body or "").splitlines():
        s = line.lstrip()
        fm = _FENCE_RE.match(s)
        if fm:
            tok = fm.group(1)
            if fence and s.startswith(fence):
                fence = None
            elif not fence:
                fence = tok
            out.append(line)
            continue
        if fence is None:
            line = re.sub(r"^(#+)(\s)", lambda m: "#" + m.group(1) + m.group(2), line)
        out.append(line)
    return "\n".join(out)


def _resolve_for_edit(store, query, action, note_id=None):
    """Resolve exactly one note for an in-place edit, honoring --id to pick among
    same-named notes. Returns (note, err) like `_resolve_one` but never guesses."""
    matches = resolve_notes(store, query)
    if not matches:
        return None, "No note matches %r." % query
    if note_id:
        target = next((m for m in matches if m.get("id") == note_id), None)
        if target is None:
            return None, "No note named %r has id %r." % (query, note_id)
        matches = [target]
    if len(matches) > 1:
        msg = ["%r matches %d notes; pass --id to choose (%s):"
               % (query, len(matches), action)]
        for m in matches[:10]:
            msg.append("  %s  (%s)" % (m["id"], m["name"]))
        return None, "\n".join(msg)
    note = matches[0]
    if not os.path.isfile(os.path.join(notes_dir(store), note.get("file") or "")):
        return None, ("Note %r is in the index but its file is missing "
                      "(run `cairn reindex`)." % note.get("name"))
    return note, None


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def save_note(store, name, body, session="unknown", cwd=None, tags=None,
              parent=None, source="manual", summary=None, last_timestamp=None,
              created=None, scope=None, pinned=False, best_effort=False):
    """Core new-note writer shared by `cmd_save` and the PreCompact hook.
    Returns (note_id, path, index_ok)."""
    store = ensure_store(store)
    body = body.strip() + "\n"
    tags = tags or []
    ts = now_iso()
    session = session or "unknown"
    short = (session.split("-")[0] if session and session != "unknown" else "nosess")[:8]
    base = "%s--%s--%s" % (slugify(name), compact_stamp(), short)
    note_id, path = _claim_note_file(store, base)
    meta = {
        "id": note_id, "name": name, "created": created or ts,
        "updated": created or ts, "session_id": session,
        "cwd": cwd or os.getcwd(), "tags": tags, "parent": parent,
        "source": source, "summary": summary or extract_summary(body),
        "last_timestamp": last_timestamp or (created or ts),
    }
    # Only persist the new fields when set, so a v1-shaped note (no scope/pin)
    # stays byte-identical and old readers see exactly what they did before.
    if scope:
        meta["scope"] = scope
    if pinned:
        meta["pinned"] = True
    atomic_write(path, write_frontmatter(meta) + "\n\n" + body)
    ok = upsert_index(store, meta, note_id + ".md", best_effort=best_effort)
    return note_id, path, ok


def roll_auto_note(store, session, name, body, summary, cwd, tags=None):
    """Create-or-refresh THE single rolling auto-note for `session`, atomically
    under the index lock (the PreCompact hook's writer). Robust to a stale (file
    deleted), corrupt, or id-less existing entry -- it falls through to creating
    a fresh note and prunes other auto entries for this session so exactly one
    survives. Holding the lock across find+create+index-write closes the
    duplicate-on-contention and concurrent-first-fire races. Returns the path."""
    store = ensure_store(store)
    body = body.strip() + "\n"
    tags = tags or ["auto", "precompact"]
    ts = now_iso()
    with FileLock(index_path(store) + ".lock"):
        idx = read_index(store)
        meta = path = fname = None
        for n in idx["notes"]:
            if n.get("session_id") == session and n.get("source") == "auto":
                p = os.path.join(notes_dir(store), n.get("file") or "")
                if os.path.isfile(p):
                    try:
                        m, _ = parse_note(p)
                    except Exception:
                        m = {}
                    if m.get("id"):
                        m["updated"] = ts
                        m["summary"] = summary
                        atomic_write(p, write_frontmatter(m) + "\n\n" + body)
                        meta, path, fname = m, p, os.path.basename(p)
                        break
                # stale/corrupt/id-less -> ignore and create a fresh one
        if meta is None:
            short = (session.split("-")[0] if session and session != "unknown"
                     else "nosess")[:8]
            note_id, path = _claim_note_file(store, "%s--%s--%s"
                                             % (slugify(name), compact_stamp(), short))
            fname = note_id + ".md"
            meta = {"id": note_id, "name": name, "created": ts, "updated": ts,
                    "session_id": session, "cwd": cwd or os.getcwd(), "tags": tags,
                    "parent": None, "source": "auto", "summary": summary,
                    "last_timestamp": ts}
            atomic_write(path, write_frontmatter(meta) + "\n\n" + body)
        # keep exactly one auto note per session: drop other auto entries + our own
        idx["notes"] = [x for x in idx["notes"] if x.get("id") != meta["id"]
                        and not (x.get("session_id") == session
                                 and x.get("source") == "auto")]
        idx["notes"].append(index_entry_from_meta(meta, fname))
        try:
            atomic_write(index_path(store),
                         json.dumps(idx, indent=2, ensure_ascii=False))
        except OSError:
            pass
        return path


def cmd_resolve(args):
    if getattr(args, "list", False):
        cwd = args.cwd or os.getcwd()
        cands = transcripts_for_cwd(cwd)
        if not cands:
            print("No transcripts for cwd %s" % cwd)
            return 0
        print("%d transcript(s) for cwd %s (newest first):" % (len(cands), cwd))
        for p in cands:
            sid = os.path.splitext(os.path.basename(p))[0]
            print("  %s  %s" % (sid, p))
        return 0
    p = resolve_transcript(args.transcript, session=args.session, cwd=args.cwd)
    if not p:
        sys.stderr.write("cairn: could not resolve a transcript\n")
        return 1
    print(p)
    return 0


def cmd_digest(args):
    p = resolve_transcript(args.transcript, session=args.session, cwd=args.cwd)
    if not p:
        sys.stderr.write("cairn: transcript not found: %s\n" % args.transcript)
        return 1
    session = args.session or os.path.splitext(os.path.basename(p))[0]
    cwd = args.cwd or _first_cwd(p)
    sys.stdout.write(build_digest(p, session=session, cwd=cwd,
                                  since=args.since, budget=args.budget))
    return 0


def cmd_extract(args):
    p = resolve_transcript(args.transcript, session=args.session, cwd=args.cwd)
    if not p:
        sys.stderr.write("cairn: transcript not found\n")
        return 1
    body, _ = build_extract(p, session=args.session or os.path.splitext(os.path.basename(p))[0],
                            cwd=args.cwd or _first_cwd(p), since=args.since,
                            budget=args.budget)
    sys.stdout.write(body)
    return 0


def _read_body(args):
    if getattr(args, "body_file", None):
        with open(args.body_file, "r", errors="replace") as f:
            return f.read()
    return sys.stdin.read()


def cmd_save(args):
    store = ensure_store(store_dir(args))
    body = _read_body(args).strip() + "\n"
    tags = _parse_tags(args.tags)
    ts = now_iso()

    if args.update:
        matches = resolve_notes(store, args.name)
        if not matches:
            sys.stderr.write("cairn: no note matches %r to update\n" % args.name)
            return 1
        if len(matches) > 1 and not args.id:
            sys.stderr.write("cairn: %r is ambiguous; pass --id. candidates:\n" % args.name)
            for m in matches:
                sys.stderr.write("  %s  (%s)\n" % (m["id"], m["name"]))
            return 2
        if args.id:
            target = next((m for m in matches if m.get("id") == args.id), None)
            if target is None:
                sys.stderr.write("cairn: no note named %r has id %r\n"
                                 % (args.name, args.id))
                return 1
        else:
            target = matches[0]
        path = os.path.join(notes_dir(store), target.get("file") or "")
        if not os.path.isfile(path):
            sys.stderr.write("cairn: note %r is in the index but its file is "
                             "missing; run `cairn reindex`\n" % args.name)
            return 1
        meta, old_body = parse_note(path)
        meta["updated"] = ts
        meta["last_timestamp"] = args.last_timestamp or meta.get("last_timestamp")
        if tags:
            meta["tags"] = sorted(set((meta.get("tags") or []) + tags))
        # Refresh the one-line summary so /checkpoints and /find don't show a
        # stale description for an updated note (the delta should lead with the
        # now-true state -- see the update flow in checkpoint.md).
        delta_sum = args.summary or extract_summary(body)
        if delta_sum:
            meta["summary"] = delta_sum
        # Scope describes how the note was built; on update we only change it when
        # the caller explicitly passes --scope, otherwise the existing scope stands.
        if args.scope:
            meta["scope"] = args.scope
        new_body = old_body.rstrip() + "\n\n---\n\n## Update — %s\n\n%s" % (ts, body)
        atomic_write(path, write_frontmatter(meta) + "\n\n" + new_body)
        upsert_index(store, meta, target["file"])
        print("updated %s\n%s" % (meta["id"], path))
        return 0

    note_id, path, ok = save_note(
        store, args.name, body, session=args.session or "unknown",
        cwd=args.cwd or os.getcwd(), tags=tags, parent=args.parent,
        source=args.source, summary=args.summary,
        last_timestamp=args.last_timestamp, created=args.created,
        scope=args.scope or "focused", pinned=args.pinned,
        best_effort=args.best_effort)
    if not ok and args.best_effort:
        sys.stderr.write("cairn: index busy; note saved, index will lazy-rebuild\n")
    print("saved %s\n%s" % (note_id, path))
    return 0


def _parse_tags(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        items = []
        for r in raw:
            items += re.split(r"[,\s]+", r)
    else:
        items = re.split(r"[,\s]+", raw)
    return [t for t in (i.strip() for i in items) if t]


def _fmt_date(s):
    return str(s or "")[:10]


def _safe_tags(n):
    """Tags from an index entry as a clean list of strings (a hand-edited
    index.json could have a bare string or numeric elements)."""
    t = n.get("tags") or []
    if not isinstance(t, list):
        t = [t]
    return [str(x) for x in t]


def cmd_list(args):
    store = store_dir(args)
    idx = read_index(store)
    notes = idx["notes"]
    if args.project:
        notes = [n for n in notes if args.project in (n.get("cwd") or "")]
    notes = _by_pinned_recency(notes)
    if args.json:
        print(json.dumps(notes, indent=2, ensure_ascii=False))
        return 0
    if not notes:
        print("No cairn notes yet. Create one with /cairn:checkpoint "
              "(or /checkpoint).")
        return 0
    print("%d note(s) in %s\n" % (len(notes), store))
    for n in notes:
        _print_note_line(n)
    return 0


def search_notes(store, query, project=None):
    """Ranked keyword search -> list of (score, note), best first. Shared by the
    `find` CLI and the MCP server so both rank identically. Empty query -> []."""
    idx = read_index(store)
    notes = idx["notes"]
    if project:
        notes = [n for n in notes if project in (n.get("cwd") or "")]
    tokens = [t.lower() for t in re.split(r"\s+", (query or "").strip()) if t]
    if not tokens:
        return []
    scored = []
    for n in notes:
        fn = n.get("file")
        if not fn:
            continue                     # malformed index entry -> skip, don't crash
        try:
            _, body = parse_note(os.path.join(notes_dir(store), fn))
        except OSError:
            body = ""                    # stale entry (file gone) -> search metadata only
        hay_body = body.lower()
        hay_meta = ((n.get("name") or "") + " " + " ".join(_safe_tags(n))
                    + " " + (n.get("summary") or "")).lower()
        score = 0
        for tok in tokens:
            score += hay_meta.count(tok) * 3 + hay_body.count(tok)
        if score > 0:
            scored.append((score, n))
    scored.sort(key=lambda s: (s[0], str(s[1].get("updated") or "")), reverse=True)
    return scored


def cmd_find(args):
    store = store_dir(args)
    if not [t for t in re.split(r"\s+", args.query.strip()) if t]:
        sys.stderr.write("cairn: empty query\n")
        return 1
    scored = search_notes(store, args.query, project=args.project)
    if args.json:
        print(json.dumps([{**n, "score": s} for s, n in scored], indent=2,
                         ensure_ascii=False))
        return 0
    if not scored:
        print("No notes match %r." % args.query)
        return 0
    print("%d match(es) for %r:\n" % (len(scored), args.query))
    for s, n in scored:
        print("• %s   [%s]  (score %d)" % (n.get("name"), _fmt_date(n.get("updated")), s))
        print("    %s" % (n.get("summary") or ""))
        print("    id: %s" % n.get("id"))
    return 0


def _resolve_one(store, query, action):
    matches = resolve_notes(store, query)
    if not matches:
        return None, "No note matches %r." % query
    # >1 match is ALWAYS ambiguous (incl. true duplicate names) -- never guess
    # for a destructive/loading action. An exact unique id/name yields 1 match.
    if len(matches) > 1:
        msg = ["%r matches %d notes; pass the exact id (%s):"
               % (query, len(matches), action)]
        for m in matches[:10]:
            msg.append("  %s  (%s)" % (m["id"], m["name"]))
        return None, "\n".join(msg)
    note = matches[0]
    # Stale index entry: the note file was deleted out of band. Don't let the
    # caller crash with FileNotFoundError -- report it and suggest reindex.
    if not os.path.isfile(os.path.join(notes_dir(store), note.get("file") or "")):
        return None, ("Note %r is in the index but its file is missing "
                      "(run `cairn reindex`)." % note.get("name"))
    return note, None


def cmd_show(args):
    store = store_dir(args)
    note, err = _resolve_one(store, args.name, "show")
    if err:
        print(err)
        return 0 if err.startswith("No note") else 2
    meta, body = parse_note(os.path.join(notes_dir(store), note["file"]))
    print("# %s" % meta.get("name"))
    print("_created %s · updated %s · source %s · session %s_"
          % (meta.get("created"), meta.get("updated"), meta.get("source"),
             meta.get("session_id")))
    if meta.get("tags"):
        print("_tags: %s_" % " ".join("#" + t for t in meta["tags"]))
    bits = []
    if meta.get("scope"):
        bits.append("scope: %s" % meta.get("scope"))
    if meta.get("pinned"):
        bits.append("📌 pinned")
    if bits:
        print("_%s_" % " · ".join(bits))
    print()
    print(body.strip())
    return 0


def render_load(store, names):
    """Map-not-dump load text for `names`: distilled note bodies + pointer lists,
    NEVER file contents. Returns (text, n_resolved). Shared by the `load` CLI and
    the MCP server so both honor the same guarantee and format identically."""
    resolved, missing, seen = [], [], set()
    for name in names:
        note, err = _resolve_one(store, name, "load")
        if note:
            if note.get("id") in seen:       # `load foo foo` -> load it once
                continue
            seen.add(note.get("id"))
            resolved.append(note)
        else:
            missing.append((name, err))
    if not resolved:
        return "\n".join(err for _, err in missing), 0
    out = ["# Resumed Cairn context — %d note(s)" % len(resolved),
           "> These notes are DISTILLED THINKING + POINTERS to files. They are your",
           "> loaded context. Do NOT open the referenced files unless the current",
           "> task actually requires them — the pointers are a map, not a dump."]
    for note in resolved:
        meta, body = parse_note(os.path.join(notes_dir(store), note["file"]))
        out.append("\n\n=== Note: %s  (created %s · session %s) ==="
                   % (meta.get("name"), _fmt_date(meta.get("created")),
                      meta.get("session_id")))
        out.append(body.strip())
    for name, err in missing:
        out.append("\n[skipped] %s" % err.splitlines()[0])
    return "\n".join(out), len(resolved)


def cmd_load(args):
    store = store_dir(args)
    text, n = render_load(store, args.names)
    print(text)
    return 0 if n else 1


def cmd_rm(args):
    store = store_dir(args)
    note, err = _resolve_one(store, args.name, "rm")
    if err:
        print(err)
        return 0 if err.startswith("No note") else 2
    path = os.path.join(notes_dir(store), note["file"])
    if not args.yes:
        print("Would delete: %s (%s)\n  %s\nRe-run with --yes to confirm."
              % (note["name"], note["id"], path))
        return 0
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    # exact sidecar only (a wildcard would also match a different note's sidecar)
    try:
        os.remove(path[:-len(".md")] + ".pending-digest.txt")
    except OSError:
        pass
    mutate_index(store, lambda idx: idx.__setitem__(
        "notes", [n for n in idx["notes"] if n.get("id") != note["id"]]))
    print("Deleted %s (%s)" % (note["name"], note["id"]))
    return 0


def cmd_path(args):
    store = store_dir(args)
    note, err = _resolve_one(store, args.name, "path")
    if err:
        sys.stderr.write(err + "\n")
        return 1
    print(os.path.join(notes_dir(store), note["file"]))
    return 0


def cmd_export(args):
    store = store_dir(args)
    note, err = _resolve_one(store, args.name, "export")
    if err:
        sys.stderr.write(err + "\n")
        return 1
    meta, body = parse_note(os.path.join(notes_dir(store), note["file"]))
    lines = ["# %s" % meta.get("name"), ""]
    created = meta.get("created")
    lines.append("_Cairn note · created %s · from session %s_"
                 % (_fmt_date(created), (meta.get("session_id") or "")[:8]))
    if meta.get("tags"):
        lines.append("_Tags: %s_" % ", ".join(meta["tags"]))
    if meta.get("parent"):
        lines.append("_Builds on: %s_" % meta["parent"])
    lines.append("")
    # strip internal "auto-captured" banner if present, keep the substance
    clean = re.sub(r"(?m)^>\s*\*\*Auto-captured.*?\n", "", body).strip()
    lines.append(clean)
    out = "\n".join(lines).rstrip() + "\n"

    dest = args.out or os.path.join(store, "exports", slugify(meta.get("name")) + ".md")
    dest = os.path.abspath(dest)         # so a bare filename has a real dirname
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    atomic_write(dest, out)
    print("Exported to %s" % dest)
    return 0


def _rewrite_note(store, note, meta, body):
    """Persist edited (meta, body) for an existing note + refresh its index entry.
    Keeps the id/filename stable; only the contents change."""
    path = os.path.join(notes_dir(store), note["file"])
    meta["updated"] = now_iso()
    atomic_write(path, write_frontmatter(meta) + "\n\n" + body.strip() + "\n")
    upsert_index(store, meta, note["file"])
    return path


def cmd_rename(args):
    store = store_dir(args)
    note, err = _resolve_for_edit(store, args.name, "rename", getattr(args, "id", None))
    if err:
        print(err)
        return 0 if err.startswith("No note") else 2
    meta, body = parse_note(os.path.join(notes_dir(store), note["file"]))
    old = meta.get("name")
    meta["name"] = args.new_name
    _rewrite_note(store, note, meta, body)
    print("Renamed %r -> %r (%s)" % (old, args.new_name, meta["id"]))
    return 0


def cmd_tag(args):
    store = store_dir(args)
    note, err = _resolve_for_edit(store, args.name, "tag", getattr(args, "id", None))
    if err:
        print(err)
        return 0 if err.startswith("No note") else 2
    meta, body = parse_note(os.path.join(notes_dir(store), note["file"]))
    add, remove = _parse_tags(args.add), set(_parse_tags(args.remove))
    if not add and not remove:
        # Pure view: never rewrite the note (that would bump `updated`/reorder it).
        print("Tags for %s: %s" % (meta.get("name"),
              " ".join("#" + t for t in (meta.get("tags") or [])) or "(none)"))
        return 0
    tags = [t for t in (meta.get("tags") or []) if t not in remove]
    for t in add:
        if t not in tags:
            tags.append(t)
    meta["tags"] = tags
    _rewrite_note(store, note, meta, body)
    print("Tags for %s: %s" % (meta["name"],
                               " ".join("#" + t for t in tags) or "(none)"))
    return 0


def cmd_pin(args):
    store = store_dir(args)
    note, err = _resolve_for_edit(store, args.name, "pin", getattr(args, "id", None))
    if err:
        print(err)
        return 0 if err.startswith("No note") else 2
    meta, body = parse_note(os.path.join(notes_dir(store), note["file"]))
    if args.pinned:
        meta["pinned"] = True
    else:
        meta.pop("pinned", None)          # unpin -> back to clean v1-shaped frontmatter
    _rewrite_note(store, note, meta, body)
    print("%s %s" % ("Pinned" if args.pinned else "Unpinned", meta["name"]))
    return 0


def cmd_recent(args):
    store = store_dir(args)
    idx = read_index(store)
    notes = idx["notes"]
    if args.project:
        notes = [n for n in notes if args.project in (n.get("cwd") or "")]
    notes = _by_pinned_recency(notes)[:max(1, args.n)]
    if args.json:
        print(json.dumps(notes, indent=2, ensure_ascii=False))
        return 0
    if not notes:
        print("No cairn notes yet. Create one with /cairn:checkpoint "
              "(or /checkpoint).")
        return 0
    print("%d most-recent note(s) in %s\n" % (len(notes), store))
    for n in notes:
        _print_note_line(n)
    return 0


def cmd_merge(args):
    store = ensure_store(store_dir(args))
    if len(args.sources) < 2:
        sys.stderr.write("cairn: merge needs at least 2 source notes\n")
        return 2
    sources, seen = [], set()
    for q in args.sources:
        note, err = _resolve_one(store, q, "merge")
        if err:
            print(err)
            return 0 if err.startswith("No note") else 2
        if note.get("id") in seen:           # `merge x alpha alpha` -> include once
            continue
        seen.add(note.get("id"))
        sources.append(note)
    if len(sources) < 2:
        sys.stderr.write("cairn: merge needs at least 2 DISTINCT source notes\n")
        return 2

    summary_bullets, parts, pointers, all_tags, merged_ids = [], [], [], [], []
    seen_ptr = set()
    for note in sources:
        m, b = parse_note(os.path.join(notes_dir(store), note["file"]))
        merged_ids.append(m.get("id"))
        for t in (m.get("tags") or []):
            if t not in all_tags:
                all_tags.append(t)
        summ = (m.get("summary") or extract_summary(b) or "").strip()
        summary_bullets.append("- **%s:** %s" % (m.get("name"), summ))
        for line in _section_lines(b, "Files & areas to look at"):
            key = line.strip()
            if key and key not in seen_ptr:
                seen_ptr.add(key)
                pointers.append(line.rstrip())
        body_wo_files = _strip_section(b, "Files & areas to look at")
        parts.append('## From "%s"\n\n%s'
                     % (m.get("name"), _demote_headers(body_wo_files).strip()))

    out = ["## Summary",
           "Merged note combining %d checkpoint(s):" % len(sources)]
    out += summary_bullets
    out.append("")
    for p in parts:                       # blank line between blocks so every
        out += [p, ""]                    # '## From ...' header starts clean
    out.append("## Files & areas to look at")
    out += pointers if pointers else ["- (none)"]
    out += ["", "## Merged from"]
    out += ["- %s (%s)" % (n.get("name"), i) for n, i in zip(sources, merged_ids)]
    body = "\n".join(out)

    tags = list(all_tags)
    for t in _parse_tags(args.tags):
        if t not in tags:
            tags.append(t)
    nid, path, _ = save_note(
        store, args.name, body, session=args.session or "merge",
        cwd=args.cwd or os.getcwd(), tags=tags, parent=merged_ids[0],
        scope="full",
        summary="Merged: " + "; ".join(n.get("name") or "" for n in sources))
    print("merged %d note(s) into %s\n%s" % (len(sources), nid, path))
    return 0


def cmd_diff(args):
    store = store_dir(args)
    a, erra = _resolve_one(store, args.a, "diff")
    if erra:
        print(erra)
        return 0 if erra.startswith("No note") else 2
    b, errb = _resolve_one(store, args.b, "diff")
    if errb:
        print(errb)
        return 0 if errb.startswith("No note") else 2
    ma, ba = parse_note(os.path.join(notes_dir(store), a["file"]))
    mb, bb = parse_note(os.path.join(notes_dir(store), b["file"]))
    secs_a, secs_b = _section_headers(ba), _section_headers(bb)
    ptr_a = set(ln.strip() for ln in _section_lines(ba, "Files & areas to look at"))
    ptr_b = set(ln.strip() for ln in _section_lines(bb, "Files & areas to look at"))
    res = {
        "a": ma.get("name"), "b": mb.get("name"),
        "summary_changed": (ma.get("summary") or "") != (mb.get("summary") or ""),
        "sections_only_in_a": sorted(secs_a - secs_b),
        "sections_only_in_b": sorted(secs_b - secs_a),
        "sections_common": sorted(secs_a & secs_b),
        "pointers_only_in_a": sorted(ptr_a - ptr_b),
        "pointers_only_in_b": sorted(ptr_b - ptr_a),
        "pointers_common": sorted(ptr_a & ptr_b),
    }
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0
    print("# diff: %r  vs  %r" % (res["a"], res["b"]))
    print("\nsummary: %s" % ("CHANGED" if res["summary_changed"] else "same"))

    def _block(title, items):
        print("\n%s:" % title)
        if items:
            for it in items:
                print("  - %s" % it)
        else:
            print("  (none)")
    _block("sections only in %r" % res["a"], res["sections_only_in_a"])
    _block("sections only in %r" % res["b"], res["sections_only_in_b"])
    _block("pointers only in %r" % res["a"], res["pointers_only_in_a"])
    _block("pointers only in %r" % res["b"], res["pointers_only_in_b"])
    _block("pointers in both", res["pointers_common"])
    return 0


def cmd_reindex(args):
    store = store_dir(args)
    idx = reindex(store)
    print("Reindexed %d note(s) into %s" % (len(idx["notes"]), index_path(store)))
    return 0


def cmd_redact(args):
    sys.stdout.write(redact_text(sys.stdin.read()))
    return 0


def cmd_selftest(args):
    """A dependency-free smoke test (no pytest needed) over the core paths,
    using the real engine APIs directly."""
    import shutil
    import tempfile
    fails = []

    def check(name, cond):
        print(("  PASS " if cond else "  FAIL ") + name)
        if not cond:
            fails.append(name)

    print("cairn selftest")
    check("slugify", slugify("Auth Refactor!") == "auth-refactor"
          and slugify("日本語").startswith("note-"))
    r = redact_text("key sk-ant-" + "abc123def456ghi789jkl and AKIA" + "IOSFODNN7EXAMPLE x")
    check("redact secrets", "[REDACTED:anthropic_key]" in r and "[REDACTED:aws_key]" in r)
    check("redact keeps prose",
          redact_text("the password reset email") == "the password reset email")

    tmp = tempfile.mkdtemp(prefix="cairn-selftest-")
    try:
        body = ("## Summary\nBuilt the thing; chose A over B.\n\n## Directions explored\n"
                "- B — rejected: too slow.\n\n## Files & areas to look at\n"
                "- src/main.py\n\n## Next step\nShip it.\n")
        save_note(tmp, "demo note", body, session="abcd1234-1111",
                  cwd="/example/proj", tags=["auth"])
        idx = read_index(tmp)
        check("save -> 1 note in index", len(idx["notes"]) == 1)
        check("summary auto-extracted", idx["notes"][0]["summary"].startswith("Built the thing"))
        check("resolve by name", len(resolve_notes(tmp, "demo note")) == 1)
        with open(index_path(tmp), "w") as f:
            f.write("{ this is not json")
        check("auto-reindex on corrupt", len(read_index(tmp)["notes"]) == 1)
        nf = os.listdir(notes_dir(tmp))[0]
        _, saved = parse_note(os.path.join(notes_dir(tmp), nf))
        check("note body has rejected direction", "rejected" in saved.lower())

        # v1.5: scope + pin roundtrip, and rename keeps the id while changing name
        sid, spath, _ = save_note(tmp, "scoped", body, session="ss-1", cwd="/p",
                                  scope="full", pinned=True)
        sm, sb = parse_note(spath)
        check("scope+pin roundtrip", sm.get("scope") == "full" and sm.get("pinned") is True)
        snote = resolve_notes(tmp, "scoped")[0]
        sm["name"] = "renamed"
        _rewrite_note(tmp, snote, sm, sb)
        ridx = {n["id"]: n for n in read_index(tmp)["notes"]}
        check("rename updates name + keeps id", ridx.get(sid, {}).get("name") == "renamed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%s (%d failure(s))" % ("OK" if not fails else "FAILED", len(fails)))
    return 1 if fails else 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="cairn", description="Claude Cairn core CLI")
    p.add_argument("--store", help="override note store (default: $CAIRN_HOME or ~/.claude/cairn)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_transcript(sp):
        sp.add_argument("transcript", nargs="?", help="transcript .jsonl path (resolved defensively)")
        sp.add_argument("--session", help="session id (for worktree-safe resolution)")
        sp.add_argument("--cwd", help="originating cwd")

    sp = sub.add_parser("resolve", help="resolve a transcript path (worktree-safe)")
    add_transcript(sp)
    sp.add_argument("--list", action="store_true",
                    help="list ALL transcripts for --cwd (newest first) instead of resolving")
    sp.set_defaults(func=cmd_resolve)

    sp = sub.add_parser("digest", help="distillation-ready reasoning trace")
    add_transcript(sp)
    sp.add_argument("--since", help="only events after this ISO timestamp")
    sp.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    sp.set_defaults(func=cmd_digest)

    sp = sub.add_parser("extract", help="mechanical note body (for the hook)")
    add_transcript(sp)
    sp.add_argument("--since")
    sp.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    sp.set_defaults(func=cmd_extract)

    sp = sub.add_parser("save", help="write/append a note (body on stdin)")
    sp.add_argument("--name", required=True)
    sp.add_argument("--tags", action="append")
    sp.add_argument("--parent")
    sp.add_argument("--session")
    sp.add_argument("--cwd")
    sp.add_argument("--source", default="manual", choices=["manual", "auto"])
    sp.add_argument("--summary")
    sp.add_argument("--last-timestamp", dest="last_timestamp")
    sp.add_argument("--created")
    sp.add_argument("--update", action="store_true")
    sp.add_argument("--id", help="disambiguate the note to --update")
    sp.add_argument("--body-file", dest="body_file")
    sp.add_argument("--scope", choices=SCOPE_CHOICES,
                    help="checkpoint breadth: full (all topics) | focused (current) | "
                         "delta (since last); default focused on a new note")
    sp.add_argument("--pinned", action="store_true", help="pin the new note to the top")
    sp.add_argument("--best-effort", dest="best_effort", action="store_true",
                    help="skip index write under lock contention (hooks)")
    sp.set_defaults(func=cmd_save)

    sp = sub.add_parser("list", help="list notes (newest first)")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--project")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("find", help="ranked keyword search")
    sp.add_argument("query")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--project")
    sp.set_defaults(func=cmd_find)

    sp = sub.add_parser("show", help="print a note to the terminal")
    sp.add_argument("name")
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("load", help="emit note(s) as resume context (no file bodies)")
    sp.add_argument("names", nargs="+")
    sp.set_defaults(func=cmd_load)

    sp = sub.add_parser("export", help="standalone shareable markdown")
    sp.add_argument("name")
    sp.add_argument("--out")
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("rm", help="delete a note")
    sp.add_argument("name")
    sp.add_argument("--yes", action="store_true")
    sp.set_defaults(func=cmd_rm)

    sp = sub.add_parser("path", help="print a note's file path")
    sp.add_argument("name")
    sp.set_defaults(func=cmd_path)

    sp = sub.add_parser("rename", help="rename a note's display name")
    sp.add_argument("name")
    sp.add_argument("new_name", metavar="new-name")
    sp.add_argument("--id", help="disambiguate when the name matches several notes")
    sp.set_defaults(func=cmd_rename)

    sp = sub.add_parser("tag", help="add/remove tags on a note")
    sp.add_argument("name")
    sp.add_argument("--add", action="append", help="comma/space-separated tag(s) to add")
    sp.add_argument("--remove", action="append", help="comma/space-separated tag(s) to remove")
    sp.add_argument("--id", help="disambiguate when the name matches several notes")
    sp.set_defaults(func=cmd_tag)

    sp = sub.add_parser("pin", help="pin a note to the top of list/recent")
    sp.add_argument("name")
    sp.add_argument("--id", help="disambiguate when the name matches several notes")
    sp.set_defaults(func=cmd_pin, pinned=True)

    sp = sub.add_parser("unpin", help="unpin a note")
    sp.add_argument("name")
    sp.add_argument("--id", help="disambiguate when the name matches several notes")
    sp.set_defaults(func=cmd_pin, pinned=False)

    sp = sub.add_parser("recent", help="the N most-recent notes (pinned first)")
    sp.add_argument("--n", type=int, default=10)
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--project")
    sp.set_defaults(func=cmd_recent)

    sp = sub.add_parser("merge", help="merge several notes into one new note")
    sp.add_argument("--name", required=True, help="name for the merged note")
    sp.add_argument("sources", nargs="+", help="2+ source notes (by name or id)")
    sp.add_argument("--tags", action="append")
    sp.add_argument("--session")
    sp.add_argument("--cwd")
    sp.set_defaults(func=cmd_merge)

    sp = sub.add_parser("diff", help="structural diff between two notes")
    sp.add_argument("a")
    sp.add_argument("b")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_diff)

    sp = sub.add_parser("reindex", help="rebuild index.json from note frontmatter")
    sp.set_defaults(func=cmd_reindex)

    sp = sub.add_parser("redact", help="redact secrets from stdin")
    sp.set_defaults(func=cmd_redact)

    sp = sub.add_parser("selftest", help="run an in-process smoke test")
    sp.set_defaults(func=cmd_selftest)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
