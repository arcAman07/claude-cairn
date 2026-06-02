"""Original royalty-free ambient bed for the Cairn launch video.

Soft sustained pads (Cmaj7 -> Em7 -> Am7 -> Fmaj7) + a gentle piano arpeggio +
light reverb. No drums, no lyrics. 100% generated here, so it carries no copyright
or attribution. Standard library + numpy only.

Full pipeline (render -> music -> mux):
    python3 -m manim -qh assets/cairn_demo.py CairnDemo            # -> .../1080p60/CairnDemo.mp4
    DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 .../CairnDemo.mp4)
    python3 assets/cairn_music.py "$DUR"                           # -> /tmp/cairn_music.wav
    ffmpeg -y -i .../CairnDemo.mp4 -i /tmp/cairn_music.wav \
        -c:v copy -c:a aac -b:a 192k -shortest assets/cairn-launch.mp4
"""
import sys
import wave
import numpy as np

SR = 44100
DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 39.2
N = int(SR * DUR)


def midi(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


# smooth, soothing loop: Cmaj7 -> Em7 -> Am7 -> Fmaj7  (close voicings, mid register)
CHORDS = [
    [48, 52, 55, 59],   # Cmaj7  C3 E3 G3 B3
    [52, 55, 59, 62],   # Em7    E3 G3 B3 D4
    [57, 60, 64, 67],   # Am7    A3 C4 E4 G4
    [53, 57, 60, 64],   # Fmaj7  F3 A3 C4 E4
]
CHORD_LEN = 4.0  # seconds per chord
XF = 0.7         # crossfade between chords


def osc(freq, n, detune=0.0):
    """Warm pad voice: detuned tone with soft harmonics + slow vibrato."""
    tt = np.arange(n) / SR
    f = freq * (1.0 + detune)
    vib = 1.0 + 0.0025 * np.sin(2 * np.pi * 0.18 * tt)
    s = (np.sin(2 * np.pi * f * tt * vib)
         + 0.35 * np.sin(2 * np.pi * 2 * f * tt)
         + 0.18 * np.sin(2 * np.pi * 3 * f * tt))
    return s / 1.53


def trapz_env(n, fade):
    e = np.ones(n)
    k = int(SR * fade)
    if k > 0:
        ramp = np.linspace(0, 1, k)
        e[:k] = ramp
        e[-k:] = ramp[::-1]
    return e


def piano(freq, n):
    """Piano-ish tone: fast attack, exponential decay, a few harmonics."""
    tt = np.arange(n) / SR
    env = np.exp(-tt * 3.2) * (1 - np.exp(-tt * 300))
    s = (np.sin(2 * np.pi * freq * tt)
         + 0.5 * np.sin(2 * np.pi * 2 * freq * tt)
         + 0.25 * np.sin(2 * np.pi * 3 * freq * tt)
         + 0.12 * np.sin(2 * np.pi * 4 * freq * tt))
    return (s / 1.87) * env


def reverb(x, decay=1.1, wet=0.28, seed=1):
    """Light hall via FFT convolution with a synthetic exponential impulse."""
    rng = np.random.RandomState(seed)
    ir_n = int(SR * decay)
    ir = rng.randn(ir_n) * np.exp(-np.arange(ir_n) / (SR * decay / 4.0))
    ir[: int(SR * 0.01)] = 0
    ir /= np.max(np.abs(ir))
    L = 1
    while L < len(x) + len(ir):
        L *= 2
    wetsig = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(ir, L))[: len(x)]
    wetsig /= (np.max(np.abs(wetsig)) + 1e-9)
    return (1 - wet) * x + wet * wetsig


def main():
    padL = np.zeros(N)
    padR = np.zeros(N)
    sub = np.zeros(N)
    arp = np.zeros(N)
    n_chords = int(np.ceil(DUR / CHORD_LEN))
    for i in range(n_chords):
        chord = CHORDS[i % len(CHORDS)]
        s0 = int(SR * max(0.0, i * CHORD_LEN - XF / 2))
        if s0 >= N:
            break
        nlen = min(int(SR * (CHORD_LEN + XF)), N - s0)
        env = trapz_env(nlen, XF) * 0.075
        for note in chord:
            f = midi(note)
            padL[s0:s0 + nlen] += osc(f, nlen, +0.0012) * env
            padR[s0:s0 + nlen] += osc(f, nlen, -0.0012) * env
        tt = np.arange(nlen) / SR
        sub[s0:s0 + nlen] += np.sin(2 * np.pi * midi(chord[0] - 12) * tt) * env * 1.3
        for j, note in enumerate(chord):
            a0 = int(SR * (i * CHORD_LEN + j * 1.0))
            if a0 >= N:
                break
            dur = min(int(SR * 1.6), N - a0)
            arp[a0:a0 + dur] += piano(midi(note + 12), dur) * 0.16

    L = reverb(padL + sub + arp, seed=1)
    R = reverb(padR + sub + arp, seed=2)

    fi, fo = int(SR * 2.0), int(SR * 3.5)
    fade = np.ones(N)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[-fo:] = np.linspace(1, 0, fo)
    L *= fade
    R *= fade

    stereo = np.tanh(np.stack([L, R], axis=1) * 1.1)
    stereo /= (np.max(np.abs(stereo)) + 1e-9)
    stereo *= 0.34  # subtle background level (sits low under the video)
    pcm = (stereo * 32767).astype(np.int16)
    with wave.open("/tmp/cairn_music.wav", "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("wrote /tmp/cairn_music.wav  %.2fs" % DUR)


if __name__ == "__main__":
    main()
