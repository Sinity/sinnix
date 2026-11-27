"""demo.py: a synthetic song and stand-in takes, so every stage of the kit can be tried in minutes, offline and free.

  python examples/demo.py audio DEMO    # DEMO/: lyric.txt, book.json, audio/{song,lead,rest,group}.wav, frames, a sheet
  python examples/demo.py takes DEMO    # after `shotbook build`: takes/<id>/take-1.mp4, each shot's own window sung
                                        # 0.12 s late and 4% slow (what real takes do), over its first frame
  python examples/demo.py audio DEMO --video-model grok-imagine-video-1.5    # the same, the book set for a first-frame
                                        # model: its stand-in takes have a sound of their own (a model that cannot hear
                                        # the song invents one) and a stand-in mouth measure that opens on their phrases
                                        # 0.12 s late and 4% slow, so sync places them by her lips

The "voice" is a buzz shaped by each syllable's vowel and placed on the beat by the kit's own scansion model; the
pictures are flat colour cards. Nothing here looks or sounds like a film: it only exercises the method.
"""
import json, pathlib, shutil, subprocess, sys
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from claudia_kit import lyric
from claudia_kit.common import write_wav

SR, BPM, BARS = 44100, 100.0, 20
BAR = 240 / BPM
FORMANTS = {'AA': (730, 1090), 'AE': (660, 1720), 'AH': (640, 1190), 'AO': (570, 840), 'AW': (700, 1100), 'AY': (700, 1700),
            'EH': (530, 1840), 'ER': (490, 1350), 'EY': (450, 2000), 'IH': (390, 1990), 'IY': (270, 2290), 'OW': (450, 900),
            'OY': (500, 1000), 'UH': (440, 1020), 'UW': (300, 870)}
MELODY = [392, 440, 392, 349, 330, 349, 392, 294]


def syllable(v, f0, dur, sung, rng):
    """a vowel: harmonics under two formant peaks, a soft attack and release, a consonant tick at its start."""
    t = np.arange(int(dur * SR)) / SR; F1, F2 = FORMANTS.get(v, (500, 1500))
    f = f0 * (1 + (0.012 * np.sin(2 * np.pi * 5.5 * t) if sung else 0)); ph = 2 * np.pi * np.cumsum(f) / SR; y = np.zeros_like(t)
    for k in range(1, int(5000 / f0)):
        y += (np.exp(-((k * f0 - F1) / 120) ** 2) + 0.7 * np.exp(-((k * f0 - F2) / 160) ** 2) + 0.04 / k) * np.sin(k * ph)
    env = np.minimum(1, np.minimum(t / 0.02, (dur - t) / 0.04)).clip(0)
    y = y * env / (np.abs(y).max() + 1e-9); n = min(len(y), int(0.015 * SR)); y[:n] += 0.15 * rng.standard_normal(n)
    return y


def sing(out, text, mode, t0, bars, pitch, rng, gain=0.5):
    """lay one line into `out`, its syllables where the scansion model puts them on the grid."""
    r = lyric.score_line(text, mode, bars=bars, bpm=BPM); syl = r['syl']; q = BAR / 16
    for i, s in enumerate(syl):
        a = t0 + s['t'] * q; nxt = syl[i + 1]['t'] * q + t0 if i + 1 < len(syl) else a + 4 * q
        f0 = (MELODY[i % len(MELODY)] if mode == 'sung' else 200 + 25 * s['P']) * pitch
        y = syllable(s['v'], f0, max(0.08, min(nxt - a - 0.03, 0.7)), mode == 'sung', rng) * gain * (0.6 + 0.4 * s['P'])
        i0 = int(a * SR); out[i0:i0 + len(y)] += y[:max(0, len(out) - i0)]


def audio(demo, video_model=None):
    here = pathlib.Path(__file__).parent; demo.mkdir(parents=True, exist_ok=True)
    for f in ('lyric.txt', 'book.json'): shutil.copy(here / f, demo / f)
    if video_model:
        book = json.loads((demo / 'book.json').read_text()); book['video_model'] = video_model
        (demo / 'book.json').write_text(json.dumps(book, indent=1, ensure_ascii=False) + '\n')
    secs = lyric.parse((here / 'lyric.txt').read_text()); rng = np.random.default_rng(7); n = int(BARS * BAR * SR)
    lead, group, drums = np.zeros(n), np.zeros(n), np.zeros(n)
    t = 2 * BAR                                    # each line in its own slot (two bars a verse line, one a chorus part)
    for line in secs[0][2]: sing(lead, line, 'spoken', t + 0.6, 2, 1.0, rng); t += 2.5 * BAR      # with half a bar of air
    for line in secs[1][2]:                        # the group asks, she answers
        q, a = line[1:line.index(')')], line[line.index(')') + 1:].strip()
        for p in (0.5, 0.63, 0.75): sing(group, q, 'chant', t + 0.6, 1, p, rng, 0.25)
        sing(lead, a, 'sung', t + 1.5 * BAR + 0.6, 1, 1.0, rng); t += 3 * BAR
    t = np.arange(int(0.3 * SR)) / SR; kick = np.sin(2 * np.pi * np.cumsum(45 + 65 * np.exp(-t / 0.03)) / SR) * np.exp(-t / 0.08)
    hat = rng.standard_normal(int(0.03 * SR)); hat = np.diff(hat, prepend=0) * np.exp(-np.arange(len(hat)) / (0.008 * SR)) * 0.25
    for b in range(int(BARS * BAR / (60 / BPM))):
        i = int(b * 60 / BPM * SR); drums[i:i + len(kick)] += 0.8 * kick[:max(0, n - i)]
        for h in (0, 0.5):
            j = int((b + h) * 60 / BPM * SR); drums[j:j + len(hat)] += hat[:max(0, n - j)]
    rest = drums + group; song = lead + rest; g = 10 ** (-1 / 20) / np.abs(song).max()
    for name, y in (('song', song), ('lead', lead), ('rest', rest), ('group', group)):
        write_wav(demo / 'audio' / f'{name}.wav', np.repeat((y * g)[:, None], 2, 1), SR)
    (demo / 'frames').mkdir(exist_ok=True); (demo / 'refs').mkdir(exist_ok=True)
    cards = {'S1': '0x24435a', 'S2': '0x3b4d63', 'Q1': '0x5a3b24', 'A1': '0x2f5446', 'Q2': '0x4a2f54', 'A2': '0x54462f'}
    for sid, c in list(cards.items()) + [('sheet', '0x777777')]:
        out = demo / ('refs/sheet.png' if sid == 'sheet' else f'frames/{sid}.png')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'color=c={c}:s=1280x720', '-vf',
                        'drawbox=x=520:y=160:w=240:h=480:color=white@0.35:t=fill,drawbox=x=580:y=90:w=120:h=120:color=white@0.5:t=fill',
                        '-frames:v', '1', str(out)], check=True)
    print(f"wrote {demo}: a {BARS * BAR:.1f} s song at {BPM:g} BPM with its stems, six first frames and a stand-in sheet")


def mouth(job, fps=24):
    """a stand-in for what the face landmarker reads off a take (sync mouth): her mouth opening per frame, open through
    each sung phrase of the window 0.12 s late and 4% slow (opening 0.1 s before the voice), shut elsewhere."""
    c = np.arange(int(job['duration'] * fps)) / fps; t = (c - 0.12) * 0.96; m = np.full(len(c), 0.006)
    for a, b, _ in job['phrases']:
        on = (t >= a - 0.1) & (t <= b); m[on] = 0.07 + 0.04 * np.abs(np.sin(7 * c[on]))
    return dict(fps=fps, open=[round(float(v), 4) for v in m], found=1.0)


def takes(demo):
    for jf in sorted((demo / 'build' / 'jobs').glob('*.json')):
        job = json.loads(jf.read_text()); out = demo / 'takes' / job['id'] / 'take-1.mp4'
        if out.exists(): continue
        out.parent.mkdir(parents=True, exist_ok=True); D = job['duration']
        deaf = job.get('form') == 'first_frame' and job['kind'] == 'sung'      # it never heard the song: it makes its own sound
        vid = ['-framerate', '24', '-loop', '1', '-i', str(demo / job['first_frame'])]
        aud = ['-i', str(demo / job['audio'][0])] if job['audio'] else ['-f', 'lavfi', '-i', 'sine=frequency=220:sample_rate=48000'] if deaf else []
        af = ['-map', '1:a', '-af', 'adelay=120|120,atempo=0.96,apad', '-c:a', 'aac'] if job['audio'] else \
            ['-map', '1:a', '-af', 'volume=0.1', '-c:a', 'aac'] if deaf else []
        subprocess.run(['ffmpeg', '-v', 'error', '-y', *vid, *aud, '-map', '0:v', *af, '-vf',
                        "zoompan=z='min(zoom+0.0007,1.2)':d=1:s=1280x720:fps=24,format=yuv420p", '-t', str(D),
                        '-c:v', 'libx264', '-preset', 'veryfast', str(out)], check=True)
        if deaf: (out.parent / 'take-1.mouth.json').write_text(json.dumps(mouth(job)) + '\n')
        print('stand-in take:', out.relative_to(demo), *(['(a sound of its own, and a stand-in mouth measure)'] if deaf else []))


if __name__ == '__main__':
    a = sys.argv[1:]; vm = a[a.index('--video-model') + 1] if '--video-model' in a[:-1] else None
    a = [x for x in a if x not in ('--video-model', vm)]
    if len(a) != 2 or a[0] not in ('audio', 'takes') or (vm and a[0] != 'audio'): sys.exit(__doc__)
    audio(pathlib.Path(a[1]), vm) if a[0] == 'audio' else takes(pathlib.Path(a[1]))
