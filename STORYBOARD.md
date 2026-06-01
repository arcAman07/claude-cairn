# Claude Cairn: launch video storyboard

**Format:** ~32s, 1920×1080, 60fps**no narration** (text-on-screen only).
**Engine:** Manim CE 0.20.1 via `python3 -m manim`. **Text only, no LaTeX.**
**Scenario:** on a web project you design two features in one session, checkpoint each,
then load them in two separate terminals and build in parallel.

## Type & palette
- **Type:** Avenir Next (headings, wordmark, captions) · Menlo (terminal lines, commands).
- **Brand accent:** teal `#1FA39A` = the "chosen / command / context-loaded" signal.
- **Background:** dark `#10201E`. **Text:** `#EAF1F0`. **Muted:** `#7E938F`. **Panel:** `#182B29`.
- **Logo:** the real `assets/logo.png` (terracotta cairn) embedded on the end card.

---

## Beat 1: Design a couple of features  (~9s)
**Heading:** `Design a couple of features`
**Window** `claude code · web-app`, lines type in (Menlo):
```
web app · v1, designing two features
auth       sessions → JWT + refresh
database   Postgres, raw SQL
designed both, time to build
```
`auth` and `database` highlight in teal (the two features). **Hold ~2.6s.**

## Beat 2: Checkpoint each one  (~10s)
**Heading:** `Checkpoint each one`
**Commands (typed, teal):** `/cairn:checkpoint auth` and `/cairn:checkpoint database`
**Two note cards form side by side** (real Cairn note shape):
```
auth      #feature           database  #feature
Summary                      Summary
JWT auth + refresh tokens    Postgres data layer
Decisions                    Decisions
JWT, not server sessions     raw SQL, not an ORM
Next                         Next
build POST /auth/login       write schema.sql
```
**Caption:** `two checkpoints, one per feature`. **Hold ~3s.**

## Beat 3: Load each in its own terminal  (~13s)  ← the point
**Heading:** `Load each in its own terminal`
**Two terminals side by side** (`claude code · auth`, `claude code · database`); a note
flies into each; each fills in (Menlo):
```
$ /cairn:load auth            $ /cairn:load database
context loaded                context loaded
next: build POST /auth/login  next: write schema.sql
implementing…                 implementing…
```
**Caption (teal):** `design context already loaded, build in parallel`. **Hold ~3.2s.**

## Beat 4: End card  (~7s)
```
        [ logo.png, the cairn ]
            Claude Cairn
   Save the thinking. Resume it anywhere.        (teal)
 Portable, distilled session notes for Claude Code.   (muted)
 /cairn:checkpoint   /cairn:load   /cairn:find   /cairn:checkpoints   (Menlo, muted)
```

---

**Actual duration:** 32.4s (no-narration). **Truth check:** every command shown is real
(`/cairn:checkpoint`, `/cairn:load`, `/cairn:find`, `/cairn:checkpoints`); the note shape
matches `commands/checkpoint.md` (Summary · Decisions · Next, with the chosen-vs-rejected
captured in Decisions); no invented features.
