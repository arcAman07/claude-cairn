"""Claude Cairn — launch demo (Manim Community Edition 0.20.1).

Render preview : python3 -m manim -ql assets/cairn_demo.py CairnDemo
Render final   : python3 -m manim -qh assets/cairn_demo.py CairnDemo -o cairn-launch.mp4

NO LaTeX (not installed): Text only. Brand accent teal #1FA39A on a dark bg; the
real assets/logo.png is embedded on the end card. ~38s, no narration.

Story (see STORYBOARD.md): on a web project you design TWO features (auth + database)
in one session, /cairn:checkpoint each into its own portable note, then open TWO
terminals and /cairn:load one note in each — so both fresh sessions start with the
design context already loaded and you implement the features in parallel.
"""
from manim import *

UI = "Avenir Next"
MONO = "Menlo"

BG = "#10201E"
TEAL = "#1FA39A"
TEXT = "#EAF1F0"
MUTED = "#7E938F"
PANEL = "#182B29"
BORDER = "#2E4744"

FULL_W, FULL_H = 10.0, 5.0
WIN_Y = DOWN * 0.32

FEATURES = [
    dict(name="auth", design="sessions → JWT + refresh",
         summary="JWT auth + refresh tokens", decision="JWT, not server sessions",
         nxt="build POST /auth/login"),
    dict(name="database", design="Postgres, raw SQL",
         summary="Postgres data layer", decision="raw SQL, not an ORM",
         nxt="write schema.sql"),
]


def ui(s, fs, color=TEXT, w="MEDIUM"):
    return Text(s, font=UI, font_size=fs, weight=w, color=color)


def mono(s, fs, color=TEXT, w="NORMAL"):
    return Text(s, font=MONO, font_size=fs, weight=w, color=color)


def heading(s):
    return ui(s, 46, TEXT, "BOLD").to_edge(UP, buff=0.66)


def caption(s, color=MUTED):
    return ui(s, 28, color, "MEDIUM")


def window(w, h, title):
    p = RoundedRectangle(width=w, height=h, corner_radius=0.18, fill_color=PANEL,
                         fill_opacity=1, stroke_color=BORDER, stroke_width=2.0)
    by = p.get_top()[1] - 0.62
    bar = Line([p.get_left()[0], by, 0], [p.get_right()[0], by, 0],
               stroke_color=BORDER, stroke_width=2.0)
    dots = VGroup(*[Dot(radius=0.072, color=MUTED) for _ in range(3)]).arrange(RIGHT, buff=0.15)
    dots.move_to([p.get_left()[0] + 0.46, p.get_top()[1] - 0.32, 0])
    cap = mono(title, 20, MUTED).next_to(dots, RIGHT, buff=0.32)
    g = VGroup(p, bar, dots, cap)
    g.panel = p
    return g


def block_in(group, panel, right=0.55, down=1.2):
    group.next_to([panel.get_left()[0], panel.get_top()[1], 0], DOWN + RIGHT, buff=0)
    group.shift(RIGHT * right + DOWN * down)
    return group


def feature_note(f, w=4.4, h=3.95):
    pad = 0.42
    card = RoundedRectangle(width=w, height=h, corner_radius=0.16, fill_color=PANEL,
                            fill_opacity=1, stroke_color=BORDER, stroke_width=2.0)
    title = ui(f["name"], 24, TEXT, "BOLD")
    tag = mono("#feature", 15, TEAL)
    head = VGroup(title, tag).arrange(RIGHT, buff=0.28, aligned_edge=DOWN)
    rule = Line(ORIGIN, RIGHT * (w - 2 * pad), color=BORDER, stroke_width=2)

    def sec(lbl, val, vc=TEXT):
        return VGroup(ui(lbl, 14, MUTED, "BOLD"),
                      mono(val, 17, vc)).arrange(DOWN, aligned_edge=LEFT, buff=0.06)

    col = VGroup(head, rule, sec("Summary", f["summary"]),
                 sec("Decisions", f["decision"]),
                 sec("Next", f["nxt"], TEAL)).arrange(DOWN, aligned_edge=LEFT, buff=0.2)
    col.move_to(card.get_center())
    g = VGroup(card, col)
    g.card = card
    g.col = col
    return g


class CairnDemo(Scene):
    def construct(self):
        self.camera.background_color = BG
        self.beat1_design()
        self.beat2_checkpoint()
        self.clear_stage()
        self.beat3_terminals()
        self.clear_stage()
        self.beat4_end()

    def clear_stage(self, rt=0.55):
        if self.mobjects:
            self.play(*[FadeOut(m) for m in self.mobjects], run_time=rt)

    # 1 — design two features in one session
    def beat1_design(self):
        self.head = heading("Design a couple of features")
        self.win = window(FULL_W, FULL_H, "claude code · web-app").move_to(WIN_Y)
        self.play(FadeIn(self.head, shift=DOWN * 0.2), run_time=0.7)
        self.play(FadeIn(self.win, shift=UP * 0.2), run_time=0.7)
        row_a = VGroup(mono("auth", 30, TEAL, "BOLD"),
                       mono("  sessions → JWT + refresh", 30, TEXT)).arrange(RIGHT, buff=0.2, aligned_edge=DOWN)
        row_b = VGroup(mono("database", 30, TEAL, "BOLD"),
                       mono("  Postgres, raw SQL", 30, TEXT)).arrange(RIGHT, buff=0.2, aligned_edge=DOWN)
        ls = VGroup(
            mono("web app · v1 — designing two features", 30, MUTED),
            row_a, row_b,
            mono("designed both — time to build", 30, MUTED),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.46)
        block_in(ls, self.win.panel, right=0.6, down=1.25)
        self.play(FadeIn(ls[0], shift=RIGHT * 0.15), run_time=0.5)
        self.wait(0.15)
        self.play(FadeIn(ls[1], shift=RIGHT * 0.15), run_time=0.55)
        self.wait(0.12)
        self.play(FadeIn(ls[2], shift=RIGHT * 0.15), run_time=0.55)
        self.wait(0.12)
        self.play(FadeIn(ls[3], shift=RIGHT * 0.15), run_time=0.5)
        self.wait(2.6)
        self.lines = ls

    # 2 — checkpoint each into its own note
    def beat2_checkpoint(self):
        nh = heading("Checkpoint each one")
        self.play(ReplacementTransform(self.head, nh), run_time=0.6)
        self.head = nh
        cue = VGroup(
            mono("/cairn:checkpoint auth", 22, TEAL),
            mono("/cairn:checkpoint database", 22, TEAL),
        ).arrange(DOWN, buff=0.16, aligned_edge=LEFT).next_to(self.win, DOWN, buff=0.3)
        self.play(AddTextLetterByLetter(cue[0]), run_time=0.6)
        self.play(AddTextLetterByLetter(cue[1]), run_time=0.6)
        self.wait(0.3)
        nA = feature_note(FEATURES[0]).move_to(LEFT * 3.5 + WIN_Y)
        nB = feature_note(FEATURES[1]).move_to(RIGHT * 3.5 + WIN_Y)
        self.play(FadeOut(self.win), FadeOut(self.lines), FadeOut(cue),
                  FadeIn(nA.card, shift=UP * 0.1), FadeIn(nB.card, shift=UP * 0.1), run_time=0.6)
        self.play(LaggedStart(*[FadeIn(m, shift=UP * 0.05) for m in [*nA.col, *nB.col]],
                              lag_ratio=0.07), run_time=2.2)
        cap = caption("two checkpoints — one per feature").next_to(VGroup(nA, nB), DOWN, buff=0.34)
        self.play(FadeIn(cap), run_time=0.5)
        self.wait(3.0)

    # 3 — load each in its own terminal, build in parallel
    def beat3_terminals(self):
        head = heading("Load each in its own terminal")
        self.play(FadeIn(head, shift=DOWN * 0.2), run_time=0.7)
        wins = [window(6.3, 4.4, "claude code · " + f["name"]).move_to(
            (LEFT if i == 0 else RIGHT) * 3.55 + DOWN * 0.42) for i, f in enumerate(FEATURES)]
        self.play(*[FadeIn(w, shift=UP * 0.12) for w in wins], run_time=0.7)
        self.wait(0.6)
        flyers = [feature_note(f, w=3.0, h=2.9).scale(0.55).move_to(wins[i].get_center() + UP * 1.95)
                  for i, f in enumerate(FEATURES)]
        self.play(*[FadeIn(n, shift=DOWN * 0.15) for n in flyers], run_time=0.5)
        self.wait(0.2)
        loaded = []
        for i, f in enumerate(FEATURES):
            items = [("$ /cairn:load " + f["name"], TEXT, "BOLD"),
                     ("context loaded", TEAL, "BOLD"),
                     ("next: " + f["nxt"], MUTED, "NORMAL"),
                     ("implementing…", TEXT, "NORMAL")]
            blk = VGroup(*[mono(s, 21, c, w) for (s, c, w) in items]).arrange(
                DOWN, aligned_edge=LEFT, buff=0.32)
            block_in(blk, wins[i].panel, right=0.5, down=1.15)
            loaded.append(blk)
        self.play(*[flyers[i].animate.move_to(loaded[i].get_center()).scale(0.35).set_opacity(0)
                    for i in range(2)], run_time=0.9)
        for r in range(4):
            self.play(*[FadeIn(loaded[i][r], shift=RIGHT * 0.1) for i in range(2)], run_time=0.6)
            self.wait(0.16)
        cap = caption("design context already loaded — build in parallel", TEAL).next_to(
            VGroup(*wins), DOWN, buff=0.34)
        self.play(FadeIn(cap), run_time=0.5)
        self.wait(3.2)

    # 4 — end card
    def beat4_end(self):
        logo = ImageMobject("assets/logo.png").scale(0.55).move_to(UP * 1.7)
        name = ui("Claude Cairn", 70, TEXT, "BOLD").next_to(logo, DOWN, buff=0.45)
        tag = ui("Save the thinking. Resume it anywhere.", 30, TEAL, "MEDIUM").next_to(name, DOWN, buff=0.26)
        one = ui("Portable, distilled session notes for Claude Code.", 23, MUTED).next_to(tag, DOWN, buff=0.18)
        cmds = mono("/cairn:checkpoint    /cairn:load    /cairn:find    /cairn:checkpoints",
                    20, MUTED).next_to(one, DOWN, buff=0.4)
        self.play(FadeIn(logo, shift=UP * 0.2), run_time=0.8)
        self.play(FadeIn(name, shift=UP * 0.1), run_time=0.6)
        self.play(FadeIn(tag), run_time=0.5)
        self.play(FadeIn(one), FadeIn(cmds), run_time=0.6)
        self.wait(3.6)
