"""lyric: how each lyric line sits on a 4/4 grid, how the lines ring together, and a loop that ranks rewrites.

  python -m claudia_kit lyric score LYRIC.txt [--section NAME] [--mode sung] [--bpm 120] [--grid]
  python -m claudia_kit lyric line "a line of lyric" [--mode spoken|sung|chant] [--grid]
  python -m claudia_kit lyric rewrite-loop LYRIC.txt --line N [--candidates FILE | --llm-cmd CMD] [--rounds 3] [--rhyme "partner"]
  python -m claudia_kit lyric fetch-dict          # download CMUdict (BSD licence) into ~/.cache/claudia-kit/

The model of a line:
  1. pronunciation: CMUdict, then a pron.json beside the lyric ({"word": "W ER1 D"}) for words it lacks; spaced capitals
     are letter names ("A I"), digits are read as words; anything else is guessed from spelling and flagged
  2. prominence per syllable: lexical stress, function words demoted, the last content word of each phrase accented
  3. text-setting: dynamic programming puts every syllable on the 16th-note grid of 1-4 bars (plus a one-beat pickup),
     minimising stress on weak slots, weak syllables on strong beats, and spans far from their natural length
  4. groove: short phrases that end on a stress, no long runs of weak syllables, no long spoken numbers
  5. assonance: each line end's best partner within four lines (rhyme, slant, shared vowel, consonance), and the
     stressed vowels that echo inside a line or the next
SCANSION = the setting score averaged with groove; ASSONANCE = 60% line ends + 40% echo. Both 0-100, per section and song.
Syllable rates are those measured on one Suno take: about 3.3 syllables a second spoken, 2.9 sung, 3.0 chanted.
"""
import argparse, functools, importlib.util, json, math, os, pathlib, re, subprocess, sys, urllib.request

BPM = 120.0
CACHE = pathlib.Path(os.environ.get("XDG_CACHE_HOME") or pathlib.Path.home() / ".cache") / "claudia-kit"
DICT_URL = "https://raw.githubusercontent.com/cmusphinx/cmudict/master/"

LETTER = {'a': 'EY1', 'b': 'B IY1', 'c': 'S IY1', 'd': 'D IY1', 'e': 'IY1', 'f': 'EH1 F', 'g': 'JH IY1', 'h': 'EY1 CH',
          'i': 'AY1', 'j': 'JH EY1', 'k': 'K EY1', 'l': 'EH1 L', 'm': 'EH1 M', 'n': 'EH1 N', 'o': 'OW1', 'p': 'P IY1',
          'q': 'K Y UW1', 'r': 'AA1 R', 's': 'EH1 S', 't': 'T IY1', 'u': 'Y UW1', 'v': 'V IY1',
          'w': 'D AH1 B AH0 L Y UW0', 'x': 'EH1 K S', 'y': 'W AY1', 'z': 'Z IY1'}
FUNC = set("""a an the in on at to of for with by from into onto over under up down out off about as like than through per
 i me my you your he him his she her it its we us our they them their this that these those who whom whose which what
 am is are was were be been being do does did have has had will would shall should can could may might must and or but
 nor so yet if then because while when where how there here i'm you're we're they're it's that's he's she's there's
 i've you've we've they've i'll you'll we'll they'll i'd you'd we'd they'd let's""".split())
LIGHT = set('go goes went gone get gets got make makes made take takes took say says said come came give gave let put keep kept'.split())
AUX = set('should would could can will do does did is are was were have has had must might may shall am'.split())
PARTICLE = set('up down out off in on over back away around through by'.split())
LONGV = {'AA', 'AO', 'AW', 'AY', 'EY', 'IY', 'OW', 'OY', 'UW', 'AE'}          # vowels that sustain on a long note
ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
        "eighteen nineteen").split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
EXTRA, DICT_PATH = {}, [None]                 # pron.json overrides; --dict


@functools.lru_cache(None)
def cmu():
    """CMUdict as {word: phones} (first pronunciation of each word); {} with a warning if no copy is found."""
    spec = importlib.util.find_spec("cmudict")         # the pip package "cmudict" carries the same data file
    cands = [DICT_PATH[0], os.environ.get("CLAUDIA_KIT_CMUDICT"), CACHE / "cmudict.dict",
             spec and spec.origin and pathlib.Path(spec.origin).parent / "data" / "cmudict.dict"]
    for c in cands:
        if c and pathlib.Path(c).exists():
            d = {}
            for ln in pathlib.Path(c).read_text(errors="ignore").splitlines():
                w, _, ph = ln.split("#")[0].strip().partition(" ")
                if w and not ln.startswith(";;;") and "(" not in w: d.setdefault(w.lower(), ph.split())
            return d
    print("lyric: CMUdict not found, so stresses are guessed from spelling (run: python -m claudia_kit lyric fetch-dict)",
          file=sys.stderr)
    return {}


def fetch_dict():
    """Download CMUdict and its licence (Carnegie Mellon University, BSD-style) into the cache folder."""
    CACHE.mkdir(parents=True, exist_ok=True)
    for name in ("cmudict.dict", "LICENSE"):
        urllib.request.urlretrieve(DICT_URL + name, CACHE / ("cmudict.LICENSE" if name == "LICENSE" else name))
    print("wrote", CACHE / "cmudict.dict", "(licence beside it)")


def num_words(s):
    """'2077' -> 'twenty seventy seven', '157' -> 'one fifty seven', '11.5' -> 'eleven point five'."""
    if '.' in s:
        a, b = s.split('.', 1); return num_words(a) + ' point ' + ' '.join(ONES[int(c)] for c in b if c.isdigit())
    n = int(s)
    two = lambda k: ONES[k] if k < 20 else TENS[k // 10] + ('' if k % 10 == 0 else ' ' + ONES[k % 10])
    if n < 100: return two(n)
    if 1100 <= n <= 2099 and len(s) == 4:                                   # read like a year
        hi, lo = divmod(n, 100); return two(hi) + (' hundred' if lo == 0 else (' oh ' + ONES[lo] if lo < 10 else ' ' + two(lo)))
    if n < 1000:
        h, r = divmod(n, 100); return ONES[h] + (' hundred' if r == 0 else ' ' + two(r))
    th, r = divmod(n, 1000); return num_words(str(th)) + ' thousand' + ('' if r == 0 else ' ' + num_words(str(r)))


def phones(word):
    """-> (phonemes, source) for a lower-case word."""
    w = word.lower().replace('’', "'"); d = cmu()
    if w in EXTRA: return EXTRA[w].split(), 'pron.json'
    if w in d: return d[w], 'cmu'
    for suf, add in (("'s", ['Z']), ("s", ['Z'])):                            # plurals and possessives of known words
        if w.endswith(suf) and w[:-len(suf)] in d: return d[w[:-len(suf)]] + add, 'cmu+s'
    bare = w.replace("'", '')                                                # a compound of two known words: stress the first
    for i in sorted(range(2, len(bare) - 1), key=lambda i: -min(i, len(bare) - i)):
        if bare[:i] in d and bare[i:] in d:
            return d[bare[:i]] + [p.replace('1', '2') for p in d[bare[i:]]], 'compound'
    groups = re.findall(r'[aeiouy]+', w) or ['a']                            # last resort: a syllable per vowel group
    return ['AH1' if i == 0 else 'AH0' for i in range(len(groups))], 'guess'


def syllabify(word, n):
    """split a written word into n display chunks (for the grid picture only)."""
    if n <= 1: return [word]
    g = [m.start() for m in re.finditer(r'[aeiouyAEIOUY]+', word)][1:n]
    if len(g) < n - 1: k = max(1, len(word) // n); g = [k * i for i in range(1, n)]
    cuts = [0] + [max(1, c - 1) if c - 1 > 0 and word[c - 1].isalpha() and word[c - 1] not in 'aeiouy' else c for c in g] + [len(word)]
    return [word[a:b] or '-' for a, b in zip(cuts, cuts[1:])]


TOK = re.compile(r"[A-Za-z0-9’']+(?:[-.][A-Za-z0-9’']+)*|[.,!?;:…—–]+|\(|\)")
MAJOR = set('.!?;:…')


def analyse(text):
    """-> (syllables, words). Each syllable: text, vowel v, stress st, prominence P (0-1), phrase boundary bnd (0, 1 comma,
    2 stop), backing (inside parentheses). Parenthesised words take time like any other: Suno sings them."""
    toks = TOK.findall(text.replace('...', '…')); words, back = [], False
    for i, t in enumerate(toks):
        if t in '()': back = t == '('; continue
        if re.fullmatch(r'[.,!?;:…—–]+', t):
            if words: words[-1]['bnd'] = 2 if any(c in MAJOR for c in t) else max(words[-1]['bnd'], 1)
            continue
        caps = len(re.sub(r'[^A-Za-z]', '', t)) > 1 and t.upper() == t and re.search('[A-Z]', t) is not None
        near_letter = any(0 <= j < len(toks) and re.fullmatch(r'[A-Z]', toks[j]) for j in (i - 1, i + 1))
        for piece in filter(None, t.split('-')):
            if re.fullmatch(r'\d+(\.\d+)?', piece): parts = [(x, 'num') for x in num_words(piece).split()]
            elif re.fullmatch(r'[A-Z]{2,5}', piece) and piece.lower() not in cmu(): parts = [(c, 'letter') for c in piece]
            elif re.fullmatch(r'[A-Z]', piece) and (near_letter or piece not in 'AI'): parts = [(piece, 'letter')]
            else: parts = [(piece, '')]
            for p, kind in parts:
                lp = p.lower().strip("'’")
                ph, src = (LETTER[lp].split(), 'letter') if kind == 'letter' else phones(lp)
                words.append(dict(txt=p, ph=list(ph), src=src, func=lp in FUNC and kind != 'letter', caps=caps, bnd=0,
                                  back=back, letter=kind == 'letter', num=kind == 'num'))
    for i, w in enumerate(words):        # spelled letters: the last of a run carries the stress (A G I); a lone letter
        if not w['letter'] or w['bnd'] or i + 1 == len(words): continue        # before a word is a prefix (the P of "P doom")
        if words[i + 1]['letter'] or not (i > 0 and words[i - 1]['letter'] and not words[i - 1]['bnd']):
            w['ph'] = [p[:-1] + '2' if p[-1] == '1' else p for p in w['ph']]
    start = 0                                        # the nuclear accent: the last content word of each phrase
    for i, w in enumerate(words):
        if w['bnd'] or i == len(words) - 1:
            content = [k for k in range(start, i + 1) if not words[k]['func']]
            if i > start and w['txt'].lower() in PARTICLE and not words[i - 1]['func']:
                w['nuc'] = True; words[i - 1]['demote'] = True                # "slow DOWN"
            elif content: words[content[-1]]['nuc'] = True
            elif w['func']: w['part'] = True                                  # "lock IN."
            if i > start and w['txt'].lower() in AUX: w['strand'] = True      # "as he SHOULD"
            start = i + 1
    syl = []
    for wi, w in enumerate(words):
        vs = [p for p in w['ph'] if p[-1].isdigit()] or ['AH0']; disp = syllabify(w['txt'], len(vs))
        for si, v in enumerate(vs):
            st = int(v[-1])
            if w['func']: P = 0.8 if (w.get('part') or w.get('strand')) and st == 1 else (0.22 if st == 1 else 0.05)
            else: P = {1: 0.75, 2: 0.45, 0: 0.08}[st]
            if w.get('nuc') and (st == 1 or len(vs) == 1): P = 1.0
            elif st == 1 and (w.get('demote') or (w['txt'].lower() in LIGHT and not w.get('nuc'))): P = 0.45
            if w['caps'] and st == 1: P = min(1.0, P + 0.15)
            if w['num'] and st == 1: P = max(P, 0.75)
            syl.append(dict(txt=disp[si], wi=wi, v=v[:-1], st=st, P=P, func=w['func'], back=w['back'],
                            bnd=w['bnd'] if si == len(vs) - 1 else 0))
    return syl, words


# ---- the text-setting model: weights of the 16 sixteenths of a bar, and the three deliveries ----
W16 = [1.0, 0.1, 0.35, 0.1, 0.6, 0.1, 0.35, 0.1, 0.8, 0.1, 0.35, 0.1, 0.6, 0.1, 0.35, 0.1]
MODES = {  # A stress on a weak slot, B weak syllable on a strong beat, C span deviation, base span (16ths), shortest spans,
    # breath after a stop/comma (16ths), held final, syllables per bar band, long line, run without a breath
    'spoken': dict(A=1.5, B=1.2, C=0.3, base=5.0, min_weak=1, min_strong=1, breath=(2, 1), final=2, band=(6, 10), long=16, run=15),
    'sung':   dict(A=1.5, B=1.2, C=0.3, base=4.0, min_weak=1, min_strong=2, breath=(3, 2), final=4, band=(4, 8), long=10, run=10),
    'chant':  dict(A=1.0, B=2.0, C=1.2, base=5.0, min_weak=2, min_strong=2, breath=(2, 2), final=4, band=(2, 8), long=12, run=9)}
RATE = {'spoken': 3.33, 'sung': 2.94, 'chant': 3.01}       # syllables a second, measured on one Suno take
PICKUP = 4                                                 # a one-beat pickup before bar 1


def place_cost(s, t, m):
    w = W16[t % 16]; hi = max(0.0, s['P'] - w); lo = max(0.0, w - s['P'] - 0.25) if w >= 0.6 else 0.0
    return m['A'] * hi * hi + m['B'] * lo * lo


def span_cost(s, d, m, final=False):
    if final: return 0.0 if d >= m['final'] else 2.0 * (m['final'] - d)
    lo = m['min_strong'] if s['P'] >= 0.5 else m['min_weak']
    if s['bnd'] == 2: lo = max(lo, 2)
    nat = m['base'] * (0.7 + 0.6 * s['P']) * (1.15 if s['v'] in LONGV else 1.0) + \
        (m['breath'][0] if s['bnd'] == 2 else m['breath'][1] if s['bnd'] == 1 else 0)
    return (3.0 * (lo - d) if d < lo else 0.0) + m['C'] * math.log2(d / nat) ** 2


def setting(syl, bars, mode):
    """the cheapest placement of the syllables on bars*16 slots (plus the pickup) -> (cost, onsets, per-syllable costs)."""
    m = MODES[mode]; n = len(syl); T = int(round(bars * 16)); INF = float('inf'); size = T + PICKUP
    cost = [[INF] * size for _ in range(n)]; back = [[-1] * size for _ in range(n)]
    for t in range(-PICKUP, min(8, T - 1) + 1):
        cost[0][t + PICKUP] = place_cost(syl[0], t, m) + 0.03 * max(0, t) + (0.15 if t < 0 and syl[0]['P'] >= 0.5 else 0)
    for i in range(1, n):
        for t in range(-PICKUP + i, T):
            best, arg = INF, -1
            for d in range(1, 17):
                tp = t - d
                if tp < -PICKUP: break
                c0 = cost[i - 1][tp + PICKUP]
                if c0 < INF:
                    c = c0 + span_cost(syl[i - 1], d, m)
                    if c < best: best, arg = c, tp
            if arg != -1: cost[i][t + PICKUP], back[i][t + PICKUP] = best + place_cost(syl[i], t, m), arg
    ends = [(cost[n - 1][t + PICKUP] + span_cost(syl[-1], T - t, m, True), t) for t in range(-PICKUP, T) if cost[n - 1][t + PICKUP] < INF]
    if not ends: return INF, [], []
    best, tl = min(ends); on = [0] * n; on[-1] = tl
    for i in range(n - 1, 0, -1): on[i - 1] = back[i][on[i] + PICKUP]
    per = [place_cost(syl[i], on[i], m) + span_cost(syl[i], (on[i + 1] if i + 1 < n else T) - on[i], m, i == n - 1) for i in range(n)]
    return best, on, per


def groove(text):
    """does the line lock to the pulse: short phrases (3-5 syllables between stops) that end on a stress, no runs of four
    or more weak syllables, no long numbers. 100 = nothing to fix."""
    syl, words = analyse(text); phrases, cur, pen, why = [], [], 0.0, []
    for s in syl:
        cur.append(s)
        if s['bnd']: phrases.append(cur); cur = []
    if cur: phrases.append(cur)
    for ph in phrases:
        L = len(ph); run = best = 0
        if L > 5: pen += 0.45 * (L - 5); why.append(f'{L}-syllable phrase')
        for s in ph: run = run + 1 if s['P'] < 0.5 else 0; best = max(best, run)
        if best >= 4: pen += 0.8 * (best - 3); why.append(f'{best} weak syllables in a row')
        strong = [i for i, s in enumerate(ph) if s['P'] >= 0.5]; tail = (L - 1 - strong[-1]) if strong else L
        if tail >= 2: pen += 0.7 * (tail - 1); why.append(f'phrase ends {tail} syllables after its last stress')
        if L == 1 and ph[0]['func']: pen += 2.5; why.append('a one-word function-word phrase')
    run = best = 0
    for w in words: run = run + 1 if w['num'] else 0; best = max(best, run)
    if best >= 3: pen += 0.8 * (best - 2); why.append(f'{best}-word number')
    return dict(groove=round(100 * math.exp(-pen / 3.0)), why=why)


def score_line(text, mode='sung', bars=None, bpm=BPM):
    """one line on the grid: score 0-100 and what drags it down."""
    syl, words = analyse(text); m = MODES[mode]; n = len(syl)
    if n == 0: return None
    L0 = max(1.0, round(2 * n / (RATE[mode] * 240 / bpm)) / 2)             # bars at Suno's pace
    best = None
    for L in ([bars] if bars else sorted({max(1.0, L0 - 0.5), L0, L0 + 0.5, L0 + 1.0})):
        c, on, per = setting(syl, L, mode)
        total = c + (0 if bars else 0.6 * abs(L - L0) * n / 6)
        if on and (best is None or total < best[0]): best = (total, L, c, on, per)
    if best is None: return dict(text=text, n=n, error='does not fit')
    _, L, c, on, per = best
    for s, t, pc in zip(syl, on, per): s['t'] = t; s['cost'] = pc
    spans = [(on[i + 1] if i + 1 < n else int(L * 16)) - on[i] for i in range(n)]
    prom = [s for s in syl if s['P'] >= 0.7]
    notes = []
    for pc, s in sorted(zip(per, syl), key=lambda x: -x[0])[:3]:
        if pc < 0.6: continue
        w = W16[s['t'] % 16]
        notes.append(f'stressed "{s["txt"]}" on a weak 16th' if s['P'] - w > 0.4 else
                     f'weak "{s["txt"]}" on a strong beat' if w - s['P'] > 0.4 else f'"{s["txt"]}" rushed or dragged')
    sustain = [1.0 if s['v'] in LONGV else (0.2 if s['st'] == 0 else 0.6)
               for s, d in zip(syl, spans) if mode != 'spoken' and (d >= 4 or s is syl[-1])]
    runs, cur = [], 0
    for s in syl:
        cur += 1
        if s['bnd']: runs.append(cur); cur = 0
    rare = []
    if mode != 'spoken' and importlib.util.find_spec('wordfreq'):           # optional: rare words get misheard when sung
        from wordfreq import zipf_frequency
        rare = [w['txt'] for w in words if not (w['func'] or w['letter'] or w['num']) and zipf_frequency(w['txt'].lower(), 'en') < 3.2]
    return dict(text=text, mode=mode, n=n, bars=L, per_sec=round(n / (L * 240 / bpm), 2), suno_s=round(n / RATE[mode], 1),
                longest_run=max(runs + [cur]), score=round(100 * math.exp(-(c / n) / 0.9), 1),
                onbeat=round(100 * (sum(W16[s['t'] % 16] >= 0.6 for s in prom) / len(prom) if prom else 1.0)),
                weakdown=[s['txt'] for s in syl if s['P'] <= 0.25 and s['t'] % 8 == 0],
                sustain=round(sum(sustain) / len(sustain), 2) if sustain else None, notes=notes, rare=rare,
                guessed=sorted({w['txt'] for w in words if w['src'] in ('guess', 'compound')}), syl=syl)


def grid(r):
    """the placement as text: one row per bar, | on each beat, CAPS on prominent syllables."""
    cells = {s['t']: s['txt'].upper() if s['P'] >= 0.7 else s['txt'].lower() for s in r['syl']}
    rows, T = [], int(r['bars'] * 16)
    for b0 in range(-16 if min(cells) < 0 else 0, T, 16):
        rows.append(('pk ' if b0 < 0 else '%2d ' % (b0 // 16 + 1)) + ''.join(
            ('|' if t % 4 == 0 else ' ') + cells.get(t, '·' if t >= 0 else ' ')[:6].ljust(6) for t in range(b0, b0 + 16)))
    return '\n'.join(rows)


# ---- assonance: how the line ends ring together, and how the stressed vowels echo ----
VOWELS = {'AA', 'AE', 'AH', 'AO', 'AW', 'AY', 'EH', 'ER', 'EY', 'IH', 'IY', 'OW', 'OY', 'UH', 'UW'}
NEAR_V = [{'AE', 'EH'}, {'IH', 'IY'}, {'AH', 'AA', 'AO'}, {'UH', 'UW'}, {'EY', 'EH'}, {'OW', 'AO'}, {'AY', 'AA'}, {'ER', 'AH'}]
SAY = {'AA': 'ah', 'AE': 'a', 'AH': 'uh', 'AO': 'aw', 'AW': 'ow', 'AY': 'eye', 'EH': 'eh', 'ER': 'er', 'EY': 'ay',
       'IH': 'ih', 'IY': 'ee', 'OW': 'oh', 'OY': 'oy', 'UH': 'u', 'UW': 'oo'}


def sound_line(text):
    """the line's end: its phonemes from the last beat-bearing syllable (lead voice only), and its stressed vowels."""
    syl, words = analyse(text)
    pos = [(wi, vi) for wi, w in enumerate(words) for vi in ([i for i, p in enumerate(w['ph']) if p[-1].isdigit()] or [0])]
    lead = [i for i in range(min(len(pos), len(syl))) if not syl[i]['back']]
    if not lead: return None
    wi, vi = pos[([i for i in lead if syl[i]['P'] >= 0.6] or [lead[-1]])[-1]]
    tail = [re.sub(r'\d', '', p) for p in words[wi]['ph'][vi:]]
    for w in words[wi + 1:]:
        if not w['back']: tail += [re.sub(r'\d', '', p) for p in w['ph']]
    coda = []
    for p in reversed(tail):
        if p in VOWELS: break
        coda.insert(0, p)
    plain = re.sub(r"[^a-z' ]", ' ', re.sub(r'\([^)]*\)', ' ', text.lower())).split()
    return dict(tail=tail, tv=[p for p in tail if p in VOWELS], coda=coda, vow=[syl[i]['v'] for i in lead if syl[i]['P'] >= 0.45],
                key=' '.join(plain), last=plain[-1] if plain else '')


def ring(a, b):
    """how two line ends ring together -> (0-1, kind)."""
    if a['key'] and a['key'] == b['key']: return 0.5, 'repeat'
    if a['last'] and a['last'] == b['last']: return 0.6, 'same word'
    if a['tail'] == b['tail'] and a['tail']: return 1.0, 'rhyme'
    va, vb = a['tv'], b['tv']
    if not va or not vb: return 0.0, ''
    cls = lambda c: 'open' if not c else 'nasal' if c[0] in ('M', 'N', 'NG') else 'stop' if c[0] in 'PBTDKG' else c[0]
    same = cls(a['coda']) == cls(b['coda'])
    if va == vb: return ((0.95 if same else 0.8), 'multi') if len(va) >= 2 else ((0.75, 'slant') if same else (0.6, 'assonance'))
    if va[0] == vb[0]: return (0.65 if same else 0.55), 'assonance'
    if a['coda'] and a['coda'] == b['coda']:
        return (0.45, 'near') if any(va[0] in g and vb[0] in g for g in NEAR_V) else (0.3, 'consonance')
    return 0.0, ''


def assonance(lines):
    """-> dict(assonance 0-100, end, echo, rows aligned with the lines (None for a line with no lead voice))."""
    S = list(map(sound_line, lines)); idx = [i for i, x in enumerate(S) if x]
    if not idx: return None
    rows = [None] * len(S)
    for q, i in enumerate(idx):
        a = S[i]; near_i = idx[max(0, q - 4):q] + idx[q + 1:q + 5]
        best = max([(*ring(a, S[j]), j) for j in near_i] or [(0.0, '', None)], key=lambda x: x[0])
        nb = (S[idx[q - 1]]['vow'] if q else []) + (S[idx[q + 1]]['vow'] if q + 1 < len(idx) else []); vs = a['vow']
        echo = sum(1.0 if vs.count(v) >= 2 else 0.5 if v in nb else 0.0 for v in vs) / len(vs) if vs else 0.0
        rows[i] = dict(end=best[0], kind=best[1], partner=best[2], echo=echo, tail=a['tv'], coda=a['coda'])
    ok = [r for r in rows if r]; end, echo = (sum(r[k] for r in ok) / len(ok) for k in ('end', 'echo'))
    return dict(assonance=round(100 * (0.6 * end + 0.4 * echo)), end=end, echo=echo, rows=rows)


# ---- lint: what Suno reads differently from what you meant, and generic AI-lyric words ----
TELLS = [r'\bneon\b', r'\bechoes?\b', r'\bwhispers?\b', r'\bshadows?\b', r'\bignite', r'\btapestr', r'\bsymphon',
         r'\bvelvet\b', r'\belectric\b', r'\bdelve', r'\btestament\b', r'\brealm\b', r"\bit'?s not (just )?\w+.{0,20}, it'?s\b"]
HOMOGRAPH = set('live read lead tear bass wind bow close content desert minute object present produce record invalid row '
                'sow wound polish resume use house'.split())


def lint(text):
    out, low = [], text.lower()
    if '(' in text: out.append(('info', 'parentheses are sung as backing vocals (1-3 words work; a sentence gets sung)'))
    if re.search(r'\d', text):
        out.append(('warn', 'digits: write numbers as words (' + ', '.join(f'{d} = {num_words(d)}' for d in re.findall(r'\d+(?:\.\d+)?', text)) + ')'))
    for a in re.findall(r'\b[A-Z]{2,5}\b', text):
        if a.lower() not in cmu() and a != text.strip(): out.append(('warn', f'acronym "{a}": spell it with spaces ({" ".join(a)})'))
    if '[' in text: out.append(('warn', 'brackets inside a lyric line may be read aloud'))
    if re.search(r'[&%$#@/+=]', text): out.append(('warn', 'a symbol in a sung line: write it as a word'))
    out += [('info', f'homograph "{w}": check it is sung the way you mean') for w in re.findall(r"[a-z']+", low) if w in HOMOGRAPH]
    out += [('info', f'generic AI-lyric word /{p}/: cut it unless the cliché is the point') for p in TELLS if re.search(p, low)]
    return out


# ---- the lyric file: Suno's lyrics field, every line as sung ----
def infer_mode(header, default='sung'):
    h = header.lower()
    if 'chant' in h or 'shout' in h or 'call and response' in h: return 'chant'
    if re.search(r'\bsung\b|\bsing', h): return 'sung'
    if any(k in h for k in ('spoken', 'talk', 'rap', 'whisper', 'deadpan')): return 'spoken'
    if any(k in h for k in ('chorus', 'hook', 'vocal')): return 'sung'
    return default


def parse(text, default='sung'):
    """-> [(section header, mode, [lines])]. [Header - description] lines open sections; blank and # lines are skipped."""
    secs, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'): continue
        h = re.fullmatch(r'\[(.+)\]', line)
        if h:
            if h.group(1).strip().lower() != 'end': cur = (h.group(1), infer_mode(h.group(1), default), []); secs.append(cur)
            continue
        if cur is None: cur = ('Untitled', default, []); secs.append(cur)
        cur[2].append(line)
    return secs


def load_lyric(path, mode=None):
    p = pathlib.Path(path); pron = p.with_name('pron.json')
    if pron.exists(): EXTRA.update({k.lower(): v for k, v in json.loads(pron.read_text()).items()})
    secs = parse(p.read_text(), mode or 'sung')
    return [(n, mode or m, ls) for n, m, ls in secs] if mode else secs


def section_report(name, mode, lines, show_grid=False, bpm=BPM):
    rs = [score_line(l, mode, bpm=bpm) for l in lines]; gs = [groove(l)['groove'] for l in lines]; asn = assonance(lines)
    ok = [r['score'] for r in rs if r and 'error' not in r]
    scan = round(0.5 * sum(ok) / max(1, len(ok)) + 0.5 * sum(gs) / max(1, len(gs)))
    out = [f"\n== {name}  [{mode}]   SCANSION {scan}   ASSONANCE {asn['assonance'] if asn else '-'}"
           + (f"  (ends {asn['end']:.2f} · echo {asn['echo']:.2f})" if asn else '')]
    m = MODES[mode]
    for i, (r, g, line) in enumerate(zip(rs, gs, lines)):
        if not r or 'error' in r: out.append(f'{i + 1:3d}  (does not fit a 1-4 bar grid)  {line}'); continue
        a = asn['rows'][i] if asn else None
        end = ('-'.join(SAY.get(v, v) for v in a['tail']) + ('+' + ''.join(a['coda']).lower() if a['coda'] else '')) if a else ''
        link = f"↔{a['partner'] + 1} {a['kind']} {a['end']:.2f}" if a and a['partner'] is not None and a['end'] else '↔ none'
        out.append(f"{i + 1:3d}  {r['score']:5.1f} groove {g:3d}  {line}")
        flag = (f' · LONG for {mode}' if r['n'] > m['long'] else '') + (f' · {r["longest_run"]} syllables without a breath' if r['longest_run'] > m['run'] else '')
        out.append(f"      {r['n']} syl · ~{r['suno_s']} s at Suno pace · {r['bars']:g} bars · stresses on beats {r['onbeat']}%"
                   + (f" · long-note vowels {r['sustain']:.2f}" if r['sustain'] is not None else '') + flag
                   + (' · weak on 1/3: ' + ', '.join(r['weakdown']) if r['weakdown'] else '') + f" · end {end} {link}")
        for n in r['notes'] + groove(line)['why'][:2]: out.append('      - ' + n)
        if r['rare']: out.append('      - rare words (misheard when sung): ' + ', '.join(r['rare']))
        if r['guessed']: out.append('      - pronunciation guessed (add to pron.json): ' + ', '.join(r['guessed']))
        for lvl, msg in lint(line): out.append(f"      {'!' if lvl == 'warn' else '·'} {msg}")
        if show_grid: out += ['        ' + g_ for g_ in grid(r).splitlines()]
    return out, scan, asn['assonance'] if asn else 0, len(lines)


# ---- the rewrite loop: candidates from any LLM, ranked by the scorer ----
RULES = """You are a line editor for a pop song. Rewrite ONE lyric line so it sits better on a 4/4 grid while keeping its
meaning, its image and its voice. Rules: original words only (never quote or closely paraphrase an existing song); sung
lines use common words and put open vowels (ah, oh, ay, ee, oo) on long notes; spoken lines are natural sentences of
about 10-13 syllables with the stressed words where speech already puts them on the beat, ending on a stressed word;
write numbers as words; spell acronyms with spaces; parentheses only for a 1-3 word backing vocal; subtract rather than
add; no generic AI-lyric words (neon, echoes, whispers, shadows, ignite, tapestry, symphony, velvet, electric) unless
the cliché is the point. Answer with one candidate per line and nothing else."""


def evaluate(text, mode, partner=None):
    """rank a candidate line: the setting score and groove, minus lint and shape problems, plus the ring with a partner."""
    r = score_line(text, mode)
    if not r or 'error' in r: return None
    g = groove(text); lt = lint(text); m = MODES[mode]
    rank = 0.5 * r['score'] + 0.5 * g['groove'] - 4 * sum(l == 'warn' for l, _ in lt)
    rank -= 3 * max(0, r['n'] - m['long']) + 2 * max(0, r['longest_run'] - m['run'])
    if r['sustain'] is not None: rank -= 10 * max(0.0, 0.8 - r['sustain'])
    if mode == 'spoken':           # Suno sets a spoken line in a two-bar slot: 10-13 syllables fill it, 7-9 get dragged
        stops = len(re.findall(r'[.!?;:]\s+\S', text))
        rank -= (6 if 7 <= r['n'] <= 9 else 2 * max(0, r['n'] - 13)) + 5 * max(0, stops - 1)
    why = list(dict.fromkeys(r['notes'] + g['why'] + [msg for l, msg in lt if l == 'warn']))
    if partner:
        a, b = sound_line(text), sound_line(partner)
        if a and b: s, kind = ring(a, b); rank += 15 * s - 7.5; why.append(f'ring with the partner line {s:.2f} ({kind or "none"})')
    return dict(text=text, rank=round(rank, 1), score=r['score'], groove=g['groove'], n=r['n'], why=why)


def ask(line, mode, section, around, best, n):
    shown = '\n'.join(f'  "{b["text"]}"  -> rank {b["rank"]}; ' + ('; '.join(b['why']) or 'no problems found') for b in best)
    return (f"{RULES}\n\nSection: {section} ({mode} delivery).\nThe lines around it (context only):\n"
            + '\n'.join('  ' + x for x in around) + f'\n\nLine to improve: "{line}"\n\nCurrent best versions and what the scorer '
            f'says about each:\n{shown}\n\nWrite {n} new versions that fix what is flagged. Vary the approach: cut words, '
            'swap a word, reorder, move the stress onto a strong word.')


def candidates_from(text):
    out = []
    for ln in text.splitlines():
        ln = re.sub(r'^\s*(\d+[.)]|[-*•])\s*', '', ln).strip().strip('"“”').strip()
        if ln and len(ln) < 200: out.append(ln)
    return out


def rewrite_loop(o):
    secs = load_lyric(o.path, o.mode); flat = [(n, m, l, ls) for n, m, ls in secs for l in ls]
    if not 1 <= o.line <= len(flat): sys.exit(f'--line must be 1-{len(flat)} (lines are counted through the whole file)')
    section, mode, line, ls = flat[o.line - 1]; k = ls.index(line); around = ls[max(0, k - 2):k] + ls[k + 1:k + 3]
    pool = {line: evaluate(line, mode, o.rhyme)}
    if o.candidates:
        for c in candidates_from(pathlib.Path(o.candidates).read_text()): pool.setdefault(c, evaluate(c, mode, o.rhyme))
    for rd in range(o.rounds if o.llm_cmd else 0):
        best = sorted((v for v in pool.values() if v), key=lambda x: -x['rank'])[:o.keep]
        print(f'round {rd + 1}: asking the model', file=sys.stderr)
        r = subprocess.run(o.llm_cmd, shell=True, input=ask(line, mode, section, around, best, o.n), capture_output=True, text=True, timeout=900)
        if r.returncode: sys.exit(f'--llm-cmd failed: {r.stderr[-400:]}')
        for c in candidates_from(r.stdout): pool.setdefault(c, evaluate(c, mode, o.rhyme))
    ranked = sorted((v for v in pool.values() if v), key=lambda x: -x['rank'])
    print(f'# {section} [{mode}], line {o.line}\n\n| # | line | rank | score | groove | syl | flags |\n|---|---|---|---|---|---|---|')
    for i, c in enumerate(ranked[:12], 1):
        print(f"| {i} | {c['text']}{' (original)' if c['text'] == line else ''} | {c['rank']} | {c['score']} | {c['groove']} | {c['n']} | {'; '.join(c['why'])[:140]} |")
    if not o.llm_cmd or o.prompt:
        print('\n--- the next round: paste this into any LLM, add its answers to your candidates file (one per line), '
              'and run again with --candidates FILE ---\n')
        print(ask(line, mode, section, around, ranked[:o.keep], o.n))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='claudia_kit lyric', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dict', help='path to a cmudict.dict file'); sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('score'); a.add_argument('path'); a.add_argument('--section'); a.add_argument('--grid', action='store_true')
    a.add_argument('--mode', choices=list(MODES), help='one delivery for the whole file (default: from each section header)')
    a.add_argument('--bpm', type=float, default=BPM)
    b = sub.add_parser('line'); b.add_argument('text'); b.add_argument('--mode', default='sung', choices=list(MODES))
    b.add_argument('--grid', action='store_true'); b.add_argument('--bpm', type=float, default=BPM)
    r = sub.add_parser('rewrite-loop'); r.add_argument('path'); r.add_argument('--line', type=int, required=True)
    r.add_argument('--candidates', help='a file of candidate lines, one per line'); r.add_argument('--llm-cmd',
                   help='a shell command that reads the prompt on stdin and prints candidates, one per line')
    r.add_argument('--rounds', type=int, default=3); r.add_argument('--n', type=int, default=6); r.add_argument('--keep', type=int, default=3)
    r.add_argument('--rhyme', help='the couplet partner line: rank by how the ends ring together'); r.add_argument('--mode', choices=list(MODES))
    r.add_argument('--prompt', action='store_true', help='print the next prompt even after ranking candidates')
    sub.add_parser('fetch-dict')
    o = ap.parse_args(argv); DICT_PATH[0] = o.dict
    if o.cmd == 'fetch-dict': return fetch_dict()
    if o.cmd == 'rewrite-loop': return rewrite_loop(o)
    secs = [('line', o.mode, [o.text])] if o.cmd == 'line' else load_lyric(o.path, o.mode)
    out, tot = [], []
    for name, mode, lines in secs:
        if getattr(o, 'section', None) and o.section.lower() not in name.lower(): continue
        rows, sc, asn, n = section_report(name, mode, lines, o.grid, o.bpm); out += rows; tot.append((n, sc, asn))
    n = sum(t[0] for t in tot) or 1
    out.append('\nsong  SCANSION %d   ASSONANCE %d' % tuple(round(sum(t[0] * t[k] for t in tot) / n) for k in (1, 2)))
    print('\n'.join(out))


if __name__ == '__main__':
    main()
