# Contributing to Claude Cairn

Cairn is small and dependency-free, so it's easy to hack on. Thanks for helping.

## Setup

- Requires **Python 3**, standard library only, nothing to `pip install`.
- Layout: the engine is `lib/cairn.py`; slash-command prompts live in `commands/`;
  the skill is `skills/cairn/SKILL.md`; hooks are in `hooks/`.
- To run your working copy inside Claude Code during development:

  ```
  claude --plugin-dir ./claude-cairn
  /reload-plugins      # after each change, no restart needed
  ```

## Running the tests

Stdlib `unittest`, no test dependencies:

```
python3 lib/cairn.py selftest      # fast in-process smoke test
bash tests/run_tests.sh            # full unit suite
bash tests/verify_install.sh       # validate the plugin tree as the loader sees it
```

All three should pass before you open a PR.

## Conventions

- **Stdlib only.** The engine must not take third-party dependencies. If you reach
  for a package, find a standard-library way instead.
- **Engine is deterministic; Claude does the judgment.** Mechanical work (transcript
  parsing, redaction, the note store, search) lives in `lib/cairn.py`. Distillation
  *quality* lives in the `commands/*.md` prompts. Keep that split, don't put
  judgment in the CLI or plumbing in the prompts.
- **Notes are the source of truth; `index.json` is a derived cache.** Write notes
  atomically; never make the index authoritative (it must be rebuildable with
  `cairn.py reindex`).
- **Redact before writing, and before truncating.** Any new path that emits
  transcript content must pass through `redact_text` first.
- **Hooks must never crash a session.** Hook scripts always exit 0 and swallow their
  own errors.
- Match the surrounding style: 4-space indent, clear names, and comments that
  explain *why*. Add or update a test for any behavior change.
- Keep the six-section note format stable, `/cairn:checkpoint update` relies on it.

## Opening a PR

1. If you're starting from a plain copy that isn't a git repo yet, run `git init`.
2. Branch: `git checkout -b my-change`.
3. Make a focused change and run the three test commands above.
4. Commit with a clear message, push your branch, and open a PR describing **what**
   changed and **why**, including the test output.
