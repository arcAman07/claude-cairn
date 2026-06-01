# Claude Cairn — launch video storyboard

**Format:** ~36s, 1920×1080, 60fps, **no narration** (text-on-screen only).
**Engine:** Manim CE 0.20.1 via `python3 -m manim`. **Text/MarkupText only — no LaTeX.**
**One concrete example end-to-end:** choosing a **rate-limiting** algorithm.
The payoff beat is recovering the **rejected** directions (and *why*) in a fresh session.

## Type & palette
- **Type:** Avenir Next (UI: headings, wordmark, captions) · Menlo (terminal lines, commands, note body).
- **Brand accent:** teal `#1FA39A` (per brief) = the "chosen / loaded / command" signal.
- **Background:** dark `#10201E`. **Text:** `#EAF1F0`. **Muted:** `#7E938F`. **Panel:** `#182B29`.
- **Rejected options:** muted + strikethrough (so teal reads as "the good path").
- **Logo:** the real `assets/logo.png` (terracotta cairn) embedded at the end — teal + terracotta
  is a deliberate complementary pair on the dark bg. *(If you'd rather the whole video be terracotta
  to match the logo/DESIGN palette instead of teal, say so — one-line change.)*

---

## Beat 1 — You reason through a hard problem  (~8s)
**Heading (top):** `You reason through a hard problem`
**Terminal window** `claude code · session`, lines type/fade in (Menlo):
```
considering: API rate limiting
fixed-window  — boundary bursts        ← struck through (rejected)
leaky-bucket  — no bursts allowed      ← struck through (rejected)
token-bucket  — bursts + smooth avg    ← teal (chosen)
```
**Motion:** four lines appear in sequence; a strikethrough draws across the two rejected lines;
`token-bucket` turns teal. **Transition out:** hold ~1.2s.

## Beat 2 — Checkpoint the thinking  (~7s)
**Heading:** `Checkpoint the thinking`
**Command (typed, teal, Menlo):** `/cairn:checkpoint rate-limiting`
**A note card forms** (the real Cairn note shape):
```
rate-limiting                         #api
──────────────────────────────────────────
Summary
chose token-bucket for API rate limiting
Directions explored
token-bucket — chosen
fixed-window — rejected: boundary bursts     ← struck
leaky-bucket — rejected: no bursts           ← struck
Next step
add token-bucket middleware in api/limit.ts
```
**Motion:** command types in; the session's reasoning condenses into the card section-by-section;
a teal border "seal" pulse. **Caption:** `a portable note — the decision and the dead ends`.

## Beat 3 — The gap  (~5s)
**Heading:** `Days later. A different machine.`
**Motion:** the session window dims and collapses; a **blank** new session window fades up with a
blinking cursor. **Caption (muted):** `normally, the reasoning is gone`.

## Beat 4 — Load it — the reasoning comes back  (~10s)  ← the point
**Heading:** `Load it — the reasoning comes back`
**Command (teal):** `/cairn:load rate-limiting`
**The note flows into the blank session;** lines reappear (Menlo):
```
resumed: rate-limiting
token-bucket — chosen
fixed-window — rejected: boundary bursts     ← pulses/highlights
next: add middleware in api/limit.ts
```
**Caption (teal):** `…including what you ruled out — and why`
**Motion:** the note travels into the new window; the `fixed-window — rejected` line pulses to land
the payoff (you don't re-walk the dead end). Hold ~1.5s.

## Beat 5 — End card  (~6s)
**Visual (centered):**
```
        [ logo.png — the cairn ]
            Claude Cairn
   Save the thinking. Resume it anywhere.        (teal)
 Portable, distilled session notes for Claude Code.   (muted)
 /cairn:checkpoint   /cairn:load   /cairn:find   /cairn:checkpoints   (Menlo, muted)
```
**Motion:** logo fades up; wordmark, tagline, one-liner, then the command row stagger in. Hold ~2.5s.

---

**Duration budget:** 8 + 7 + 5 + 10 + 6 = **36s** (within 30–45s).
**Truth check:** every command shown is real (`/cairn:checkpoint`, `/cairn:load`, `/cairn:find`,
`/cairn:checkpoints`); the note shape matches `commands/checkpoint.md` (Summary · Directions explored
with rejected options · Next step); no invented features.
