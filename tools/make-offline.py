#!/usr/bin/env python3
"""Build a single-file, offline copy of Hills of Dowra.

    python3 tools/make-offline.py

Reads `Hills of Dowra.html` and writes `Hills of Dowra (offline).html` next to it: the same game with everything it loads from the
internet embedded in the file, so it runs with no connection and no server (just open it).

What it embeds:
  * the JavaScript modules named in the game's import map (three.js and its add-ons, three-mesh-bvh, meshoptimizer), found by reading
    the import map and the game's import() calls, then following each module's own relative imports. They are fetched once from
    jsDelivr (the same URLs the game uses) and cached in tools/cache/, so later builds need no connection.
  * the Google Fonts the game asks for (Latin and Latin Extended), as base64 @font-face rules.

How the modules are served: the file carries them as base64 and, before the game starts, turns each into a blob: URL and registers an
import map pointing the game's module names at those. Browsers refuse to import ordinary files from file:// pages; blob: URLs are not
affected, so a double-click works. A relative import inside a library ('./three.core.js') is rewritten to a module name of its own
('lib:three@0.185.1/build/three.core.js'), since blob: URLs have nothing to resolve it against.

Python 3 standard library only. Nothing is written outside tools/cache/ and the output file.
"""
import base64, hashlib, json, pathlib, re, sys, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "Hills of Dowra.html"
OUT = ROOT / "Hills of Dowra (offline).html"
CACHE = pathlib.Path(__file__).resolve().parent / "cache"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def get(url, cache_name=None):
    """Fetch url (bytes), through tools/cache/ when cache_name is given."""
    if cache_name:
        p = CACHE / cache_name
        if p.exists():
            return p.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if cache_name:
        p = CACHE / cache_name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return data


def cache_name(url):
    u = urllib.parse.urlparse(url)
    return u.netloc + u.path


def b64(data):
    return base64.b64encode(data).decode("ascii")


# --- the modules --------------------------------------------------------------------------------------------------------------

# a real import or export-from statement starts its line; the same words inside comments and strings do not
IMPORT_RE = re.compile(r"""(?m)^(\s*(?:import|export)\b[^'"`;]*?\bfrom\s*|\s*import\s*)(['"])([^'"\n]+)\2""")


def build_modules(html):
    m = re.search(r'<script type="importmap">(.*?)</script>', html, re.S)
    if not m:
        sys.exit("no import map found in the game")
    imap = json.loads(m.group(1))["imports"]
    exact = {k: v for k, v in imap.items() if not k.endswith("/")}
    prefixes = {k: v for k, v in imap.items() if k.endswith("/")}

    def resolve_bare(spec):
        if spec in exact:
            return exact[spec]
        for p, base in prefixes.items():
            if spec.startswith(p):
                return base + spec[len(p):]
        return None

    # every bare specifier the game itself imports, in the import() calls and any static imports
    game = re.findall(r"""\bimport\(\s*['"]([^'"]+)['"]\s*\)""", html)
    roots = list(dict.fromkeys(list(exact) + game))

    url_key = {}      # url -> canonical module name
    keys = {}         # module name -> url
    for spec in roots:
        url = resolve_bare(spec)
        if url is None:
            sys.exit(f"the game imports '{spec}', which the import map does not cover")
        url_key.setdefault(url, spec)
        keys[spec] = url

    text = {}         # url -> source text, after rewriting
    importer = {}     # url -> the module that imports it, for error messages
    queue = list(dict.fromkeys(keys.values()))
    while queue:
        url = queue.pop(0)
        if url in text:
            continue
        try:
            src = get(url, cache_name(url)).decode("utf-8")
        except Exception as e:
            sys.exit(f"could not fetch {url} ({e}); imported by {importer.get(url)}")
        text[url] = src
        for _, _, spec in IMPORT_RE.findall(src):
            if spec.startswith(("./", "../")):
                dep = urllib.parse.urljoin(url, spec)
                if dep not in url_key:
                    # a module only reached by a relative import gets a name of its own
                    path = urllib.parse.urlparse(dep).path.replace("/npm/", "", 1)
                    url_key[dep] = "lib:" + path
                    keys[url_key[dep]] = dep
                importer.setdefault(dep, url)
                queue.append(dep)
    # point each relative import at the module's name
    out = {}
    for url, src in text.items():
        def fix(mo, url=url):
            spec = mo.group(3)
            if spec.startswith(("./", "../")):
                return f"{mo.group(1)}{mo.group(2)}{url_key[urllib.parse.urljoin(url, spec)]}{mo.group(2)}"
            return mo.group(0)
        out[url] = IMPORT_RE.sub(fix, src)
    return keys, out


# --- the fonts ----------------------------------------------------------------------------------------------------------------

def build_fonts(html):
    m = re.search(r'<link rel="stylesheet" href="(https://fonts\.googleapis\.com/css2[^"]+)">', html)
    if not m:
        return ""
    css = get(m.group(1).replace("&amp;", "&"), "fonts.googleapis.com/" + hashlib.sha1(m.group(1).encode()).hexdigest() + ".css").decode("utf-8")
    faces = []
    for block in re.findall(r"(/\*\s*([\w-]+)\s*\*/\s*@font-face\s*\{.*?\})", css, re.S):
        text, subset = block
        if subset not in ("latin", "latin-ext"):
            continue
        def embed(mo):
            font = get(mo.group(1), cache_name(mo.group(1)))
            return f"url(data:font/woff2;base64,{b64(font)})"
        faces.append(re.sub(r"url\((https://[^)]+)\)", embed, text))
    return "<style>\n" + "\n".join(faces) + "\n</style>\n"


# --- the page -----------------------------------------------------------------------------------------------------------------

LOADER = """<script>
// the game's libraries travel inside this file: each becomes a blob: URL, and the import map the game was written against points at them
(()=>{const L=%s,K=%s,B=[];
for(const s of L){const t=atob(s),u=new Uint8Array(t.length);for(let i=0;i<t.length;i++)u[i]=t.charCodeAt(i);B.push(URL.createObjectURL(new Blob([u],{type:'text/javascript'})))}
const m={};for(const k in K)m[k]=B[K[k]];
const s=document.createElement('script');s.type='importmap';s.textContent=JSON.stringify({imports:m});document.head.appendChild(s)})();
</script>"""


def main():
    html = SRC.read_text(encoding="utf-8")
    keys, mods = build_modules(html)
    order = list(mods)
    index = {url: i for i, url in enumerate(order)}
    kmap = {k: index[u] for k, u in keys.items()}
    loader = LOADER % (json.dumps([b64(mods[u].encode("utf-8")) for u in order]), json.dumps(kmap))

    # 1. the import map becomes the loader
    html, n = re.subn(r'<script type="importmap">.*?</script>', lambda _: loader, html, count=1, flags=re.S)
    assert n == 1
    # 2. the web fonts become embedded ones
    fonts = build_fonts(html)
    html, n = re.subn(r'<link rel="preconnect" href="https://fonts\.googleapis\.com"><link rel="preconnect" href="https://fonts\.gstatic\.com" crossorigin>\n<link rel="stylesheet" href="[^"]+">\n',
                      lambda _: fonts, html, count=1)
    assert n == 1, "font links not found as expected"
    # 3. a failed load can no longer mean 'no internet'
    old = "Hills of Dowra loads from the internet. Check your connection, then try again."
    assert html.count(old) == 1
    html = html.replace(old, "Some of the game's files didn't load. Try again, and if it keeps happening, reopen the file.")

    left = sorted(set(re.findall(r"https?://(?!www\.w3\.org)[^\s\"'<>)]+", re.sub(r"<script>\n// the game's libraries.*?</script>", "", html, flags=re.S))))
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.name}: {OUT.stat().st_size / 1e6:.2f} MB, {len(order)} modules, {len(kmap)} module names")
    for k in sorted(kmap):
        print("  ", k)
    # every http(s) address still in the file should be one the game never fetches (comments, SVG namespaces)
    ext = [u for u in left if "fonts.g" in u or "jsdelivr" in u]
    if ext:
        print("WARNING: still references the network:", ext)


if __name__ == "__main__":
    main()
