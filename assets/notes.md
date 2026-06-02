# Cairn - How Checkpoint Scoping *Actually* Works

> Written to kill a specific confusion for good: **why a second checkpoint in
> the same session does NOT contain every earlier topic - even though the raw
> material handed to it does.** The short answer: a checkpoint runs in **two
> layers**, and it is **Layer 2 (distillation), not Layer 1 (the engine), that
> does the topic separation.** Not all of the chat's content is kept in a note.

---

## TL;DR

- A `/checkpoint` is **two steps**, not one:
  1. **Layer 1 - Digest** (deterministic engine, `lib/cairn.py`): reads the
     transcript and builds the *raw material*.
  2. **Layer 2 - Distillation** (the LLM, driven by `commands/checkpoint.md`):
     reads that raw material and *writes the note*.
- **Layer 1 scopes by time only**, never by topic. A *fresh* checkpoint reads
  the **whole session from line 1**; an *update* reads only events **after the
  previous note's timestamp** (`--since`).
- **Layer 2 is where topic separation happens.** Even when Layer 1 hands over
  the *entire* session (both/all topics), the LLM writes a note focused on what
  you were actually checkpointing, and **leaves the rest out.**
- Therefore: **the clean, single-topic notes you get are produced by good LLM
  judgment, not by a deterministic guarantee.** Usually right; not a rule you
  can lean on 100%. For a *hard, mechanical* cut, use `/checkpoint update`.

---

## The two layers, drawn out

```
   /checkpoint topic-two
        │
   ┌────┴───────────────────────────────────────────────┐
   │ LAYER 1 - DIGEST  (lib/cairn.py, deterministic)     │
   │                                                     │
   │  • Fresh checkpoint  → reads WHOLE session (line 1) │
   │  • Update            → reads only events AFTER the  │
   │                        previous note's last_timestamp (--since)
   │                                                     │
   │  Scopes by TIME ONLY. Never by topic.               │
   │  → For a fresh checkpoint the raw material          │
   │    contains EVERY topic discussed so far.           │
   └────┬───────────────────────────────────────────────┘
        │  (hands ALL of it to the LLM)
   ┌────┴───────────────────────────────────────────────┐
   │ LAYER 2 - DISTILL  (commands/checkpoint.md, the LLM)│
   │                                                     │
   │  • Reads the raw digest (which may hold many topics)│
   │  • WRITES THE NOTE - and here it exercises judgment:│
   │    it scopes the note to the thing you just asked   │
   │    it to checkpoint, and drops the rest.            │
   │                                                     │
   │  THIS is where topic separation happens.            │
   │  → The note is a SELECTION, not the full chat.      │
   └─────────────────────────────────────────────────────┘
```

**Key sentence to remember:** *Layer 1 decides what time-window of the chat is
available; Layer 2 decides what actually goes into the note. The note is never
the whole chat - it is what the LLM judged worth keeping.*

---

## The proof (why we know it's Layer 2, not Layer 1)

We ran the exact test:

1. One fresh session. Discussed **hash maps**, then `/checkpoint topic-one`.
2. Same session, switched to **bloom filters**, then `/checkpoint topic-two`
   (a **fresh** checkpoint, *not* an update).
3. Loaded both notes:
   - `topic-one` → only hash maps ✅ (expected)
   - `topic-two` → **only bloom filters** - no hash maps at all.

That looks like the engine cleanly separated the topics. It did **not**. We then
ran the raw whole-session digest that the fresh `topic-two` checkpoint actually
saw:

```bash
CAIRN="/Users/arcaman07/Documents/Fun Projects/claude cairn/lib/cairn.py"
python3 "$CAIRN" digest <that-session.jsonl> \
  | grep -ioE "hash map|bucket|chaining|bloom|bit array|false positive" \
  | sort | uniq -c | sort -rn
```

Result - **both** topics are in the raw material:

```
  14 bucket          ← hash maps
   6 Bloom           ← bloom filters
   5 bit array       ← bloom filters
   4 hash map        ← hash maps
   4 chaining        ← hash maps
   2 false positive  ← bloom filters
```

So the fresh `topic-two` checkpoint **had hash maps right in front of it** and
still produced a bloom-filters-only note. The separation was done by the LLM in
**Layer 2**, not by the engine in Layer 1. Confirmed.

---

## What this means in practice

| You run | Layer 1 gives the LLM | The note you get | Why |
|---|---|---|---|
| `/checkpoint <new>` (fresh) | the **whole session** (all topics) | usually **just the current topic** | Layer 2 judgment scopes it down |
| `/checkpoint update <name>` | **only events since the last note** (`--since`) | **only the new material**, appended as `## Update` | Layer 1 time-cut - the old topic isn't even in the raw material |

Two honest consequences:

1. **A fresh checkpoint is *not guaranteed* to exclude earlier topics.** In a
   session where two topics are intertwined, or where the earlier topic is
   clearly still relevant to current work, the LLM may legitimately pull both
   in - because both are in the raw material. The clean separation you saw is
   the *common* case, not a *contract*.
2. **`update` is the only deterministic clean cut.** It passes `--since` into
   Layer 1, so the earlier topic is **physically absent** from the raw material.
   No judgment involved - it *cannot* leak in. (Caveat: the cut is strict
   greater-than on the timestamp, so if you *circled back* to the old topic
   *after* the previous checkpoint, that later mention is post-timestamp and
   will be included - again, time, not topic.)

**A note is a MAP, not a DUMP.** Two separate mechanisms guarantee this:
- `load` only ever emits the note's summary + the "Files & areas" pointer list,
  never the contents of referenced project files (enforced in `cairn.py`, not by
  prompt).
- Layer 2 distillation keeps only the decisions / directions / open questions /
  pointers worth resuming - **the full chat transcript is never stored in the note.**

---

## The gap we want to close (forward pointer)

Right now the user has only two scope behaviors, and one of them is implicit:

- **Fresh** = "the LLM picks the salient topic" (Layer 2 judgment - not user-controllable).
- **Update** = "only the delta since the last checkpoint" (Layer 1 time-cut).

There is **no first-class way to say**: *"For this second checkpoint, give me the
**entire list of topics** summarized from the whole chat - every thread, as a
structured table of contents - NOT just the latest topic, and NOT just the delta
since the previous checkpoint."*

That capability is a **Layer 2 change** (the distillation instruction needs a
"summarize ALL topics, drop nothing" mode), optionally paired with the existing
whole-session Layer 1 digest. We want to expose it as an explicit, user-chosen
**scope** so the behavior is a deliberate command, not a judgment call.

→ Full design, plus the rest of the command/feature backlog, lives in
[`future_roadmap.md`](future_roadmap.md) under **"Priority 1 - Checkpoint scope
modes."**
