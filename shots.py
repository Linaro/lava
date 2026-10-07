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
    "/results/3/None",
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
    "/scheduler/job/3/description",
    "/scheduler/reports/device/qemu-01",
    "/scheduler/job/2/description",
    "/scheduler/job/2/annotate_failure",
    "/results/testcase/12",
    "/results/testcase/13",
    "/results/testcase/14",
    "/scheduler/job/1/description",
    "/scheduler/job/1/annotate_failure",
    "/scheduler/device/qemu-01/devicedict",
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

    def __call__(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})


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


def capture(cdp, url, path):
    cdp("Page.navigate", url=url)
    for _ in range(100):
        time.sleep(0.2)
        if evaluate(cdp, "document.readyState") == "complete":
            break
    time.sleep(1.0)  # let datatables and charts render
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


def main():
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "shots")
    out.mkdir(parents=True, exist_ok=True)
    profile = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    chrome = subprocess.Popen(
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
    try:
        for _ in range(50):
            try:
                tabs = requests.get("http://127.0.0.1:9333/json").json()
                break
            except requests.ConnectionError:
                time.sleep(0.2)
        cdp = CDP(next(t for t in tabs if t["type"] == "page")["webSocketDebuggerUrl"])
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
            line = (
                f"{compare(imgs['master'], imgs['bs5'], out / f'{slug}.side.png'):6.1%} "
                f"{imgs['master'].height:5d} {imgs['bs5'].height:5d} {page}"
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
