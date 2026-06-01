# Claude Cairn: Verification Report

Two full verification passes were run, each with evidence (commands + real output),
independent grading, and an adversarial code audit. Round 2 was a *fresh* pass on
the post-fix code and it found real regressions, documented below, all fixed.

**Current state:** 114 tests pass · 92% coverage (lib 93%) · ruff + pyflakes clean
(lib/hooks/tests) · no dead functions · 8/8 commands + auto-capture pass · 9/9
fixtures pass the summary rubric + resume test · 0 redaction leaks · 40 defects
found across both rounds, all resolved or consciously accepted.

> Note: `assets/` (logo, Manim launch animation), `DESIGN.md`, `CONTRIBUTING.md`,
> and `LAUNCH.md` were authored out-of-band (not by the build). `from manim import
> *` in `assets/cairn_launch.py` is idiomatic Manim and is not linted here. (An
> earlier stale `cairn-design.md` draft was removed once `DESIGN.md` superseded it.)

---

## 1. Command pass/fail (8 commands + auto-capture)

| Command | Criterion | Result |
|---|---|---|
| `/checkpoint [name]` | valid note + frontmatter; decisions + dropped directions; redacts; auto-names; updates index | PASS |
| `/checkpoint update <name>` | clean append, no dup, summary + timestamp refreshed | PASS |
| `/checkpoints` | reads index, newest-first, empty-store grace | PASS |
| `/load <name> …` | summary + pointers, never file bodies; merges; cross-directory | PASS |
| `/find <query>` | ranked over body+tags; sensible no-match | PASS |
| `/export <name>` | self-contained, cold-readable, predictable path | PASS |
| `/cairn:show <name>` | prints; honest that the slash form enters context | PASS |
| `/cairn:rm <name>` | removes file + entry; safe on missing; safe on duplicate names | PASS |
| PreCompact auto-capture | one rolling note/session; never crashes (exit 0) | PASS |

Verified via: full lifecycle run (state shown between every step), the 114-test
suite, and two independent digest-only distill+grade workflows.

## 2. Summary quality (independent, digest-only) + resume test

Two independent runs (fresh agents each time). Averages of run 1 / run 2:

| Faithfulness | Completeness | Conciseness | Actionability | Redaction | Resume |
|---|---|---|---|---|---|
| 5.00 / 4.89 | 5.00 / 5.00 | 4.00 / 4.33 | 4.89 / 4.89 | 5.00 / 5.00 | 9/9 both |

Redaction leaks: **0** in both runs (secrets fixture independently grep-clean).
The one run-2 faithfulness-4 (worktree) was a grader artifact, it flagged "small
JSON body" as invented, but that phrase is literally in the fixture; the note was
faithful. Exploration captured all rejected paths + reasons; long/compacted kept
the pre-compaction decision; trivial/empty stayed minimal (no hallucination).

## 3. Edge cases (expected → observed)

empty transcript → header, no crash · 73 MB → 45 KB bounded, ~1s · missing → exit 1
· worktree → resolves by session-id glob (unit-proven) · malformed index → auto-
rebuild · spaces → fs-safe slug · unicode → hash slug · duplicate name → refuses
(exit 2) · empty query → matches nothing · missing name → graceful · 5 concurrent
writers → valid index, all files, reindex recovers all.

## 4. Static analysis & coverage

- ruff (full ruleset) + pyflakes: **clean** on lib/hooks/tests. byte-compile OK.
- **No dead functions** (reference scan). `write_index` removed (orphaned by the
  `mutate_index` refactor); `cmd_selftest` rewritten to drop a fake-argparse hack.
- 114 tests, green, ~8s. Coverage **92%** (lib/cairn.py **93%**, hooks 83-86%).
  Accepted gaps: defensive `except` branches, lock-timeout race, the unreachable
  10,000-collision filename fallback, CLI default-path lines.

## 5. Defects found & resolved

### Round 1 (build review + my own hardening): 22, all fixed
Redaction ReDoS in `_ASSIGN`; 12× budget blowout via compaction markers; redaction
gaps (AWS/Stripe/npm/Basic/conn-string); secret-leak at truncation boundary;
duplicate-name delete; sidecar over-deletion; index lost-update window; string-tag
corruption; cwd-only resolution ambiguity; stale-summary-on-update; auto-note
anti-signal + store bloat; under-constrained template; buried show caveat; plus
lint/dead-code cleanup. (Details retained in git history of this file.)

### Round 2 (fresh independent 6-dimension audit): 18 confirmed, all resolved
The audit reproduced each finding against the post-fix code. **Three were
regressions introduced by my own Round-1 fixes.**

| # | Sev | Finding | Resolution |
|---|---|---|---|
| 1 | HIGH | **ReDoS in `_URL_CRED`**, unbounded scheme `[a-z0-9+.\-]*://` backtracks quadratically on dotted text (stack traces, package dumps); 123 KB → 9.5s; reachable via the PreCompact hook. *(my Round-1 regression)* | Bounded scheme to `{0,31}` (RFC 3986). 123 KB → 0.18s; conn-string redaction byte-identical. |
| 12 | HIGH | **Duplicate auto-notes**, a best-effort index write skipped under contention made the next compaction's find-existing miss → spawned a duplicate, defeating "rolling". *(my Round-1 regression)* | New `roll_auto_note()` does find+create+index-write under one lock hold. |
| 16 | HIGH | **Empty/blank query resolved to the sole note**, `rm ""`/`show ""` could hit the only note. | `resolve_notes` returns `[]` for an empty query. |
| 2 | MED | JSON/quoted-key secrets (`{"password":"…"}`) not redacted. | `_ASSIGN` now allows optional surrounding quotes on the key. |
| 5 | MED | `text_budget` floor + file block could exceed a small `budget`. | Hard ceiling: final output truncated to `budget` (post-redaction). |
| 6 | MED | `FileLock.__exit__` deleted a successor's lock after a stale-steal. | Unlink only if the file at the path still has our fd's inode. |
| 7 | MED | `reindex()` wrote `index.json` unlocked, clobbering a locked upsert. | Split `reindex_build` (pure) / `reindex` (writes under lock); `read_index` rebuilds in memory without writing. |
| 17 | MED | `--update --id <wrong>` silently updated `matches[0]`. | Errors if no match has that id. |
| 11,13,14 | MED | Hook rolling-note races / corrupt / stale-entry edges. | All handled in `roll_auto_note` (lock-held, guards missing/corrupt/id-less, prunes extras). |
| 3 | LOW | ReDoS via repeated unmatched PEM `BEGIN` headers. | Bounded the BEGIN→END gap to `{0,4096}`. |
| 18 | LOW | Non-string tag list elements crashed find/list. | `parse_note` coerces elements to `str`. |
| 10,15 | NIT | `basename[:-6]` mangled non-`.jsonl`; autoload rendered literal `None`. | `os.path.splitext`; null-coalesced labels. |

### Consciously accepted (not "fixed"), with rationale
- **#4 (LOW)**, a secret glued to a 33+ char boundary-free word run isn't caught.
  This is the inherent cost of the *deliberate* bounded-key design that prevents
  ReDoS. Redaction is documented as best-effort.
- **#8 (MED)**, on lock timeout the index write proceeds *without* the lock, a
  small lost-update window. Kept by design: the index is a derived cache, notes
  are the source of truth, and any inconsistency self-heals on the next
  `reindex`. Failing the write instead would risk dropping a user's checkpoint, 
  worse for a notes tool. The inode-safe lock (#6) + `roll_auto_note` shrink the
  window substantially.

All 18 have regression tests (`tests/test_audit_fixes.py`).

## 6. Honest verdict

**Solid.** Engine streams 73 MB in ~1s; redaction is now ReDoS-safe on every known
vector (verified end-to-end through the hook path); map-not-dump is enforced in
code; the hook never crashes a session and keeps one rolling auto-note per session
atomically; index self-heals; distillation passes the resume test 9/9 across two
independent runs with zero leaks.

**Fragile / honest caveats.**
- Redaction is **best-effort**, not a guarantee (#4; novel/keyless secret formats).
- Index consistency under heavy concurrent writes is **eventually-consistent**, not
  strictly serialized (#8), safe because notes are the source of truth.
- `/cairn:*` slash-command **registration is only fully proven by a real restart**;
  the engine + prompts + manifest are verified, not first-run registration.
- `find` is literal (no stemming); distillation quality depends on the model.

**What I'd harden next (proposals, not built):** enable the shipped-disabled
SessionStart auto-load; exact-name/tag-substring boost for `find`; lineage via
`parent` + a `--graph`; periodic prune of old `source:auto` notes.
