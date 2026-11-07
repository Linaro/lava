#!/usr/bin/env python3
# Copyright (C) 2026 Qualcomm Technologies, Inc. and/or its subsidiaries.
#
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compare the web UI of two LAVA instances with full-page screenshots.

Logs into both instances as admin/admin, screenshots each page with headless
Chrome (google-chrome must be in PATH) and compares them.

1. Start the branch on port 8080 with ./test.sh.

2. Build and start an unpatched master on port 8081, seeded with the same
   test-data.sh so both instances have the same jobs, devices and results:

    git worktree add ../lava-master origin/master
    cp test-data.sh ../lava-master/
    cd ../lava-master
    ./docker/share/generate.py
    podman build -t lava-server-base:master \
        -f docker/lava-server-base/Dockerfile .
    podman build -t lava-server:master --build-arg base_image=lava-server-base:master \
        -f docker/lava-server/Dockerfile .
    podman run -d --name lava-master-baseline -p 8081:80 \
        -e LAVA_ADMIN_USERNAME=admin -e LAVA_ADMIN_PASSWORD=admin \
        -v "$PWD/test-data.sh:/root/entrypoint.d/90-test-data.sh:ro" \
        lava-server:master
    cd -

   Wait until http://localhost:8081/ answers before taking screenshots.

3. Take the screenshots:

    pip install requests websocket-client pillow
    ./shots.py shots/

4. Compare the results in shots/:

   scores.txt lists one page per line, worst first: the fraction of pixels
   that differ, the master page height, the branch page height and the path.
   A high score or a height mismatch is worth a look; a few percent is
   usually just font rendering and timestamps.

   <slug>.side.png shows master on the left and the branch on the right,
   separated by a red bar, padded to the same height. <slug>.master.png and
   <slug>.bs5.png are the individual full-page screenshots.

   To re-check a few pages after an edit, set PAGES before calling main():

    python3 -c "import sys, shots; sys.argv = ['shots', 'shots/'];
        shots.PAGES = ['/scheduler/alljobs']; shots.main()"

When done, remove the baseline (the container mounts test-data.sh from the
worktree, so remove it first):

    podman rm -f lava-master-baseline
    git worktree remove ../lava-master
"""

import base64
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import time

import requests
import websocket
from PIL import Image, ImageChops

SITES = {"master": "http://localhost:8081", "bs5": "http://localhost:8080"}
WIDTH = 1280
PAGES = [
    "/",
    "/scheduler/",
    "/results/",
    "/api/help/",
    "/results/query",
    "/results/chart",
    "/scheduler/reports",
    "/scheduler/device_types",
    "/scheduler/alldevices/active",
    "/scheduler/alljobs",
    "/scheduler/allworkers",
    "/scheduler/jobsubmit",
    "/api/tokens/",
    "/me/",
    "/scheduler/myjobs",
    "/scheduler/favorite-jobs",
    "/scheduler/mydevices",
    "/scheduler/mydevicetypehealthhistory",
    "/scheduler/alldevices/online",
    "/scheduler/alldevices/passinghealthchecks",
    "/scheduler/running",
    "/scheduler/alldevices",
    "/scheduler/labhealth/",
    "/scheduler/alldevices/maintenance",
    "/scheduler/queue",
    "/scheduler/activejobs",
    "/scheduler/joberrors",
    "/scheduler/device_type/qemu",
    "/scheduler/job/3",
    "/results/3",
    "/scheduler/job/2",
    "/results/2",
    "/results/2/lava",
    "/scheduler/job/1",
    "/results/1",
    "/results/1/lava",
    "/results/1/0_smoke-tests",
    "/results/query/+add",
    "/results/chart/+add",
    "/scheduler/longestjobs",
    "/scheduler/device/qemu-01",
    "/scheduler/worker/worker01",
    "/scheduler/healthcheck",
    "/scheduler/job/3/definition",
    "/scheduler/job/2/definition",
    "/scheduler/job/1/definition",
    "/scheduler/myactivejobs",
    "/scheduler/myqueuedjobs",
    "/scheduler/myerrorjobs",
    "/scheduler/reports/device_type/qemu",
    "/scheduler/reports/device/qemu-01",
    "/scheduler/job/2/annotate_failure",
    "/results/testcase/12",
    "/results/testcase/13",
    "/results/testcase/14",
    "/scheduler/job/1/annotate_failure",
    "/scheduler/dthealthhistory/device_type/qemu",
    "/results/2/lava/12",
    "/results/2/lava/13",
    "/results/2/lava/14",
]


def login(base):
    s = requests.Session()
    r = s.get(base + "/accounts/login/")
    # cookies are Secure but the test instances are plain http
    for c in s.cookies:
        c.secure = False
    tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text).group(1)
    s.post(
        base + "/accounts/login/",
        data={
            "csrfmiddlewaretoken": tok,
            "username": "admin",
            "password": "admin",
            "next": "/",
        },
        headers={"Referer": base + "/accounts/login/"},
    )
    return s.cookies["sessionid"]


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=60, suppress_origin=True)
        self.n = 0
        self.events = []

    def __call__(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if "method" in m:
                self.events.append(m)
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})

    def drain_events(self):
        events, self.events = self.events, []
        return events


def viewport(cdp, height):
    cdp(
        "Emulation.setDeviceMetricsOverride",
        width=WIDTH,
        height=height,
        deviceScaleFactor=1,
        mobile=False,
    )


def evaluate(cdp, expression):
    return cdp("Runtime.evaluate", expression=expression)["result"]["value"]


def navigate(cdp, url):
    cdp("Page.navigate", url=url)
    for _ in range(100):
        time.sleep(0.2)
        if evaluate(cdp, "document.readyState") == "complete":
            break


def capture(cdp, url, path):
    navigate(cdp, url)
    # LAVA's tables are server-side django_tables2; no JS DataTables exists
    # (repo-wide grep for dataTable(/new DataTable = 0 hits), so navigate()'s
    # readyState poll is sufficient; the grace below covers late charts.
    time.sleep(1.0)  # let charts draw their first frames
    viewport(
        cdp, min(int(evaluate(cdp, "document.documentElement.scrollHeight")), 8000)
    )
    path.write_bytes(
        base64.b64decode(cdp("Page.captureScreenshot", format="png")["data"])
    )
    viewport(cdp, 900)
    return Image.open(path).convert("RGB")


def compare(a, b, path):
    height = max(a.height, b.height)
    pa, pb = (Image.new("RGB", (WIDTH, height), "white") for _ in range(2))
    pa.paste(a)
    pb.paste(b)
    side = Image.new("RGB", (WIDTH * 2 + 10, height), "red")
    side.paste(pa, (0, 0))
    side.paste(pb, (WIDTH + 10, 0))
    side.save(path)
    diff = (
        ImageChops.difference(pa, pb).convert("L").point(lambda v: 255 if v > 24 else 0)
    )
    return diff.histogram()[255] / (WIDTH * height)


def launch_chrome(profile):
    return subprocess.Popen(
        [
            "google-chrome",
            "--headless=new",
            "--remote-debugging-port=9333",
            f"--user-data-dir={profile.name}",
            "--hide-scrollbars",
            "--no-first-run",
            "--force-device-scale-factor=1",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def connect_cdp():
    for _ in range(50):
        try:
            tabs = requests.get("http://127.0.0.1:9333/json").json()
            break
        except requests.ConnectionError:
            time.sleep(0.2)
    else:
        raise SystemExit("Chrome devtools never became reachable on :9333")
    return CDP(next(t for t in tabs if t["type"] == "page")["webSocketDebuggerUrl"])


HEALTH = """(() => JSON.stringify({
  bs: typeof bootstrap !== 'undefined' && !!bootstrap.Modal && typeof Popper !== 'undefined',
  overflow: [...document.querySelectorAll('.row,.container,table')]
    .filter(e => e.getBoundingClientRect().right > window.innerWidth + 1)
    .slice(0, 5).map(e => e.className),
  icon: (() => { const els = [...document.querySelectorAll('[class*="bi-"]')]
      .filter(e => e.offsetParent); // skip display:none (e.g. collapsed navbar)
    return !els.length || els.slice(0, 5).some(e => e.getBoundingClientRect().width > 0);
  })()
}))()"""

# Toggle check: per data-bs-toggle type -> (success selector, modal dismiss needed)
TOGGLE_CHECKS = {
    "modal": (".modal.show,.modal.showing", True),
    "confirm": (".modal.show,.modal.showing", True),
    "collapse": (".collapse.show", False),
    "dropdown": (".dropdown-menu.show", False),
    # shortcut: presence-only; asserting the .active class actually *moved*
    # needs a second tab to switch to, upgrade when a page regresses.
    "tab": (".nav-link.active,.page-item.active", False),
}


def page_errors(cdp):
    errors = []
    for m in cdp.drain_events():
        p = m.get("params", {})
        if m["method"] == "Runtime.exceptionThrown":
            d = p.get("exceptionDetails", {})
            errors.append(
                (d.get("exception", {}).get("description") or d.get("text"))[:200]
            )
        elif (
            m["method"] == "Log.entryAdded"
            and p.get("entry", {}).get("level") == "error"
        ):
            errors.append(p["entry"].get("text", "")[:200])
        elif (
            m["method"] == "Network.responseReceived"
            and p.get("response", {}).get("status", 0) >= 400
        ):
            errors.append(f"HTTP {p['response']['status']} {p['response']['url']}")
    return errors


def check(base):
    """Runtime BS5 checks: assert the BS5 contract on every page. Returns failure count."""
    profile = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    chrome = launch_chrome(profile)
    failures = []
    try:
        cdp = connect_cdp()
        viewport(cdp, 900)  # deterministic width, same as the screenshots path
        for domain in ("Page", "Runtime", "Log", "Network"):
            cdp(f"{domain}.enable")
        cdp("Network.setCookie", name="sessionid", value=login(base), url=base + "/")
        for page in PAGES:
            navigate(cdp, base + page)
            time.sleep(0.5)  # grace for late script errors
            health = json.loads(evaluate(cdp, HEALTH))
            errors = page_errors(cdp)
            bad = []
            if not health["bs"]:
                bad.append("bootstrap/Popper globals missing")
            if health["overflow"]:
                bad.append(f"overflow: {health['overflow']}")
            if not health["icon"]:
                bad.append("bi- icon zero-width (font 404?)")
            if errors:
                bad.append(f"{len(errors)} console/network errors: {errors[:3]}")
            # Toggle check: the migrated API surface is [data-bs-toggle]; click one
            # instance of each type on the page and assert the DOM responds.
            for t in json.loads(
                evaluate(
                    cdp,
                    "JSON.stringify(["
                    "...new Set([...document.querySelectorAll('[data-bs-toggle]')]"
                    ".map(e => e.dataset.bsToggle))])",
                )
            ):
                if t not in TOGGLE_CHECKS:
                    continue
                sel, dismiss = TOGGLE_CHECKS[t]
                evaluate(
                    cdp,
                    f"document.querySelector('[data-bs-toggle=\"{t}\"]')?.click(); true",
                )
                ok = False
                for _ in range(10):
                    time.sleep(0.2)
                    if evaluate(cdp, f"!!document.querySelector('{sel}')"):
                        ok = True
                        break
                if not ok:
                    bad.append(f"{t} toggle did not open ({sel})")
                if dismiss and ok:
                    evaluate(
                        cdp,
                        "document.querySelectorAll('.modal.show')"
                        ".forEach(m => bootstrap.Modal.getInstance(m)?.hide()); true",
                    )
                    time.sleep(0.4)
            # Tooltips: BS5 never auto-initialises [data-bs-toggle="tooltip"],
            # so assert the page itself initialised an instance (the regression
            # the static test cannot see), then that it can actually show.
            tip = "none"
            for _ in range(5):
                tip = evaluate(
                    cdp,
                    "(() => { const el = document.querySelector"
                    "('[data-bs-toggle=\"tooltip\"]'); if (!el) return 'none';"
                    " const i = bootstrap.Tooltip.getInstance(el);"
                    " if (!i) return 'uninitialized'; i.show();"
                    " const ok = !!document.querySelector('.tooltip.show');"
                    " i.hide(); return ok ? 'ok' : 'no-show'; })()",
                )
                if tip != "no-show":
                    break
                time.sleep(0.2)
            if tip not in ("none", "ok"):
                bad.append(f"tooltip probe: {tip}")
            print(
                f"{'FAIL' if bad else 'PASS'} {page}" + (f": {bad}" if bad else ""),
                flush=True,
            )
            if bad:
                failures.append(page)
    finally:
        chrome.terminate()
        chrome.wait(timeout=10)
        profile.cleanup()
    return len(failures)


def main():
    if sys.argv[1:2] == ["check"]:
        raise SystemExit(
            bool(check(sys.argv[2] if len(sys.argv) > 2 else SITES["bs5"]))
        )
    if sys.argv[1:2] == ["shots"]:  # single-site capture, no master pair
        single_base = sys.argv[2]
        argv_out = sys.argv[3] if len(sys.argv) > 3 else "shots"
        SITES.clear()
        SITES["bs5"] = single_base
    else:
        argv_out = sys.argv[1] if len(sys.argv) > 1 else "shots"
    out = pathlib.Path(argv_out)
    out.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    chrome = launch_chrome(profile)
    try:
        cdp = connect_cdp()
        cdp("Page.enable")
        cdp("Network.enable")
        viewport(cdp, 900)
        for base in SITES.values():
            cdp(
                "Network.setCookie", name="sessionid", value=login(base), url=base + "/"
            )
        scores = []
        for page in PAGES:
            slug = re.sub(r"[^A-Za-z0-9]+", "_", page).strip("_") or "index"
            imgs = {
                name: capture(cdp, base + page, out / f"{slug}.{name}.png")
                for name, base in SITES.items()
            }
            if "master" in imgs:
                line = f"{compare(imgs['master'], imgs['bs5'], out / f'{slug}.side.png'):6.1%} "
            else:
                line = "      -- "
            line += (
                f"{(imgs.get('master') or imgs['bs5']).height:5d} "
                f"{imgs['bs5'].height:5d} {page}"
            )
            print(line, flush=True)
            scores.append(line)
        (out / "scores.txt").write_text("\n".join(sorted(scores, reverse=True)) + "\n")
    finally:
        chrome.terminate()
        chrome.wait(timeout=10)
        profile.cleanup()


if __name__ == "__main__":
    main()
