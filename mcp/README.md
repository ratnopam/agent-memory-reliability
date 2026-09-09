# MCP server

An MCP server exposing the nine record operations of `version2/SPEC.md` §3 over one in-process
`ReferenceSystem`. Stdio transport. It is a translation layer and nothing else: JSON in, a
call into the system, JSON out, and a protocol error turned into a tool error with a coded
prefix. Every decision that could be argued about lives in `systems/reference/`, where the
conformance suite can see it.

## Running it

```
python -m pip install -e ".[mcp]"
python mcp/server.py
```

`AMR_FORGET_MODE` sets the default forget mode (`tombstone`, the default; `cascade`;
`erase`). `memory_forget` can override it per call, and `memory_capabilities` reports
what is in force.

As a client entry — for Claude Desktop, Claude Code, or anything else that speaks MCP:

```json
{
  "mcpServers": {
    "agent-memory": {
      "command": "python",
      "args": ["/absolute/path/to/agent-memory-reliability/mcp/server.py"],
      "env": {"AMR_FORGET_MODE": "tombstone"}
    }
  }
}
```

State is in-process and lives as long as the server does. Nothing is written to disk, and a
restart is an empty store. That is deliberate for a reference server: durability is a
property of an adapter, and `ReferenceSystem` declares `durability: round-trip`, meaning it
can serialise and be reopened, not that this server does it for you.

This directory has no `__init__.py`. A package named `mcp` at the repository root would
shadow the installed one.

## Tools

| Tool | Notes |
|---|---|
| `memory_write` | `sources` is the citation list. A source id that does not resolve rejects the write and persists nothing. Write ancestors first. |
| `memory_get` | `outcome` is `ok`, `forgotten`, or `not_found`. The last two are never collapsed. |
| `memory_provenance` | Every transitive ancestor once. An ancestor in another scope has `opaque: true`: id and declared confidence visible, content withheld. |
| `memory_effective_confidence` | `min(declared, min over ancestors)`. Empty chain is 1.0. |
| `memory_descendants` | Everything derived from a memory, transitively. |
| `memory_revise` | Declared confidence and a reason. Nothing else about a memory can change. Lowering propagates; raising does not lift a descendant past its own declared value. |
| `memory_revisions` | The revision log, oldest first. The reader for what `memory_revise` records. |
| `memory_forget` | `mode` defaults to the server default. The receipt names every affected memory and every confidence that moved. |
| `memory_list_scope` | Memories native to a scope. A memory shared from elsewhere is readable but not listed. |
| `memory_capabilities` | The declaration of `version2/SPEC.md` §8. |

Every tool takes `scope`, defaulting to `default`.

The other three operations of §3 — `grant`, `revoke`, `grants` — are deliberately not
tools. A client that can widen its own visibility is not isolated by anything. Grants are
configuration, set by whoever runs the server.

## Errors

A tool error's text begins with a code, so a client can branch without parsing English:
`cycle`, `unresolved_source`, `forgotten`, `scope`, `not_found`, `invalid_argument`. A
memory this scope cannot see is `not_found`, exactly as an id that was never assigned is;
the `scope` code is reachable only when a grant already made the memory readable.
Anything else escaping a tool is a bug in the server, and the SDK withholds its text from
the caller.

## The one thing worth knowing before you use it

`memory_forget` with `mode: "erase"` can make a surviving memory *more* confident, because
its chain got shorter and the minimum now runs over fewer records. The receipt says so —
each affected memory gets a delta, with `inflated: true` where it happened — but the number
you read afterwards is higher than the number you read before, and nothing is broken. See
`taxonomy/erasure-inflation.md`. `tombstone` keeps the chain position and does not have
this behaviour, which is why it is the default.

## Test

```
make mcp-test
```

Starts the server as a subprocess, talks to it over stdio with the official client, writes
a derivation, and checks the arithmetic and the receipt. The conformance suite does not
import `mcp`: `make test`, `make reproduce`, and `make determinism` pass without it
installed.
