#!/usr/bin/env python3
"""parity.py — rapp-parity/0: build a clean-room estate from public source, then check
whether your live estate is still in parity with it. Every divergence IS drift, located,
with the direction of truth known.

Kody's insight (2026-08-25): one sentinel compared against one fresh clone is a sample.
An entire REFERENCE ESTATE, rebuilt from the public repos on a device that never grew
organically, is a differential oracle. The organic estate accreted over months —
hand-fixes, half-migrations, code that never got pushed, code that never got pulled. You
cannot see that from inside it, because there is nothing to compare against. Build the
same estate from the public source of truth and every difference is a finding, and its
direction is knowable:

    reference AHEAD  -> the organic instance never pulled  (deployment gap)
    organic AHEAD    -> a local fix never got pushed       (publication gap)
    both differ      -> genuine divergence needing judgment (a fork, or a conflict)
    only organic has -> local-only work, possibly unbacked  (risk)
    only reference   -> something the organic estate is missing entirely

Frames make this permanent rather than a one-off report: each build mints a
`reference.build` frame carrying every component's public HEAD, and each comparison
mints `reference.diff` frames. So "when did this instance start drifting?" becomes a
query, not an archaeology project — the same unlock the health chain gave the ops score.

  python3 parity.py build     clone/refresh the reference estate (deck by default)
  python3 parity.py diff      compare organic vs reference, mint frames
  python3 parity.py report    human-readable divergence report
"""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rapp as R

CHAIN = HERE / "parity.jsonl"
STREAM = "parity:@kody-w/estate"

# The estate's public components. Each entry: (repo, where the ORGANIC copy lives).
# Organic paths are per-device; None means "this-mac only".
# Your estate, in one place. Each entry: (public repo, {device: path-to-the-live-copy}).
# Device "local" means this machine; anything else is an ssh target.
# Override by writing parity.json beside this file — see README.
COMPONENTS = [
    ("kody-w/rapp-1", {"local": "~/Documents/GitHub/rapp-1"}),
]

REF_HOST = "local"          # ideally a device that never grew organically
REF_ROOT = "~/parity-reference"

_cfg = Path(__file__).resolve().parent / "parity.json"
if _cfg.exists():
    import json as _json
    _c = _json.loads(_cfg.read_text())
    COMPONENTS = [(r, m) for r, m in (_c.get("components") or COMPONENTS)]
    REF_HOST = _c.get("reference_host", REF_HOST)
    REF_ROOT = _c.get("reference_root", REF_ROOT)


def _utc() -> str:
    n = datetime.datetime.now(datetime.timezone.utc)
    return n.strftime("%Y-%m-%dT%H:%M:%S.") + f"{n.microsecond // 1000:03d}Z"


def sh(cmd, timeout=300):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def ssh(host, cmd, timeout=300):
    if host in ("local", "localhost", "this-mac"):
        return sh(cmd, timeout)
    return sh(f"ssh -o BatchMode=yes -o ConnectTimeout=15 {host} '{cmd}'", timeout)


def load() -> list[dict]:
    if not CHAIN.exists():
        return []
    frames = [json.loads(l) for l in CHAIN.read_text().splitlines() if l.strip()]
    head = None
    for f in frames:
        ok, step, why = R.verify_frame(f, head=head, stream_id_of_record=STREAM)
        if not ok:
            raise ValueError(f"reference chain BROKEN at seq {f.get('seq')}: {step}: {why}")
        head = f
    return frames


def _append(kind: str, payload: dict) -> dict:
    frames = load()
    head = frames[-1] if frames else None
    f = R.build_frame(kind, STREAM, (head["seq"] + 1) if head else 0, _utc(), payload,
                      prev=(head["payload_hash"] if head else None))
    ok, step, why = R.verify_frame(f, head=head, stream_id_of_record=STREAM)
    if not ok:
        raise ValueError(f"refusing invalid reference frame: {step}: {why}")
    with open(CHAIN, "a") as fh:
        fh.write(json.dumps(f) + "\n")
    return f


def build() -> dict:
    """Clone or refresh every public component into the reference estate."""
    ssh(REF_HOST, f"mkdir -p {REF_ROOT}")
    built = {}
    for repo, _ in COMPONENTS:
        name = repo.split("/")[1]
        dest = f"{REF_ROOT}/{name}"
        rc, _, _ = ssh(REF_HOST, f"test -d {dest}/.git")
        if rc == 0:
            ssh(REF_HOST, f"git -C {dest} fetch -q origin && git -C {dest} reset -q --hard origin/main")
        else:
            ssh(REF_HOST, f"git clone -q https://github.com/{repo}.git {dest}")
        rc, sha, _ = ssh(REF_HOST, f"git -C {dest} log -1 --format=%h")
        built[repo] = sha.strip() or "FAILED"
        print(f"  {name:16} {built[repo]}")
    f = _append("reference.build", {"host": REF_HOST, "root": REF_ROOT,
                                    "components": built, "at": _utc()})
    print(f"reference.build frame {f['seq']} — {len(built)} components")
    return built


def _organic_sha(device: str, path: str) -> str | None:
    cmd = f"git -C {path} log -1 --format=%h"
    rc, out, _ = (sh(cmd) if device == "this-mac" else ssh(_host(device), cmd))
    return out.strip() or None if rc == 0 else None


def _host(device: str) -> str:
    return {"rappterone": "rappterone", "rapptertwo": "rapptertwo"}.get(device, device)


def diff() -> list[dict]:
    """Compare every organic copy against the reference. Classify each divergence."""
    frames = load()
    builds = [f for f in frames if f["kind"] == "reference.build"]
    if not builds:
        print("no reference build yet — run `build` first")
        return []
    ref = builds[-1]["payload"]["components"]
    findings = []
    for repo, locations in COMPONENTS:
        rsha = ref.get(repo)
        for device, path in locations.items():
            osha = _organic_sha(device, path)
            if osha is None:
                findings.append({"repo": repo, "device": device, "path": path,
                                 "class": "MISSING-ORGANIC", "reference": rsha, "organic": None,
                                 "meaning": "the reference estate has this; the organic one does not"})
                continue
            if osha == rsha:
                continue
            # direction: is the organic copy an ancestor of the reference, or vice versa?
            cmd = f"git -C {path} merge-base --is-ancestor {osha} {rsha}"
            rc, _, _ = (sh(cmd) if device == "this-mac" else ssh(_host(device), cmd))
            klass = ("BEHIND" if rc == 0 else "AHEAD-OR-FORKED")
            findings.append({
                "repo": repo, "device": device, "path": path, "class": klass,
                "reference": rsha, "organic": osha,
                "meaning": ("organic never pulled — deployment gap" if klass == "BEHIND"
                            else "organic has commits the public repo does not — publication gap or fork"),
            })
    f = _append("reference.diff", {"findings": findings, "count": len(findings),
                                   "reference_build": builds[-1]["frame_hash"], "at": _utc()})
    print(f"reference.diff frame {f['seq']} — {len(findings)} divergence(s)")
    return findings


def report():
    frames = load()
    diffs = [f for f in frames if f["kind"] == "reference.diff"]
    if not diffs:
        print("no diff yet — run `diff`")
        return
    findings = diffs[-1]["payload"]["findings"]
    if not findings:
        print("no divergence — the organic estate matches the public source of truth")
        return
    by = {}
    for x in findings:
        by.setdefault(x["class"], []).append(x)
    for klass in ("BEHIND", "AHEAD-OR-FORKED", "MISSING-ORGANIC"):
        rows = by.get(klass, [])
        if not rows:
            continue
        print(f"\n{klass} ({len(rows)}) — {rows[0]['meaning']}")
        for x in rows:
            print(f"  {x['device']:14} {x['repo']:24} organic {x['organic'] or '—'} vs reference {x['reference']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    {"build": build, "diff": diff, "report": report}.get(cmd, report)()
