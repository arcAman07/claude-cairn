#!/usr/bin/env python3
"""Generate diverse, realistic transcript fixtures for QA (Phases 4-6).

Each fixture is JSONL in the format Claude Code actually writes, designed to
stress a specific aspect of distillation. Run: `python3 make_fixtures.py`.
The content is intentionally rich (real decisions, rejected paths, the *why*)
so the summary-quality grading has genuine material to evaluate.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _ts(i):
    return "2026-03-%02dT%02d:%02d:00.000Z" % (1 + i // 1440, (i // 60) % 24, i % 60)


class T:
    def __init__(self, session, cwd):
        self.s, self.cwd, self.i, self.lines = session, cwd, 0, []

    def _base(self):
        self.i += 1
        return {"sessionId": self.s, "cwd": self.cwd, "timestamp": _ts(self.i),
                "version": "2.1.159", "gitBranch": "main", "isSidechain": False,
                "userType": "external"}

    def human(self, text):
        o = self._base()
        o.update(type="user", isMeta=False,
                 message={"role": "user", "content": text})
        self.lines.append(o)
        return self

    def say(self, text):
        o = self._base()
        o.update(type="assistant",
                 message={"role": "assistant", "model": "claude-opus-4-8",
                          "content": [{"type": "thinking", "thinking": "", "signature": "x"},
                                      {"type": "text", "text": text}]})
        self.lines.append(o)
        return self

    def tool(self, name, inp, result=""):
        o = self._base()
        o.update(type="assistant",
                 message={"role": "assistant", "model": "claude-opus-4-8",
                          "content": [{"type": "tool_use", "id": "t%d" % self.i,
                                       "name": name, "input": inp,
                                       "caller": {"type": "direct"}}]})
        self.lines.append(o)
        r = self._base()
        r.update(type="user", isMeta=False,
                 message={"role": "user", "content": [{"type": "tool_result",
                          "tool_use_id": "t%d" % (self.i - 1), "content": result,
                          "is_error": False}]})
        self.lines.append(r)
        return self

    def compact(self, pre=190000, post=8000):
        o = {"type": "system", "subtype": "compact_boundary",
             "content": "Conversation compacted", "isMeta": False,
             "timestamp": _ts(self.i), "level": "info", "logicalParentUuid": "x",
             "compactMetadata": {"trigger": "auto", "preTokens": pre,
                                 "postTokens": post, "durationMs": 90000}}
        self.lines.append(o)
        return self

    def write(self, name):
        path = os.path.join(HERE, name)
        with open(path, "w") as f:
            for o in self.lines:
                f.write(json.dumps(o) + "\n")
        return path


def exploration_heavy():
    t = T("expl0001-0000-0000-0000-000000000001", "/work/api-gateway")
    t.human("We need to add rate limiting to the API gateway. Think through the "
            "options carefully before writing any code.")
    t.say("Let me weigh the main algorithms before committing: fixed-window "
          "counter, sliding-window log, sliding-window counter, leaky bucket, and "
          "token bucket.")
    t.say("Fixed-window counter is the simplest — one counter per time window. But "
          "it allows a burst of up to 2x the limit across a window boundary (a "
          "client sends the full limit at the end of one window and again at the "
          "start of the next). For an abuse-prevention limiter that boundary burst "
          "is a real hole, so I'm ruling fixed-window out.")
    t.say("Sliding-window log stores a timestamp per request and counts those in "
          "the trailing window. It's accurate, but memory grows O(N) with request "
          "volume per client. At our traffic that's far too much Redis memory, so "
          "I'm rejecting it on memory cost.")
    t.say("Leaky bucket (a queue draining at a fixed rate) smooths output but "
          "forbids short bursts that are legitimately fine for us — clients batch "
          "requests — and it adds queueing latency. Rejecting it because we WANT "
          "to allow controlled bursts, not flatten them.")
    t.tool("Read", {"file_path": "/work/api-gateway/middleware/auth.py"},
           "def auth_middleware(req): ...  # existing middleware chain")
    t.say("Token bucket wins: tokens refill at a steady rate, each request spends "
          "one, and the bucket cap bounds the burst. It's O(1) memory per client "
          "(token count + last-refill timestamp), allows controlled bursts, and "
          "maps cleanly to an atomic Redis Lua script. Decision: token bucket via a "
          "Redis Lua script, refill = limit/window, burst cap = 2x the limit. Open "
          "question: do we rate-limit per-API-key or per-IP behind the CDN? Next "
          "step: write the Lua script in middleware/ratelimit.lua and a thin "
          "wrapper in middleware/ratelimit.py.")
    return t.write("explore_heavy.jsonl")


def decision_heavy():
    t = T("deci0001-0000-0000-0000-000000000002", "/work/analytics")
    t.human("Pick the database for the new events-analytics service and justify it.")
    t.say("Requirements: a flexible event schema, ad-hoc analytical queries, "
          "transactional billing rollups, and ideally something the team already "
          "operates. Candidates: Postgres, MySQL, MongoDB, DynamoDB.")
    t.say("DynamoDB gives effortless scale and ops, but ad-hoc analytical queries "
          "are painful — no joins, rigid GSIs — and it'd be a brand-new operational "
          "model for the team. Our workload is analytical, not key-value lookups, "
          "so I'm rejecting DynamoDB.")
    t.say("MongoDB's flexible documents fit events well, but the billing rollups "
          "need multi-document transactions with strong consistency, and although "
          "Mongo supports them, the team has zero experience operating Mongo in "
          "prod, and analytical queries would lean on the aggregation pipeline "
          "which is harder to maintain. Rejecting on operational-familiarity and "
          "transactional-rollup risk.")
    t.say("That leaves MySQL vs Postgres, both relational and familiar. Postgres "
          "wins decisively: JSONB gives flexible, indexable event payloads; window "
          "functions and CTEs make the analytical queries clean; and we already run "
          "Postgres in production. MySQL's JSON support is weaker and we'd gain "
          "nothing by switching. Decision: PostgreSQL.")
    t.say("Concretely: events table with typed columns (id, type, occurred_at, "
          "actor_id) plus a JSONB payload, partitioned by month for retention; "
          "billing rollups run in a single transaction over a month partition. "
          "Assumption: monthly partitioning is fine for our query patterns. Next "
          "step: write the schema migration and the partition-management job.")
    return t.write("decision_heavy.jsonl")


def long_compacted():
    t = T("long0001-0000-0000-0000-000000000003", "/work/orders")
    t.human("Design the order-management service from scratch.")
    t.say("The pivotal early choice is event-sourcing vs CRUD. Compliance requires "
          "a complete, tamper-evident history of every order state change. A CRUD "
          "table with a bolt-on audit log is easy to get out of sync and auditors "
          "won't trust it. Event-sourcing makes the event log the source of truth, "
          "giving the audit trail for free plus temporal 'what did this order look "
          "like at time T' queries. The cost is added complexity: projections and "
          "eventual consistency on the read side. Given the hard audit requirement, "
          "DECISION: event-sourcing; REJECTED: CRUD-with-audit-table as fragile and "
          "untrustworthy for compliance.")
    t.say("Defining the core events: OrderPlaced, OrderPaid, OrderShipped, "
          "OrderCancelled, OrderRefunded. Each is immutable and append-only to the "
          "order's stream.")
    for k in range(8):
        t.tool("Write", {"file_path": "/work/orders/events/event_%d.py" % k},
               "wrote event class %d" % k)
        t.say("Implemented event %d with its schema and validation; keeping events "
              "small and self-describing so projections stay simple." % k)
    t.compact(pre=210000, post=9000)
    t.say("Resuming on the read side now. Building a Postgres projection that folds "
          "the event stream into a current-state orders table for fast queries; the "
          "projection is rebuildable from the log, which is the whole point.")
    t.tool("Write", {"file_path": "/work/orders/projections/current_orders.py"},
           "wrote projection")
    t.say("Open question still unresolved: how to handle projection rebuilds "
          "without downtime — likely a shadow table then an atomic swap. Next step: "
          "implement the OrderPaid -> OrderShipped projection transition and the "
          "rebuild-with-shadow-table mechanism.")
    return t.write("long_compacted.jsonl")


def trivial():
    t = T("triv0001-0000-0000-0000-000000000004", "/work/site")
    t.human("Fix the typo in the README title: 'Instalation' should be "
            "'Installation'.")
    t.say("Simple one-line fix.")
    t.tool("Edit", {"file_path": "/work/site/README.md",
                    "old_string": "# Instalation", "new_string": "# Installation"},
           "edited 1 line")
    t.say("Fixed the heading typo. Nothing else to do here.")
    return t.write("trivial.jsonl")


def secrets():
    t = T("secr0001-0000-0000-0000-000000000005", "/work/deploy")
    t.human("Set up the deploy script with our credentials so it can push to prod.")
    t.say("I'll wire the credentials into the deploy environment. Recording the "
          "values we were given so the script can use them.")
    t.tool("Bash", {"command": "cat .env"},
           "OPENAI_API_KEY=sk-proj-" + "AbCd1234EfGh5678IjKl9012MnOp\n"
           "AWS_ACCESS_KEY_ID=AKIA" + "IOSFODNN7EXAMPLE\n"
           "AWS_SECRET_ACCESS_KEY=wJalr" + "XUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n"
           "GITHUB_TOKEN=ghp_" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789\n"
           "DATABASE_URL=postgres://deployer:Sup3r" + "SecretPw99@db.prod/app\n")
    t.say("The deploy uses OPENAI_API_KEY=sk-proj-" + "AbCd1234EfGh5678IjKl9012MnOp and "
          "the AWS pair AWS_SECRET_ACCESS_KEY=wJalr" + "XUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY. "
          "Decision: store these in the secrets manager, not in .env, and inject at "
          "runtime. Next step: move the .env values into Vault and delete the file.")
    return t.write("secrets.jsonl")


def multi_topic():
    t = T("mult0001-0000-0000-0000-000000000006", "/work/app")
    t.human("A few things: the test_orders test is flaky, also add a --dry-run flag "
            "to the deploy CLI, and what color should the new logo be?")
    t.say("Thread 1 — flaky test_orders: the flakiness comes from asserting on "
          "wall-clock ordering of two events written in the same millisecond. "
          "Decision: make the test deterministic by injecting a fixed clock rather "
          "than sleeping. Rejected adding a retry, which would just hide the race.")
    t.tool("Edit", {"file_path": "/work/app/tests/test_orders.py"}, "patched clock")
    t.say("Thread 2 — deploy CLI: adding a --dry-run flag that prints the plan and "
          "skips the actual apply. Straightforward; wiring it through the arg parser "
          "and short-circuiting before the apply step.")
    t.tool("Edit", {"file_path": "/work/app/cli/deploy.py"}, "added --dry-run")
    t.say("Thread 3 — logo color: discussed brand fit; teal reads as both technical "
          "and friendly and matches the existing accent color, so leaning teal "
          "(#1FA39A) over the proposed orange. This one is a preference, not a hard "
          "decision — flagging for design sign-off. Next steps: confirm the flaky "
          "test passes 100 runs, document --dry-run, and get design to approve teal.")
    return t.write("multi_topic.jsonl")


def code_reasoning():
    t = T("code0001-0000-0000-0000-000000000007", "/work/reports")
    t.human("Report generation is slow. Figure out why and fix it.")
    t.say("Profiling generate_report() shows two problems. First, it issues one SQL "
          "query per row to fetch the line items — a classic N+1 — so a 5,000-row "
          "report makes 5,000 round trips. Second, it reloads and re-parses the "
          "YAML config on every call inside the loop.")
    t.tool("Read", {"file_path": "/work/reports/report.py"},
           "for row in rows:\n    items = db.query(item_sql, row.id)\n    cfg = load_config()")
    t.say("Fix: replace the per-row query with a single batched query that pulls all "
          "line items for the report in one round trip, then group them into a dict "
          "by row id in memory. And hoist load_config() out of the loop to call it "
          "once. The thinking: the bottleneck is round-trip count and redundant "
          "parsing, not CPU, so batching plus hoisting should cut it from O(N) "
          "queries to O(1).")
    t.tool("Edit", {"file_path": "/work/reports/report.py",
                    "old_string": "for row in rows:\n    items = db.query(item_sql, row.id)",
                    "new_string": "items_by_row = group_by(db.query(all_items_sql, report_id))\nfor row in rows:\n    items = items_by_row[row.id]"},
           "edited report.py")
    t.say("Decision: batch the query and hoist the config load. Measured 5,000-row "
          "report dropped from ~6s to ~250ms. Open question: should we add a covering "
          "index on line_items(report_id) — likely yes. Next step: add the index "
          "migration and a perf regression test asserting < 1s for 5k rows.")
    return t.write("code_reasoning.jsonl")


def worktree():
    t = T("wtre0001-0000-0000-0000-000000000008", "/work/service")
    t.human("Add a /healthz healthcheck endpoint.")
    t.say("Adding a GET /healthz that returns 200 with a small JSON body once the "
          "DB connection check passes. Decision: keep it dependency-light so load "
          "balancers can poll it cheaply.")
    t.tool("Edit", {"file_path": "/work/service/routes.py"}, "added /healthz")
    t.say("Done. Next step: add readiness vs liveness split if k8s needs it.")
    return t.write("worktree.jsonl")


def empty():
    t = T("empt0001-0000-0000-0000-000000000009", "/work/scratch")
    t.human("hi")
    return t.write("empty.jsonl")


def main():
    made = [exploration_heavy(), decision_heavy(), long_compacted(), trivial(),
            secrets(), multi_topic(), code_reasoning(), worktree(), empty()]
    for p in made:
        n = sum(1 for _ in open(p))
        print("  %-26s %3d lines  %6d bytes" % (os.path.basename(p), n, os.path.getsize(p)))


if __name__ == "__main__":
    main()
