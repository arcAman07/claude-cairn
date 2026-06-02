"""Claude Cairn — launch demo (Manim Community Edition 0.20.1).

Render preview : python3 -m manim -ql assets/cairn_demo.py CairnDemo
Render final   : python3 -m manim -qh assets/cairn_demo.py CairnDemo -o cairn-launch.mp4

Styled as the Claude Code interface: traffic-light buttons, a rounded input box at
the bottom, tool-call dots (●). You TYPE into the input box; on enter the prompt
flies up into the transcript and its tool output appears below it, then the box
clears, exactly like a real Claude Code session. Text/MarkupText only (NO LaTeX).
~42s, no narration. See STORYBOARD.md.

Arc: introduce Claude Cairn (a skill) -> the problem (two unrelated threads in one
chat, lost when the session ends) -> session 1 implements a Transformer from scratch
AND a Soft Actor-Critic agent, /cairn:checkpoint each -> two fresh sessions /cairn:load
each and continue. Checkpoints carry context from one session to the next.
"""
from manim import *

MONO = "JetBrains Mono"
UI = "Avenir Next"

PAGE = "#070809"
TERM = "#0F1113"
TEXT = "#E6E6E6"
DIM = "#8A9098"
CORAL = "#D9785E"
GREEN = "#6BD08A"
RED = "#FF5F57"
STROKE = "#2A2D31"
BOX = "#171A1D"
IBSTROKE = "#3A3F45"


def ml(m, fs=21):
    return MarkupText(m, font=MONO, font_size=fs, color=TEXT)


def cap(s, fs=27, c=DIM, w="MEDIUM"):
    return Text(s, font=UI, font_size=fs, weight=w, color=c)


def user_line(cmd, fs=21):
    p = ml(f'<span foreground="{CORAL}">&gt;</span>', fs)
    t = Text(cmd, font=MONO, font_size=fs, color=TEXT)
    return VGroup(p, t).arrange(RIGHT, buff=0.2, aligned_edge=DOWN)


def cc_window(w, h, title, with_input=False):
    panel = RoundedRectangle(width=w, height=h, corner_radius=0.16, fill_color=TERM,
                             fill_opacity=1, stroke_color=STROKE, stroke_width=2.0)
    by = panel.get_top()[1] - 0.56
    bar = Line([panel.get_left()[0], by, 0], [panel.get_right()[0], by, 0],
               stroke_color=STROKE, stroke_width=2.0)
    lights = VGroup(Dot(radius=0.078, color=RED), Dot(radius=0.078, color="#FEBC2E"),
                    Dot(radius=0.078, color="#28C840")).arrange(RIGHT, buff=0.19)
    lights.move_to([panel.get_left()[0] + 0.48, panel.get_top()[1] - 0.29, 0])
    ttl = ml(f'<span foreground="{DIM}">{title}</span>', 19).next_to(lights, RIGHT, buff=0.36)
    g = VGroup(panel, bar, lights, ttl)
    g.panel = panel
    if with_input:
        ib = RoundedRectangle(width=w - 0.7, height=0.72, corner_radius=0.16, fill_color=BOX,
                              fill_opacity=1, stroke_color=IBSTROKE, stroke_width=1.6)
        ib.move_to([panel.get_center()[0], panel.get_bottom()[1] + 0.56, 0])
        arrow = ml(f'<span foreground="{CORAL}">&gt;</span>', 21)
        arrow.set_y(ib.get_y())
        arrow.set_x(ib.get_left()[0] + 0.4 + arrow.get_width() / 2)
        cursor = Rectangle(width=0.025, height=0.32, fill_color=CORAL, fill_opacity=1,
                           stroke_width=0)
        cursor.set_y(ib.get_y())
        cursor.set_x(arrow.get_right()[0] + 0.16 + cursor.get_width() / 2)
        g.add(ib, arrow, cursor)
        g.ibox = ib
        g.boxarrow = arrow
        g.boxcursor = cursor
    return g


def transcript_tl(win):
    """Live top-left point of a window's transcript area (panel may have moved)."""
    p = win.panel
    return p.get_left()[0] + 0.55, p.get_top()[1] - 0.95


def place_top_left(group, cl, ct):
    group.move_to([cl + group.get_width() / 2, ct - group.get_height() / 2, 0])
    return group


class CairnDemo(Scene):
    def construct(self):
        self.camera.background_color = PAGE
        self.beat0_intro()
        self.clear_stage()
        self.beat1_problem()
        self.clear_stage()
        self.beat2_session1()
        self.clear_stage()
        self.beat3_load()
        self.clear_stage()
        self.beat4_end()

    def clear_stage(self, rt=0.5):
        if self.mobjects:
            self.play(*[FadeOut(m) for m in self.mobjects], run_time=rt)

    # --- input-box typing: type into the box, then send up into the transcript ---
    def start_blink(self, cursor, rate=1.4):
        cursor._bt = 0.0

        def upd(m, dt):
            m._bt += dt
            m.set_opacity(1.0 if (m._bt * rate) % 1.0 < 0.55 else 0.0)

        cursor.add_updater(upd)

    def box_type(self, win, cmd, fs=21, speed=0.045):
        typed = Text(cmd, font=MONO, font_size=fs, color=TEXT)
        typed.set_y(win.ibox.get_y())
        typed.set_x(win.boxarrow.get_right()[0] + 0.16 + typed.get_width() / 2)
        win.boxcursor.clear_updaters()
        self.play(win.boxcursor.animate.set_opacity(0),
                  win.ibox.animate.set_stroke(color=CORAL, width=2.2), run_time=0.15)
        self.play(AddTextLetterByLetter(typed), run_time=max(0.7, len(cmd) * speed))
        return typed

    def box_send(self, win, typed, slot, rt=0.5):
        cl = win.panel.get_left()[0] + 0.55
        arrow_copy = win.boxarrow.copy()
        self.add(arrow_copy)
        grp = VGroup(arrow_copy, typed)
        self.play(grp.animate.move_to([cl + grp.get_width() / 2, slot.get_y(), 0]), run_time=rt)
        self.play(win.ibox.animate.set_stroke(color=IBSTROKE, width=1.6),
                  win.boxcursor.animate.set_opacity(1), run_time=0.15)
        self.start_blink(win.boxcursor)
        return grp

    # 0 — introduce the tool (logo + name + "it's a skill")
    def beat0_intro(self):
        logo = ImageMobject("assets/logo.png").scale(0.42)
        name = Text("Claude Cairn", font=UI, font_size=74, weight="BOLD", color=TEXT)
        sub = Text("A context-checkpoint skill for Claude Code", font=UI, font_size=28,
                   weight="MEDIUM", color=CORAL)
        name.next_to(logo, DOWN, buff=0.42)
        sub.next_to(name, DOWN, buff=0.3)
        Group(logo, name, sub).move_to(ORIGIN)
        self.play(FadeIn(logo, shift=UP * 0.18), run_time=0.8)
        self.play(FadeIn(name, shift=UP * 0.1), run_time=0.6)
        self.play(FadeIn(sub), run_time=0.5)
        self.wait(1.2)

    # 1 — the problem
    def beat1_problem(self):
        head = cap("The problem", 32, TEXT, "BOLD").to_edge(UP, buff=0.55)
        win = cc_window(11.6, 4.7, "claude code · one session").move_to(DOWN * 0.1)
        self.play(FadeIn(head, shift=DOWN * 0.15), run_time=0.5)
        self.play(FadeIn(win, shift=UP * 0.12), run_time=0.6)
        rows = VGroup(
            ml(f'<span foreground="{CORAL}">&gt;</span> implement a Transformer from scratch', 22),
            ml(f'<span foreground="{CORAL}">&gt;</span> also: implement Soft Actor-Critic (SAC)', 22),
            ml(f'<span foreground="{DIM}">  two unrelated threads, one chat</span>', 22),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.34)
        cl, ct = transcript_tl(win)
        place_top_left(rows, cl, ct - 0.15)
        for r in rows:
            self.play(FadeIn(r, shift=RIGHT * 0.12), run_time=0.6)
            self.wait(0.7)
        self.wait(1.0)
        lost = ml(f'<span foreground="{RED}">  ✕ session ends, both threads gone</span>', 22)
        lost.next_to(rows, DOWN, buff=0.4, aligned_edge=LEFT)
        self.play(win.panel.animate.set_opacity(0.45), rows.animate.set_opacity(0.4),
                  FadeIn(lost), run_time=0.8)
        self.wait(1.0)
        c = cap("many threads in one chat. you can't split them out, or continue them later.",
                25, DIM).next_to(win, DOWN, buff=0.32)
        self.play(FadeIn(c), run_time=0.5)
        self.wait(2.0)

    # 2 — session 1: implement + checkpoint each (type into the box, send up)
    def beat2_session1(self):
        head = cap("Cairn: checkpoint each thread", 30, TEXT, "BOLD").to_edge(UP, buff=0.42)
        win = cc_window(12.8, 6.3, "claude code · session 1", with_input=True).move_to(DOWN * 0.25)
        self.play(FadeIn(head, shift=DOWN * 0.15), run_time=0.5)
        self.play(FadeIn(win, shift=UP * 0.1), run_time=0.6)
        self.start_blink(win.boxcursor)
        self.wait(0.2)
        spec = [
            ("user", "implement a Transformer from scratch"),
            ("tool", f'<span foreground="{CORAL}">●</span> transformer.py · multi-head attention + FFN'),
            ("user", "/cairn:checkpoint transformer"),
            ("ok", f'<span foreground="{GREEN}">✓ Saved checkpoint · transformer</span>'),
            ("user", "also: implement Soft Actor-Critic (SAC)"),
            ("tool", f'<span foreground="{CORAL}">●</span> sac.py · actor + twin critics + entropy temp'),
            ("user", "/cairn:checkpoint sac"),
            ("ok", f'<span foreground="{GREEN}">✓ Saved checkpoint · sac</span>'),
        ]
        lines = [user_line(t, 21) if k == "user" else ml(t, 21) for k, t in spec]
        transcript = VGroup(*lines).arrange(DOWN, aligned_edge=LEFT, buff=0.22)
        cl, ct = transcript_tl(win)
        place_top_left(transcript, cl, ct)
        for (kind, txt), slot in zip(spec, lines):
            if kind == "user":
                typed = self.box_type(win, txt)
                self.wait(0.2)
                self.box_send(win, typed, slot)
            else:
                self.play(FadeIn(slot, shift=RIGHT * 0.06), run_time=0.4)
                self.wait(0.35 if "✓" in txt else 0.18)
        c = cap("two threads, two checkpoints, cleanly separated.", 26, DIM).next_to(win, DOWN, buff=0.26)
        self.play(FadeIn(c), run_time=0.5)
        self.wait(1.2)
        win.boxcursor.clear_updaters()

    # 3 — carry context to fresh sessions
    def beat3_load(self):
        head = cap("Carry the context to a fresh session", 30, TEXT, "BOLD").to_edge(UP, buff=0.42)
        self.play(FadeIn(head, shift=DOWN * 0.15), run_time=0.5)
        divider = DashedLine(UP * 2.6, DOWN * 3.0, color=STROKE, stroke_width=2)
        L = cc_window(6.7, 5.5, "claude code · session 2", with_input=True).move_to(LEFT * 3.5 + DOWN * 0.55)
        R = cc_window(6.7, 5.5, "claude code · session 3", with_input=True).move_to(RIGHT * 3.5 + DOWN * 0.55)
        self.play(FadeIn(L, shift=RIGHT * 0.1), FadeIn(R, shift=LEFT * 0.1), Create(divider), run_time=0.7)
        self.start_blink(L.boxcursor)
        self.start_blink(R.boxcursor)
        self.wait(0.2)
        lspec = [
            ("user", "/cairn:load transformer"),
            ("ml", f'<span foreground="{DIM}">  resumed ·</span> transformer'),
            ("ml", f'<span foreground="{DIM}">  summary:</span> MHA + FFN blocks, pre-norm'),
            ("ml", f'<span foreground="{DIM}">  next:</span> add positional encoding + train'),
            ("ml", f'<span foreground="{GREEN}">  ✓ shapes check out · no errors</span>'),
        ]
        rspec = [
            ("user", "/cairn:load sac"),
            ("ml", f'<span foreground="{DIM}">  resumed ·</span> sac'),
            ("ml", f'<span foreground="{DIM}">  summary:</span> actor + twin critics + temp'),
            ("ml", f'<span foreground="{DIM}">  next:</span> add replay buffer + train loop'),
            ("ml", f'<span foreground="{CORAL}">●</span> training · returns climbing'),
        ]
        lb = VGroup(*[user_line(t, 19) if k == "user" else ml(t, 19) for k, t in lspec])
        rb = VGroup(*[user_line(t, 19) if k == "user" else ml(t, 19) for k, t in rspec])
        lb.arrange(DOWN, aligned_edge=LEFT, buff=0.28)
        rb.arrange(DOWN, aligned_edge=LEFT, buff=0.28)
        place_top_left(lb, *transcript_tl(L))
        place_top_left(rb, *transcript_tl(R))
        # type both /cairn:load commands into their boxes, then send both up
        self.box_type_parallel(L, lspec[0][1], R, rspec[0][1])
        self.wait(0.15)
        for i in range(1, 5):
            self.play(FadeIn(lb[i], shift=RIGHT * 0.06), FadeIn(rb[i], shift=RIGHT * 0.06), run_time=0.45)
            self.wait(0.15)
        c = cap("checkpoints carry your context from one session to the next.", 25, CORAL)
        c.next_to(VGroup(L, R), DOWN, buff=0.28)
        self.play(FadeIn(c), run_time=0.5)
        self.wait(1.6)
        L.boxcursor.clear_updaters()
        R.boxcursor.clear_updaters()

    def box_type_parallel(self, winL, cmdL, winR, cmdR, fs=19):
        """Type two commands into two boxes at once, then fly both up to slot 0."""
        tL = Text(cmdL, font=MONO, font_size=fs, color=TEXT)
        tL.set_y(winL.ibox.get_y())
        tL.set_x(winL.boxarrow.get_right()[0] + 0.16 + tL.get_width() / 2)
        tR = Text(cmdR, font=MONO, font_size=fs, color=TEXT)
        tR.set_y(winR.ibox.get_y())
        tR.set_x(winR.boxarrow.get_right()[0] + 0.16 + tR.get_width() / 2)
        winL.boxcursor.clear_updaters()
        winR.boxcursor.clear_updaters()
        self.play(winL.boxcursor.animate.set_opacity(0), winR.boxcursor.animate.set_opacity(0),
                  winL.ibox.animate.set_stroke(color=CORAL, width=2.2),
                  winR.ibox.animate.set_stroke(color=CORAL, width=2.2), run_time=0.15)
        self.play(AddTextLetterByLetter(tL), AddTextLetterByLetter(tR), run_time=1.1)
        self.wait(0.2)
        clL = winL.panel.get_left()[0] + 0.55
        clR = winR.panel.get_left()[0] + 0.55
        aL, aR = winL.boxarrow.copy(), winR.boxarrow.copy()
        self.add(aL, aR)
        gL, gR = VGroup(aL, tL), VGroup(aR, tR)
        yL = transcript_tl(winL)[1]
        yR = transcript_tl(winR)[1]
        self.play(gL.animate.move_to([clL + gL.get_width() / 2, yL, 0]),
                  gR.animate.move_to([clR + gR.get_width() / 2, yR, 0]), run_time=0.5)
        self.play(winL.ibox.animate.set_stroke(color=IBSTROKE, width=1.6),
                  winR.ibox.animate.set_stroke(color=IBSTROKE, width=1.6),
                  winL.boxcursor.animate.set_opacity(1), winR.boxcursor.animate.set_opacity(1),
                  run_time=0.15)
        self.start_blink(winL.boxcursor)
        self.start_blink(winR.boxcursor)
        return gL, gR

    # 4 — end card (centered, even rhythm)
    def beat4_end(self):
        logo = ImageMobject("assets/logo.png").scale(0.44)
        name = Text("Claude Cairn", font=UI, font_size=70, weight="BOLD", color=TEXT)
        tag = Text("Context, shared across sessions.", font=UI, font_size=30, weight="MEDIUM", color=CORAL)
        cmds = ml(f'<span foreground="{DIM}">/cairn:checkpoint    /cairn:load    /cairn:find    /cairn:checkpoints</span>', 20)
        repo = ml(f'<span foreground="{CORAL}">github.com/arcAman07/claude-cairn</span>', 24)
        name.next_to(logo, DOWN, buff=0.4)
        tag.next_to(name, DOWN, buff=0.28)
        cmds.next_to(tag, DOWN, buff=0.4)
        repo.next_to(cmds, DOWN, buff=0.34)
        Group(logo, name, tag, cmds, repo).move_to(ORIGIN)
        self.play(FadeIn(logo, shift=UP * 0.18), run_time=0.8)
        self.play(FadeIn(name, shift=UP * 0.1), run_time=0.6)
        self.play(FadeIn(tag), run_time=0.5)
        self.play(FadeIn(cmds), run_time=0.5)
        self.play(FadeIn(repo, shift=UP * 0.06), run_time=0.5)
        self.wait(2.4)
