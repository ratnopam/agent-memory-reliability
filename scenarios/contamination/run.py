"""The contamination simulation: how far one low-confidence belief travels.

Three simulated agents -- ``support-triage``, ``sre``, ``platform`` -- share one reference
store for a fixed number of rounds. Each round each agent reads a sample of what it can
see, derives one new memory from one or two of those, and writes it with a declared
confidence drawn from a fixed distribution.

There is no language model anywhere. An agent is a policy over a seeded PRNG, because the
number this produces has to be reproducible twice, and a model's output is not. Realism is
what a case study is for; this is a measurement.

In round one ``support-triage`` writes two conflicting beliefs about the same fact -- the
runbook's 250ms at 0.95 and a chat message's 400ms at 0.40, both roots -- and after that
nothing is special-cased again. Three arms run with the same seed, the same schedule, and
the same policies, differing only in what the agent is told and what it is allowed to do:

* **ungated**  -- the agent sees only *declared* confidence and may cite anything it reads.
* **surfaced** -- the agent *sees* effective confidence and nothing is withheld; a
  candidate's chance of being cited is proportional to that number, so a 0.40 rumour is
  unlikely rather than impossible. Visibility without enforcement.
* **gated**    -- a read gate withholds any memory whose *effective* confidence is below
  ``tau`` from being cited as a source. The agent may still read it; it may not build on it.

The gated arm is zero by construction at ``tau`` 0.5: the injected belief is declared 0.40,
so it and every descendant are bounded below the threshold and cannot be cited at all. It
marks the boundary; surfaced is the arm that measures anything.

Four things are measured per arm: how many writes inherited the 0.40 belief, how many were
declared at 0.9 or above while their effective confidence sat at or below ``tau`` (the
declared-versus-effective gap), how deep the contaminated subtree got, and the totals.

Each agent owns a scope named after its role, and the three scopes grant each other read
access, so citing a colleague's memory goes through the same grant machinery SPEC.md 7
specifies rather than a shortcut. A foreign ancestor is opaque in the walk but still
carries its confidence, which is the property the whole measurement rests on.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

from amr import results
from amr.protocol import ForgetMode, MemoryId, MemorySystem, Origin, UnresolvedSourceError
from amr.registry import named
from scenarios.contamination import chart

SYSTEM = "reference"
MODE = ForgetMode.TOMBSTONE
SCHEMA = "0.1"

ROLES = ("support-triage", "sre", "platform")
ARMS = ("ungated", "surfaced", "gated")
ROUNDS = 60
#: The read gate's threshold. Named ``tau`` here and everywhere; never abbreviated further.
TAU = 0.5
DEFAULT_SEED = 7

#: Candidates an agent inspects per round. Identical in every arm, so ``reads`` is a control.
READ_SAMPLE = 4
CONFIDENCE_CHOICES = (0.95, 0.90, 0.85, 0.70, 0.60)
CONFIDENCE_WEIGHTS = (3, 3, 2, 1, 1)
CITATION_SIZES = (1, 1, 2)
#: How often an agent cites an id it never actually saw. A strict store rejects the write.
HALLUCINATION_RATE = 0.1
#: "Stated confidently": the declared floor above which a low effective value is a gap.
CONFIDENT = 0.9

BOOTSTRAP = (
    ("support-triage", "checkout complaints cluster on mobile", 0.80, "tickets", "T-8814"),
    ("sre", "the p99 alert fired 41 times last week", 0.90, "metrics", "dash/p99"),
    ("platform", "the gateway retries idempotent reads twice", 0.70, "runbook", "gw/retry"),
)
HIGH = ("p99 SLO is 250ms", 0.95, "runbook", "slo/p99")
LOW = ("p99 SLO is 400ms", 0.40, "chat", "#ops/2026-03-11")

DERIVED = {
    "support-triage": ("customer impact summary", "escalation draft", "ticket merge note"),
    "sre": ("incident hypothesis", "latency budget note", "alert tuning proposal"),
    "platform": ("capacity plan revision", "gateway config change", "rollout gate"),
}


@dataclass
class Write:
    """One thing an agent put in the store, and what it said it was based on."""

    id: MemoryId
    role: str
    round: int
    declared: float
    sources: tuple[MemoryId, ...]


@dataclass
class Arm:
    """One run of the same policies under one citation rule."""

    name: str
    writes: list[Write] = field(default_factory=list)
    reads: int = 0
    rejected: int = 0
    abstained: int = 0

    @property
    def gated(self) -> bool:
        return self.name == "gated"

    @property
    def surfaced(self) -> bool:
        return self.name == "surfaced"


# --------------------------------------------------------------------- policies


def citable(system: MemorySystem, arm: Arm, role: str, seen: list[MemoryId], tau: float):
    """What the agent is *allowed* to cite. Only the gated arm withholds anything.

    Ungated and surfaced: everything the agent read is fair to cite. Under ``surfaced``
    the effective number shapes the choice (see ``choose``) but refuses nothing.

    Gated: drop anything whose *effective* confidence is below ``tau``. Effective, not
    declared, is the point -- a 0.95 analysis resting on a 0.40 rumour is withheld too,
    and that is what stops the second generation of inheritance rather than the first.
    """
    if not arm.gated:
        return list(seen)
    return [
        memory_id
        for memory_id in seen
        if system.effective_confidence(memory_id, role) >= tau
    ]


def choose(
    system: MemorySystem,
    arm: Arm,
    rng: random.Random,
    role: str,
    allowed: list[MemoryId],
    wanted: int,
) -> list[MemoryId]:
    """Which of the allowed candidates the agent actually cites.

    Ungated and gated pick uniformly: neither has a preference among what it may cite.
    Surfaced weights each candidate by its effective confidence, drawing without
    replacement so a two-source write cites two distinct records. Deliberately the
    simplest monotone rule: no threshold, no tuning constant, nothing to fit.
    """
    if not arm.surfaced:
        return rng.sample(allowed, wanted)
    remaining = list(allowed)
    weights = [system.effective_confidence(m, role) for m in remaining]
    picked: list[MemoryId] = []
    while len(picked) < wanted:
        total = sum(weights)
        if total <= 0.0:
            # Every candidate at 0.0. Nothing is withheld here, so the agent still
            # writes; it just has no preference left to express.
            picked.extend(remaining[: wanted - len(picked)])
            break
        target = rng.random() * total
        index = 0
        while index < len(weights) - 1 and target >= weights[index]:
            target -= weights[index]
            index += 1
        picked.append(remaining.pop(index))
        weights.pop(index)
    return picked


# ------------------------------------------------------------------- simulation


def simulate(arm: Arm, seed: int, rounds: int = ROUNDS, tau: float = TAU) -> dict:
    """Run one arm and measure it. Same seed and same arm gives the same bytes."""
    rng = random.Random(seed)
    system = named(SYSTEM, MODE)
    for owner in ROLES:
        for reader in ROLES:
            if owner != reader:
                system.grant(owner, reader)

    pool: list[MemoryId] = []
    for role, content, declared, kind, ref in BOOTSTRAP:
        pool.append(system.write(content, declared, scope=role, origin=Origin(kind, ref)))

    low = ""
    for number in range(1, rounds + 1):
        if number == 1:
            high = _inject(system, HIGH)
            low = _inject(system, LOW)
            pool.extend((high, low))
        for role in ROLES:
            seen = rng.sample(pool, min(READ_SAMPLE, len(pool)))
            arm.reads += len(seen)
            allowed = citable(system, arm, role, seen, tau)
            if not allowed:
                arm.abstained += 1
                continue
            wanted = min(rng.choice(CITATION_SIZES), len(allowed))
            sources = tuple(sorted(choose(system, arm, rng, role, allowed, wanted)))
            declared = rng.choices(CONFIDENCE_CHOICES, weights=CONFIDENCE_WEIGHTS)[0]
            content = f"{DERIVED[role][rng.randrange(3)]} (round {number})"
            if rng.random() < HALLUCINATION_RATE:
                # An agent citing an id it never read. The store rejects the whole write
                # rather than storing it with the bad edge dropped (SPEC.md I1.6), so the
                # agent gets one retry with only what it actually saw.
                try:
                    system.write(
                        content, declared, sources=(*sources, "m900"), scope=role
                    )
                except UnresolvedSourceError:
                    arm.rejected += 1
            memory_id = system.write(content, declared, sources=sources, scope=role)
            pool.append(memory_id)
            arm.writes.append(Write(memory_id, role, number, declared, sources))

    return measure(system, arm, low, tau, rounds)


def _inject(system: MemorySystem, belief: tuple) -> MemoryId:
    """One of the two conflicting round-one roots, written by ``support-triage``."""
    content, declared, kind, ref = belief
    return system.write(content, declared, scope=ROLES[0], origin=Origin(kind, ref))


# ---------------------------------------------------------------------- metrics


def measure(
    system: MemorySystem, arm: Arm, low: MemoryId, tau: float, rounds: int = ROUNDS
) -> dict:
    """What the arm produced, asked of the store rather than of the policy's notes."""
    inherited = [
        write
        for write in arm.writes
        if low in system.provenance(write.id, write.role).nodes
    ]
    inflated = [
        write
        for write in arm.writes
        if write.declared >= CONFIDENT
        and system.effective_confidence(write.id, write.role) <= tau
    ]
    below = frozenset(write.id for write in inherited)
    assert below == system.descendants(low, ROLES[0]), (
        "the store's descendant closure and the provenance walk disagree"
    )
    denominator = len(arm.writes)
    return {
        "arm": arm.name,
        "gated": arm.gated,
        "surfaced": arm.surfaced,
        "denominator": denominator,
        "inherited_count": len(inherited),
        "inherited_fraction": _fraction(len(inherited), denominator),
        "inflated_count": len(inflated),
        "inflated_fraction": _fraction(len(inflated), denominator),
        "max_chain_depth": depth_beneath(low, arm.writes),
        "totals": {
            "rounds": rounds,
            "writes": denominator,
            "reads": arm.reads,
            "strict_write_rejections": arm.rejected,
            "abstentions": arm.abstained,
        },
    }


def depth_beneath(low: MemoryId, writes: list[Write]) -> int:
    """Longest path from the 0.40 belief downward. It is a root, so its own depth is zero.

    Measured from what the policies actually cited rather than from the store, because it
    is a fact about how the belief spread, not about how the store answers.
    """
    children: dict[MemoryId, list[MemoryId]] = {}
    for write in writes:
        for source in write.sources:
            children.setdefault(source, []).append(write.id)

    def longest(memory_id: MemoryId) -> int:
        return 1 + max((longest(child) for child in children.get(memory_id, ())), default=-1)

    return longest(low)


def _fraction(count: int, total: int) -> float:
    return 0.0 if total == 0 else round(count / total, 4)


# ----------------------------------------------------------------------- output


def record(root: Path, seed: int, tau: float = TAU, rounds: int = ROUNDS) -> dict:
    """All three arms, their parameters, and the commit. No timestamp: the bytes are the test."""
    arms = {name: simulate(Arm(name), seed, rounds=rounds, tau=tau) for name in ARMS}
    return {
        "scenario": "contamination",
        "schema": SCHEMA,
        "system": SYSTEM,
        "forget_mode": MODE.value,
        "seed": seed,
        "environment": results.environment(root),
        "parameters": {
            "roles": list(ROLES),
            "rounds": rounds,
            "tau": tau,
            "read_sample": READ_SAMPLE,
            "confidence_choices": list(CONFIDENCE_CHOICES),
            "confidence_weights": list(CONFIDENCE_WEIGHTS),
            "citation_sizes": list(CITATION_SIZES),
            "hallucinated_citation_rate": HALLUCINATION_RATE,
            "confident_declared_floor": CONFIDENT,
            "injected": {
                "high": {"content": HIGH[0], "declared": HIGH[1], "origin": HIGH[2]},
                "low": {"content": LOW[0], "declared": LOW[1], "origin": LOW[2]},
            },
        },
        "arms": arms,
    }


def table(document: dict) -> str:
    """The Markdown block appended to summary.md."""
    rows = [
        "## Contamination",
        "",
        (
            f"Seed {document['seed']}, {document['parameters']['rounds']} rounds, "
            f"three roles, tau {document['parameters']['tau']}. One belief declared "
            f"{LOW[1]} was injected in round 1."
        ),
        "",
        "| arm | writes | inherited | inflated (declared ≥ 0.9, effective ≤ tau) | depth |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name in ARMS:
        arm = document["arms"][name]
        rows.append(
            f"| {name} | {arm['denominator']} | "
            f"{arm['inherited_count']} ({arm['inherited_fraction']:.0%}) | "
            f"{arm['inflated_count']} ({arm['inflated_fraction']:.0%}) | "
            f"{arm['max_chain_depth']} |"
        )
    rows.extend(["", chart.caption(document["parameters"]["tau"])])
    return "\n".join(rows) + "\n"


def upsert(path: Path, body: str, heading: str = "## Contamination") -> None:
    """Replace the contamination block if there is one, else append. Run twice, same file."""
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if heading in existing:
        head, _, tail = existing.partition(heading)
        rest = tail.partition("\n## ")
        keep = f"\n## {rest[2]}" if rest[1] else ""
        existing = head.rstrip("\n") + "\n\n" + body + keep
    else:
        existing = (existing.rstrip("\n") + "\n\n" if existing else "") + body
    path.write_text(existing, encoding="utf-8")


#: Where the README embeds the chart from. Undated on purpose: a dated path in the README
#: goes stale silently the next time the results are regenerated, and nothing reads an
#: image. Refreshed only by a run that writes into ``results/<date>/`` — that is, by
#: ``make results`` and not by a gate running into a temporary directory. ``amr drift``
#: requires this file to be byte-identical to the newest dated one.
STABLE_CHART = Path("docs") / "contamination.svg"


def main(
    root: Path,
    seed: int = DEFAULT_SEED,
    out: Path | None = None,
    quiet: bool = False,
    tau: float = TAU,
    rounds: int = ROUNDS,
) -> int:
    document = record(root, seed, tau, rounds)
    deliberate = out is None
    directory = out or results.results_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "contamination.json"
    svg_path = directory / "contamination.svg"
    svg = chart.inherited_chart(document)
    json_path.write_text(results.serialise(document), encoding="utf-8")
    svg_path.write_text(svg, encoding="utf-8")
    upsert(directory / "summary.md", table(document))
    written = [json_path.name, svg_path.name]
    if deliberate:
        # Only a run that was asked to produce the committed results touches the tree
        # outside results/. A gate given --out leaves the repository exactly as it was.
        (root / STABLE_CHART).write_text(svg, encoding="utf-8")
        written.append(STABLE_CHART.as_posix())
    if not quiet:
        print(table(document), end="")
    inherited = ", ".join(
        f"{document['arms'][name]['inherited_fraction']:.0%} {name}" for name in ARMS
    )
    print(f"wrote {' and '.join(written)} — inherited {inherited}")
    return 0
