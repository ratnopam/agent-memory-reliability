# Recorded tool calls

One file per session, JSON lines. The first line is a header — the trace version, the
bound scope if there was one, and the default forget mode — and every line after it is one
tool call: a sequence number, the tool, its arguments, and either the result or the error
code. No timestamps, because a field that cannot be reproduced is a field every replay
reports as a difference.

Record one by starting the server with `--trace FILE`, or by setting `AMR_MCP_TRACE`:

```
AMR_MCP_TRACE=run.jsonl python mcp/server.py
```

Replay it against a fresh system, comparing every value with the one recorded:

```
amr replay run.jsonl
```

The exit status is non-zero if anything came back different. Replay needs no MCP package:
the calls go through the same translation the server uses, which is in `amr.toolcalls`,
not in `mcp/server.py`.

## Before you commit one

**A trace contains whatever was written.** The arguments are recorded verbatim, so the
content of every memory is in the file, as is every scope name. That is the point — the
replay has to make the same calls — but it means a trace of a real session is a copy of
real data, under a filename that looks like a log. Record only content you are willing to
publish, and treat a trace from anywhere else as the data it carries rather than as
telemetry.

A forget does not reach backwards into a file already written. If a record was forgotten
because someone asked for it to be, a trace that still holds its content has not honoured
the request; delete the trace.

## What is here

| File | Session |
|---|---|
| `scripted-demo.jsonl` | The seven acts of [docs/try-it-with-claude.md](../../docs/try-it-with-claude.md), recorded by `mcp/test_try_it_script.py` against an unbound server. Its contents are the document's own invented incident. |

The suite replays every trace in this directory (`properties/test_traces.py`), so a value
that moves fails the build rather than ageing quietly in a file.
