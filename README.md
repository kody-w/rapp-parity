# rapp-parity

**Is your live estate still the same as the source it came from?**

You cannot answer that from inside the estate. A system that grew over months — hand
fixes, half-migrations, code that never got pushed, code that never got pulled — has no
way to see its own drift, because there is nothing to compare against.

So build the comparison. `rapp-parity` clones your public components onto a clean
machine, then checks every live copy against that reference. Each divergence comes back
with the one thing a plain diff cannot give you: **which side is right.**

```
BEHIND            the live copy never pulled          → deployment gap
AHEAD-OR-FORKED   the live copy has unpublished work  → publication gap, or a real fork
MISSING-ORGANIC   the reference has it, you don't     → something never arrived
```

## Use it

```bash
python3 parity.py build     # clone/refresh the reference from public source
python3 parity.py diff      # compare every live copy against it
python3 parity.py report    # read the divergences, grouped by direction
```

Configure your estate in `parity.json`:

```json
{
  "reference_host": "deck@192.168.1.50",
  "reference_root": "~/parity-reference",
  "components": [
    ["you/your-repo", {"local": "~/code/your-repo", "server": "~/deploy/your-repo"}]
  ]
}
```

`reference_host` should ideally be a machine that never grew organically — a fresh box,
a container, a spare laptop. A pristine template is the entire point.

## Why frames

Every build and every comparison is appended to `parity.jsonl` as a
[rapp/1](https://github.com/kody-w/rapp-1) frame, verified end to end. That turns a
report into a record: *when did this instance start drifting?* becomes a query instead
of an archaeology project.

## The biology, if you want it

This is **DNA mismatch repair**. Finding a mismatch is easy; knowing which strand is
wrong is the hard part — and a cell that guesses wrong "repairs" the correct strand into
the error, permanently. Biology solves it with **strand discrimination**: the parent
strand is marked, so repair always flows toward the template.

Your public repo is the marked parent. Your live estate is the daughter copy that
accumulated replication errors. The diff finds mismatches; the classification is strand
discrimination.

Where the analogy breaks, and it matters: biological repair always flows toward the
parent. Yours cannot, because sometimes the daughter is right — a local fix that was
never published. That is `AHEAD-OR-FORKED`, and it is the one class that needs judgment
rather than mechanism.

## Lineage

The idea started as **molt** — an organism shedding a worn copy and regrowing from its
own template ([git-molt](https://github.com/kody-w/git-molt) still carries that name for
self-modifying agents). Molting names the renewal; parity names what you actually test.
The pattern kept the mechanism and changed its name once the shape was clear.
