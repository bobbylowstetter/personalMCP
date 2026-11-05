"""Run loseit-mcp with GWT type schemas regenerated for Lose It's current web build.

The lose-it SDK ships a fixed ``_schemas.json``. When Lose It changes a model
class (new field, new type hash), decoding any response that contains it fails
-- e.g. a ``GoalsSummary`` change broke every weight-history read. This wrapper
rebuilds the schemas from the live compiled JS whenever the build differs from
the shipped one, merges them over the shipped catalog, then starts loseit-mcp.

The GWT read primitives have minified names that change every build, so they are
learned by aligning the deserializers of types whose hash didn't change against
their shipped field lists. If the rebuilt schemas don't reproduce those known
types, the shipped catalog is used unchanged.

Runs inside the loseit-mcp environment (launched by scripts/loseit-mcp.sh via
``uvx --from ... python``). Logs go to stderr; stdout is the MCP channel.
"""

import codecs
import collections
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

BASE = "https://d3hsih69yn4d89.cloudfront.net/web/"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "loseit-mcp"
MIN_AGREEMENT = 0.95

IDENT = r"[A-Za-z_$][\w$]*"
CONST_RE = re.compile(
    rf"(?<![\w$])({IDENT})\s*=\s*'((?:com\.loseit|com\.google|java\.|javax\.|\[(?:com\.loseit|com\.google|java\.|L))[^']+/\d+)'"
)
TABLE_RE = re.compile(rf"(?<![\w$])a\[({IDENT})\]\s*=\s*\[({IDENT})\s*,\s*({IDENT})(?:\s*,\s*{IDENT})?\]")
FRAGMENT_RE = re.compile(r"\$wnd\.web\.runAsyncCallback\d+\([\"'](.*)[\"']\)\s*;?\s*$", re.S)
ENUM_RE = re.compile(r"=\s*a\.b\[--a\.a\]\s*;[\s\S]*return\s+[\w$]+\s*\[\s*[a-z]\s*\]")
STRING_READ = re.compile(rf"({IDENT})\(a,\s*a\.b\[--a\.a\]\)")
CALL_READ = re.compile(rf"({IDENT})\(a\)")
SUPER_CALL = re.compile(rf"^({IDENT})\(a\s*,\s*b\)$")
RAW = "RAW"


def log(msg):
    print(f"loseit_serve: {msg}", file=sys.stderr)


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode("utf-8")


def load_bundle(perm):
    parts = [fetch(f"{BASE}{perm}.cache.js")]
    for n in range(1, 65):
        try:
            raw = fetch(f"{BASE}deferredjs/{perm}/{n}.cache.js")
        except Exception:
            break
        m = FRAGMENT_RE.match(raw)
        if m:
            parts.append(codecs.decode(m.group(1), "unicode_escape"))
    return "\n".join(parts)


_FN_STARTS = {}


def fn_body(js, name):
    if not _FN_STARTS:
        for m in re.finditer(rf"function ({IDENT})\([^)]*\)\s*\{{", js):
            _FN_STARTS.setdefault(m.group(1), m.end())
    start = _FN_STARTS.get(name)
    if start is None:
        return None
    depth, i = 1, start
    while depth and i < len(js):
        depth += {"{": 1, "}": -1}.get(js[i], 0)
        i += 1
    return js[start : i - 1]


def read_tokens(js, deser, seen=None):
    """Ordered read tokens for a deserializer: function names, or RAW."""
    seen = seen or set()
    if deser in seen:
        return []
    seen.add(deser)
    body = fn_body(js, deser)
    if body is None:
        return None
    tokens = []
    for stmt in (s.strip() for s in body.split(";")):
        sup = SUPER_CALL.match(stmt)
        if sup:
            inner = read_tokens(js, sup.group(1), seen)
            if inner is None:
                return None
            tokens.extend(inner)
        elif m := STRING_READ.search(stmt):
            tokens.append(("str", m.group(1)))
        elif m := CALL_READ.search(stmt):
            tokens.append(("call", m.group(1)))
        elif "a.b[--a.a]" in stmt:
            tokens.append(RAW)
    return tokens


def build(js, shipped):
    consts = dict(CONST_RE.findall(js))
    table = {v: (inst, deser) for v, inst, deser in TABLE_RE.findall(js)}
    types = {fqcn: table[var] for var, fqcn in consts.items() if var in table}

    tokens = {fqcn: read_tokens(js, deser) for fqcn, (_, deser) in types.items()}

    votes = collections.defaultdict(collections.Counter)
    for fqcn, toks in tokens.items():
        known = shipped.get(fqcn)
        if known and toks is not None and len(toks) == len(known.fields):
            for tok, kind in zip(toks, known.fields):
                if tok != RAW:
                    votes[tok][kind] += 1
    primitives = {tok: c.most_common(1)[0][0] for tok, c in votes.items()}

    schemas = {}
    for fqcn, toks in tokens.items():
        if toks is None or any(t != RAW and t not in primitives for t in toks):
            continue
        inst_body = fn_body(js, types[fqcn][0]) or ""
        schemas[fqcn] = {
            "fields": [RAW if t == RAW else primitives[t] for t in toks],
            "is_enum": bool(ENUM_RE.search(inst_body)),
        }

    overlap = [f for f in schemas if f in shipped]
    agree = sum(
        schemas[f]["fields"] == shipped[f].fields and schemas[f]["is_enum"] == shipped[f].is_enum
        for f in overlap
    )
    ratio = agree / len(overlap) if overlap else 0.0
    log(f"{len(schemas)} types rebuilt, {len(overlap)} unchanged, {ratio:.1%} match shipped schemas")
    if ratio < MIN_AGREEMENT:
        raise RuntimeError("rebuilt schemas disagree with shipped ones; not using them")
    return schemas


def install_live_schemas():
    from lose_it.core import _decoder as dec

    catalog = dec._Catalog.load()
    perm = os.environ.get("LOSEIT_STRONG_NAME", "")
    if not re.fullmatch(r"[0-9A-F]{32}", perm) or perm == catalog.permutation:
        return
    cache = CACHE_DIR / f"schemas-{perm}.json"
    try:
        schemas = json.loads(cache.read_text())
    except (OSError, ValueError):
        schemas = build(load_bundle(perm), catalog.schemas)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(schemas))
    for fqcn, info in schemas.items():
        catalog.schemas[fqcn] = dec._Schema(fqcn=fqcn, fields=info["fields"], is_enum=info["is_enum"])
    catalog.permutation = perm
    dec._CATALOG = catalog


def main():
    try:
        install_live_schemas()
    except Exception as exc:
        log(f"schema refresh failed, using shipped schemas: {exc}")
    from loseit_mcp.cli import main as cli_main

    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
