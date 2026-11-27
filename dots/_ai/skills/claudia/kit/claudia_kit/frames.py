"""frames: the stills (first frames, last frames, plates) from the book's "stills" block, made with GPT Image 2.6
Sunburst on Replicate.

  python -m claudia_kit frames make BOOK.json [IDS] --max-usd N [--quality Q] [--again] [--dry-run]
  python -m claudia_kit frames edit BOOK.json ID --from SRC --max-usd N [--dry-run]   # ID made as an edit of SRC
  python -m claudia_kit frames list BOOK.json [IDS]                                    # made, in flight, failed or not made

The book's "stills" block, every path relative to the book's folder:
  "stills": {"S1": {"prompt": "...", "images": ["refs/sheet.png", "frames/plate.png"], "aspect": "16:9", "quality": "high"},
             "S1-end": {"from": "S1", "prompt": "The same photograph from the same camera, a moment later: ..."}}
Each still is written to frames/<id>.png, with frames/<id>.json beside it (what was sent, without the uploads, and the
prediction's id and numbers). "images" go up in that order: name them in the prompt as the first image, the second
image ... "from" (or --from) is a still's id or an image path, and goes up first: a last frame made as an edit of its
first frame shares its camera (two frames made separately do not, and a video model joins them with a dissolve).
"aspect" is a ratio (16:9, 9:16, 3:2 ...) or a size (1536x1024, 2048x1152, 3840x2160 ...), by default the book's
aspect_ratio; "quality" is low, medium, high (the default), xhigh or max. In a prompt, {subject}, {world} and
{look:NAME} stand for the book's identity text, its world and that look, word for word.

The same discipline as run: one image per call; --dry-run prints what would be sent and its list price; --max-usd is
required to submit and caps build/ledger.jsonl, which the stills share with the takes; a paid submit is never retried.
A still that exists is left as it is (--again makes a new one and keeps the old one as frames/<id>.<n>.png); a still in
flight is polled again by the next make, never sent twice. The key comes from REPLICATE_API_TOKEN only, never printed.
"""
import argparse, json, re, struct, sys, time
from .common import Project, jload, jsave
from .run import Replicate, RunError, UA, http, ledger, ledger_rows, spent, uploader

MODEL = "openai/gpt-image-2.6-sunburst"
PRICE = {"low": 0.05, "medium": 0.09, "high": 0.128, "xhigh": 0.25, "max": 0.50, "auto": 0.25}   # US$ an image: Replicate's list, November 2026
ASPECTS = ("1:1 3:2 2:3 4:3 3:4 16:9 9:16 auto 1024x1024 1536x1024 1024x1536 1536x1152 1152x1536 2048x2048 2048x1152 "
           "1152x2048 3840x2160 2160x3840").split()            # the model's aspect_ratio values (its schema, November 2026)
LIVE, ENDED = {"submitted", "starting", "processing"}, {"failed", "canceled", "uncertain"}


def stills(P):
    S = P.book.get("stills") or {}
    if not isinstance(S, dict): sys.exit('the book\'s "stills" is {"<id>": {"prompt": "...", "images": [...]}, ...}')
    return S


def fill(P, text):
    """{subject}, {world} and {look:NAME} -> the book's own words, as they are."""
    def sub(m):
        k, _, arg = m.group(1).partition(":"); v = (P.book.get("looks") or {}).get(arg) if k == "look" else P.book.get(k)
        return v if v else sys.exit(f"a still's prompt names {m.group(0)}, but the book has no such {'look' if k == 'look' else k}")
    return re.sub(r"\{(subject|world|look:[^{}]+)\}", sub, text)


def out(P, sid): return P.dir / "frames" / f"{sid}.png"


def request(P, sid, st, quality=None, src=None):
    """-> (the model's input without the uploads, the images in order as the book names them)"""
    if not st.get("prompt"): sys.exit(f"still {sid}: no prompt")
    src = src or st.get("from"); imgs = ([src if re.search(r"\.(png|jpe?g|webp)$", src, re.I) else f"frames/{src}.png"] if src else []) + list(st.get("images") or [])
    aspect, q = st.get("aspect", P.book.get("defaults", {}).get("aspect_ratio", "16:9")), quality or st.get("quality", "high")
    if aspect not in ASPECTS: sys.exit(f"still {sid}: aspect {aspect!r} is not one the model takes: {' '.join(ASPECTS)}")
    if q not in PRICE: sys.exit(f"still {sid}: quality {q!r}: give low, medium, high, xhigh or max")
    return dict(prompt=fill(P, st["prompt"]), aspect_ratio=aspect, quality=q, output_format="png", background="opaque", number_of_images=1), imgs


def state(P, sid):
    """("made" | "flight" | "ended" | "new", its record)"""
    rec = jload(out(P, sid).with_suffix(".json"), {})
    if out(P, sid).exists(): return "made", rec
    if rec.get("status") in LIVE and rec.get("id"): return "flight", rec
    return ("ended" if rec.get("status") in ENDED else "new"), rec


def keep_old(P, sid):
    """--again: the still there is and its record move to frames/<id>.<n>.png and .json (n is never reused)."""
    f, n = out(P, sid), 1
    while f.with_name(f"{sid}.{n}.png").exists() or f.with_name(f"{sid}.{n}.json").exists(): n += 1
    for x in (f, f.with_suffix(".json")):
        if x.exists(): x.rename(x.with_name(f"{sid}.{n}{x.suffix}"))
    return n


def wait(P, sid, rec, timeout=600, every=4):
    """poll a still's prediction until it ends, then download the image (free calls, ridden through dropped connections)."""
    prov, t0, f = Replicate(), time.time(), out(P, sid)
    while True:
        d = http("GET", f"{prov.api}/predictions/{rec['id']}", prov.h(), retry=True); st = d.get("status")
        if st not in ("starting", "processing") or time.time() - t0 > timeout: break
        time.sleep(every)
    o = d.get("output"); u = (o[0] if o else None) if isinstance(o, list) else o
    if st == "succeeded" and not u: st, d["error"] = "failed", "the prediction ended with no image"
    rec.update(status=st, metrics=d.get("metrics"), error=d.get("error"))
    if st == "succeeded":
        data = http("GET", u, {"User-Agent": UA}, retry=True); tmp = f.with_suffix(".part"); tmp.write_bytes(data); tmp.rename(f)
        w, h = struct.unpack(">II", data[16:24]) if data[:8] == b"\x89PNG\r\n\x1a\n" else (None, None)
        print(f"{sid}: {f.relative_to(P.dir)}" + (f" {w}x{h}" if w else "") + f" ({(d.get('metrics') or {}).get('predict_time', 0):.0f} s)")
    elif st in ("starting", "processing"):
        print(f"{sid}: still running after {timeout:.0f} s; run frames make again to collect it (it is not sent again)")
    else:
        print(f"{sid}: {st}: {str(d.get('error'))[:300]}", file=sys.stderr)
    jsave(f.with_suffix(".json"), rec)


def make(P, sid, st, cap, dry, planned=0.0, again=False, quality=None, src=None, made=(), timeout=600):
    """one still (or, with dry, what it would send) -> its list price if it was sent (or would be), else 0."""
    inp, imgs = request(P, sid, st, quality, src); c = PRICE[inp["quality"]]; kind, rec = state(P, sid)
    if kind == "flight":
        if dry: print(f"{sid}: in flight ({rec['id']}): a real run collects it and sends nothing"); return 0.0
        print(f"{sid}: in flight ({rec['id']}): collecting it"); wait(P, sid, rec, timeout); return 0.0
    if kind != "new" and not again:
        print(f"{sid}: " + (f"{out(P, sid).relative_to(P.dir)} exists" if kind == "made" else f"its last request {rec.get('status')}")
              + ": left as it is (--again makes a new one" + (" and keeps this one)" if kind == "made" else ")")); return 0.0
    for x in imgs:
        if not str(x).startswith("http") and not P.p(x).exists() and not (dry and x in made): raise RunError(f"{sid}: missing image {x}")
    total = spent(P) + planned
    if total + c > cap + 1e-9: raise RunError(f"{sid}: ${c:.2f} would take the ledger from ${total:.2f} past the cap of ${cap:.2f}; nothing sent")
    if dry:
        print(f"--- {sid}: replicate {MODEL}, quality {inp['quality']}, {inp['aspect_ratio']}, {len(imgs)} image(s) in, ${c:.2f} list "
              f"(ledger and this run ${total:.2f} -> ${total + c:.2f}, cap ${cap:.2f})" + ("; the one there is would be kept" if kind == "made" else ""))
        print(json.dumps(dict(inp, **({"input_images": [x if str(x).startswith("http") else f"<upload {x}>" for x in imgs]} if imgs else {})),
                         indent=1, ensure_ascii=False))
        return c
    if kind != "new": print(f"{sid}: the earlier still and its record are kept as frames/{sid}.{keep_old(P, sid)}.*")
    prov = Replicate(); url = uploader(P, prov, "replicate"); body = dict(inp, **({"input_images": [url(x) for x in imgs]} if imgs else {}))
    rec = dict(still=sid, model=MODEL, at=time.strftime("%Y-%m-%d %H:%M:%S"), prompt=inp["prompt"], images=imgs,
               **{k: v for k, v in inp.items() if k != "prompt"}, **({"from": src or st.get("from")} if src or st.get("from") else {}), usd_est=c)
    try:
        d = http("POST", f"{prov.api}/models/{MODEL}/predictions", prov.h({"Content-Type": "application/json"}),
                 json.dumps({"input": body}).encode())                # the paid call: one attempt, never repeated by the kit
        if not isinstance(d, dict) or not d.get("id"): raise ConnectionError(f"no prediction id in the answer: {str(d)[:300]}")
    except RunError as e:
        if not (e.code or 0) >= 500: raise                          # a 4xx answer: nothing was started
        rec.update(id=None, status="uncertain", error=str(e))
    except ConnectionError as e:
        rec.update(id=None, status="uncertain", error=str(e))
    else:
        rec.update(id=d["id"], status="submitted")
    ledger(P, at=rec["at"], kind="still", still=sid, provider="replicate", model=MODEL, id=rec["id"], usd_est=c,
           quality=inp["quality"], aspect=inp["aspect_ratio"], uncertain=rec["status"] == "uncertain")
    jsave(out(P, sid).with_suffix(".json"), rec)
    if rec["status"] == "uncertain":
        print(f"{sid}: the submit did not come back cleanly ({rec['error'][:200]}), so the image may or may not have been "
              "started. Check the Replicate dashboard before making it again (--again).", file=sys.stderr)
        return c
    print(f"{sid}: submitted {rec['id']} (${c:.2f}; ledger ${spent(P):.2f} of ${cap:.2f})")
    wait(P, sid, rec, timeout); return c


def listing(P, ids):
    S = stills(P)
    for sid in ids:
        kind, rec = state(P, sid); f = out(P, sid); what = ""
        if kind == "made":
            b = f.read_bytes()[:24]; w, h = struct.unpack(">II", b[16:24]) if b[:8] == b"\x89PNG\r\n\x1a\n" else (0, 0)
            what = f"{w}x{h}" if w else "made"
        print(f"{sid:10s} {dict(made='made', flight='in flight', ended=rec.get('status', ''), new='not made')[kind]:10s} {what:10s} "
              f"{rec.get('quality', (S.get(sid) or {}).get('quality', 'high')):7s}" + (f" from {rec['from']}" if rec.get("from") else "")
              + (f"  {rec['id']}" if rec.get("id") else "") + ("" if sid in S else "  (not in the book's stills)"))
    rows = [r for r in ledger_rows(P) if r.get("kind") == "still"]
    print(f"stills in the ledger: ${sum(r['usd_est'] for r in rows):.2f} at list price over {len(rows)} submits (all: ${spent(P):.2f})")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="claudia_kit frames", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["make", "edit", "list"]); ap.add_argument("book"); ap.add_argument("ids", nargs="*")
    ap.add_argument("--from", dest="src", help="edit: the still (its id, or an image path) this one is an edit of; it goes up first")
    ap.add_argument("--max-usd", type=float, help="the most the ledger may reach (required to submit)")
    ap.add_argument("--quality", choices=list(PRICE), help="for every still made now, over the book's (low or medium for drafts)")
    ap.add_argument("--again", action="store_true", help="make a still that exists, or whose last request ended, again (the old one is kept)")
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--timeout", type=float, default=600)
    o = ap.parse_args(argv); P = Project(o.book); S = stills(P)
    if o.cmd == "list": return listing(P, o.ids or list(S))
    if o.cmd == "edit" and (len(o.ids) != 1 or not (o.src or (S.get(o.ids[0]) or {}).get("from"))):
        sys.exit("frames edit BOOK ID --from SRC: one still, and the still it is an edit of")
    if o.cmd == "make" and o.src: sys.exit("--from is for frames edit (or write \"from\" in the still)")
    ids = o.ids or list(S)
    for sid in ids:
        if sid not in S: sys.exit(f'no still {sid!r} in the book\'s "stills": add "{sid}": {{"prompt": "..."}}')
    if o.max_usd is None: sys.exit("give --max-usd: the most the ledger may reach after these stills")
    planned, n, made = 0.0, 0, set()
    try:
        for sid in ids:
            c = make(P, sid, S[sid], o.max_usd, o.dry_run, planned if o.dry_run else 0.0, o.again, o.quality,
                     o.src if o.cmd == "edit" else None, made, o.timeout)
            if c: planned += c; n += 1; made.add(f"frames/{sid}.png")
    except RunError as e:
        print(e, file=sys.stderr)
    except ConnectionError as e:
        print(f"the connection failed while waiting ({e}): run frames make again to collect what is in flight (nothing is "
              "sent twice)", file=sys.stderr)
    if o.dry_run: print(f"dry run: {n} still(s) within the cap, ${planned:.2f} at list price; nothing was sent")


if __name__ == "__main__":
    main()
