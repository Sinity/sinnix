#!/usr/bin/env python3
"""claudia.py: the claudia.gallery collection from the command line (Python standard library only).

  claudia.py canon                                   the canon as Markdown
  claudia.py search WORDS... [--film F] [--set S] [-n 12]
  claudia.py show ID                                 one image: prompt, params, flags, URLs
  claudia.py list [--film F] [--set S] [--look L] [--batch B]
  claudia.py download [--film F] [--set S] [--look L] [--batch B] [--ids ID,ID] [--size s|m|full] [--out DIR]
  claudia.py guide TOPIC                             a wiki article: start, consistency, song, storyboard, midjourney,
                                                    seedance, motion, pipeline, toolkit, formats, failures

Films: escape-velocity, clodyssey, bliss, airplane-mode, downforce, dont-let-me-scroll, whitepill,
the-cake-is-not-a-lie, aero (fable, the tenth, has no Midjourney images). Sets: in_film (plates in the finished film), her, all.
Set CLAUDIA_SITE to use a mirror. Responses are cached in ~/.cache/claudia-gallery for a day.
"""
import json, math, os, pathlib, sys, time, urllib.request

SITE = os.environ.get("CLAUDIA_SITE", "https://claudia.gallery").rstrip("/")
CACHE = pathlib.Path(os.environ.get("XDG_CACHE_HOME", pathlib.Path.home() / ".cache")) / "claudia-gallery"
UA = {"User-Agent": "claudia-skill/1.0 (+https://claudia.gallery/agents/)"}


def get(path, binary=False, ttl=86400):
    url = path if path.startswith("http") else SITE + path
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / (url.replace("://", "_").replace("/", "_")[-180:])
    if not binary and key.exists() and time.time() - key.stat().st_mtime < ttl:
        return key.read_text()
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        data = r.read()
    if binary:
        return data
    text = data.decode("utf-8")
    key.write_text(text)
    return text


def images():
    return json.loads(get("/api/images.json"))["items"]


def opt(args, name, default=None):
    if name in args:
        i = args.index(name)
        v = args[i + 1]
        del args[i:i + 2]
        return v
    return default


def keep(it, film, set_, look=None, batch=None):
    return ((not film or film == "any" or it["film"] == film)
            and (set_ == "all" or (it["her"] if set_ == "her" else it["plate"]))
            and (not look or it.get("look") == look) and (not batch or it["batch"] == batch))


def line(it):
    flags = ("FILM " if it["plate"] else "") + ((it.get("verdict") or "").upper() + " " if it.get("verdict") else "")
    return f'{it["id"]:<44} {flags:<12} {it["w"]}x{it["h"]}  {it["prompt"][:90]}…'


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); return
    cmd = a.pop(0)
    film, set_ = opt(a, "--film"), opt(a, "--set", "all" if cmd == "search" else "in_film")
    look, batch = opt(a, "--look"), opt(a, "--batch")
    if cmd == "canon":
        print(get("/claudia.md"))
    elif cmd == "guide":
        print(get(f"/wiki/{a[0]}.md"))
    elif cmd == "show":
        it = json.loads(get(f"/api/images/{a[0]}.json"))
        print(json.dumps({k: (SITE + v if isinstance(v, str) and v.startswith("/") else v) for k, v in it.items()}, indent=1, ensure_ascii=False))
    elif cmd == "search":
        n = int(opt(a, "-n", 12))
        terms = [t.lower() for t in a if len(t) > 1]
        scored = []
        for it in images():
            if not keep(it, film, set_):
                continue
            hay = (it["prompt"] + " " + it["id"] + " " + (it.get("look") or "")).lower()
            hits = [hay.count(t) for t in terms]
            if terms and all(hits):
                scored.append((sum(1 + math.log(1 + h) for h in hits) + (0.5 if it["plate"] else 0), it))
        scored.sort(key=lambda x: -x[0])
        for _, it in scored[:n]:
            print(line(it))
        print(f"{len(scored)} matches", file=sys.stderr)
    elif cmd == "list":
        for it in images():
            if keep(it, film, set_, look, batch):
                print(line(it))
    elif cmd == "download":
        size, out = opt(a, "--size", "m"), pathlib.Path(opt(a, "--out", "claudia-refs"))
        ids = opt(a, "--ids")
        if ids:
            wanted = set(ids.split(","))
            sel = [it for it in images() if it["id"] in wanted]
        else:
            sel = [it for it in images() if keep(it, film, set_, look, batch)]
        out.mkdir(parents=True, exist_ok=True)
        meta = []
        for i, it in enumerate(sel, 1):
            url = it["url"][size]
            dst = out / f'{it["id"]}{pathlib.Path(url).suffix if size == "full" else ".webp"}'
            if not dst.exists():
                dst.write_bytes(get(url, binary=True))
                time.sleep(0.15)
            meta.append({"file": dst.name, **{k: it[k] for k in ("id", "film", "prompt", "params", "plate", "look")}})
            print(f"[{i}/{len(sel)}] {dst}")
        (out / "prompts.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
        print(f"{len(sel)} images and prompts.json in {out}")
    else:
        print(__doc__); sys.exit(2)


if __name__ == "__main__":
    main()
