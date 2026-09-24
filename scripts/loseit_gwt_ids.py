#!/usr/bin/env python3
"""Print the current Lose It! GWT build IDs (LOSEIT_STRONG_NAME / LOSEIT_POLICY_HASH).

Run this when loseit-mcp's server_status says the private API "did not respond as
expected" -- that means Lose It shipped a new web build.
"""
import re
import sys
import urllib.request

BASE = "https://d3hsih69yn4d89.cloudfront.net/web/"
PROXY = "LoseItRemoteService_Proxy"
HEX32 = r"[0-9A-Fa-f]{32}"


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def strong_name(nocache):
    consts = dict(re.findall(r"([A-Za-z_$][\w$]*)='([^']*)'", nocache))
    for tok in [k for k, v in consts.items() if v == "safari"]:
        m = re.search(r"\[[^\[\]]*," + re.escape(tok) + r"\],([A-Za-z_$][\w$]*|" + HEX32 + r")\)", nocache)
        if m:
            val = consts.get(m.group(1), m.group(1))
            if re.fullmatch(HEX32, val):
                return val.upper()
    return None


def policy_hash(cache):
    var = re.search(r"([A-Za-z_$][\w$]*)='" + PROXY + "'", cache)
    cls = var and re.search("," + re.escape(var.group(1)) + r",(\d+)\)", cache)
    ctor = cls and re.search(r"\(" + cls.group(1) + r",\d+,\{[^}]*\},([A-Za-z_$][\w$]*)\)", cache)
    body = ctor and re.search("function " + re.escape(ctor.group(1)) + r"\(\)\{.*?\}", cache)
    lit = body and re.search("'(" + HEX32 + ")'", body.group(0))
    return lit.group(1).upper() if lit else None


def main():
    sn = strong_name(get(BASE + "web.nocache.js"))
    if not sn:
        sys.exit("could not find the safari permutation in web.nocache.js")
    ph = policy_hash(get(BASE + sn + ".cache.js"))
    if not ph:
        sys.exit(f"could not find the {PROXY} policy hash in {sn}.cache.js")
    print(f"LOSEIT_STRONG_NAME={sn}\nLOSEIT_POLICY_HASH={ph}")


if __name__ == "__main__":
    main()
