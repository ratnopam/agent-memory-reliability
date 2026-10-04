# Try it with Claude Desktop

Run the trust layer's checks by talking to it. No terminal after setup. Claude calls the
layer's MCP tools and shows you what they return; **the numbers come from the tool, not from
Claude**. About ten minutes.

## 1. One-time setup

Install the server's one dependency into the project's virtual environment:

```
cd <repo> && source .venv/bin/activate && pip install -e ".[mcp]"
```

Add the server to Claude Desktop (Settings → Developer → Edit Config). The file is
`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS:

```json
{
  "mcpServers": {
    "amr-memory": {
      "command": "<repo>/.venv/bin/python",
      "args": ["<repo>/mcp/server.py"]
    }
  }
}
```

Use absolute paths; Desktop does not inherit your shell. Check `mcp/README.md` if the launch
command differs. Quit Claude Desktop completely (Cmd+Q) and reopen it. In a new chat, ask:
*"List the tools from amr-memory."* You should see ten.

Two facts to know before you start:

- **State lives in the server process.** Quitting Desktop resets it, and ids start again at
  `m001`. Every expected id below assumes a fresh start.
- **Approve tool prompts** (allow for this chat) before you start, so they don't interrupt.

## 2. Paste this first

```
You are a test operator for a memory trust layer exposed as MCP tools (server: amr-memory).
Rules:
1. Use only the amr-memory tools, one call at a time, in order.
2. Use scope "demo" on every call that takes a scope, unless I name another scope.
3. Run each step exactly once. Never retry. Never make extra calls.
4. Use exactly the confidence numbers I give. Never choose your own.
5. After each step print the tool called and the raw values returned (ids, confidences,
   errors) in a code block. Quote results verbatim. Do not interpret them.
6. Remember each returned id under the letter I give it (a, b, c...).
Reply "Ready" and wait.
```

## 3. The script

Paste one act at a time. "Expect" lists the values to check, not the exact formatting.

### Act 0: what the system declares

```
Step 0. Call the capabilities tool and print the declaration verbatim.
```

Expect: forget modes `cascade`, `erase`, `tombstone`; default `tombstone`; empty chain `1.0`;
revision `logged`; durability `round-trip`. The capabilities tool is the one tool that takes
no scope, so rule 2 does not apply to it.

### Act 1: confidence cannot outscore its weakest source

```
Step 1. Write three memories, one call each, in order:
a) content "Incident report: checkout latency degraded after the 14:05 deploy", declared
   confidence 0.90, no sources
b) content "Oncall note: probably the memory leak again", declared confidence 0.40,
   sources [a]
c) content "Agent summary: root cause confirmed as a memory leak", declared confidence 0.95,
   sources [b]
Step 2. For c, call the effective-confidence tool and the provenance tool, then print one
line: declared vs effective for c.
```

Expect: ids `m001`, `m002`, `m003`. Effective for `c` is **0.40** (declared 0.95). The provenance
walk lists `m001` and `m002` as ancestors, and carries each node's declared confidence — which
is where the declared 0.95 comes from, so step 2 needs no third call.

### Act 2: revise a source and everything below it moves

```
Step 3. Revise a: new declared confidence 0.20, reason "runbook entry retracted". Print the receipt.
Step 4. Effective confidence of b, then of c.
Step 5. Call the revisions tool for a and print the history.
```

Expect: receipt before 0.90, after 0.20, with `m002` and `m003` each moving 0.40 → 0.20.
Effective for `b` and `c` is **0.20**. History shows one entry, with the reason and with no
deltas of its own: the log records what was revised, and the deltas were in the live receipt.

### Act 3: forget, mode tombstone

```
Step 6. Write a fresh chain:
d) "Runbook: p99 checkout SLO is 250 ms", 0.90, no sources
e) "Customer chat paraphrase: the SLO is about 400 ms", 0.40, sources [d]
f) "Agent plan: raise the memory limit to 4Gi", 0.95, sources [e]
Step 7. Effective confidence of f.
Step 8. The customer behind e asks to be forgotten. Forget e with mode tombstone. Print the
receipt verbatim.
Step 9. Get e. Then effective confidence of f. Then provenance of f.
```

Expect: ids `m004`–`m006`. Step 7: **0.40**. Receipt: mode tombstone, `m005` under both
`forgotten` and `tombstoned`, `m006` delta 0.40 → 0.40. `get e` reports **forgotten** (not
"not found") with a null record. Effective for `f` stays **0.40**, and the walk still passes
through `m005`, now marked `tombstoned`.

### Act 4: forget, mode erase (the finding)

```
Step 10. Write the same chain again as g, h, i: same contents and numbers as d, e, f; h has
sources [g], i has sources [h].
Step 11. Effective confidence of i.
Step 12. The same request arrives for h. Forget h with mode erase. Print the receipt verbatim.
Step 13. Get h. Then effective confidence of i. Then provenance of i.
Step 14. Print one table for f and i: declared confidence, effective before the forget,
effective after, and forget mode.
```

Expect: ids `m007`–`m009`. Step 11: 0.40. Receipt: mode erase, `tombstoned` empty, `m009` delta
**0.40 → 0.95** flagged `inflated`. `get h` reports forgotten. Effective for `i` is **0.95**,
and its provenance chain is empty. The step 14 table reads: `f` 0.95 / 0.40 / 0.40 / tombstone;
`i` 0.95 / 0.40 / **0.95** / erase.

The receipt saying `inflated` is the layer reporting the finding on itself. An erase that left
no marker is what let `i` rise, and a store that did not report the rise would leave the agent
holding a number it never earned.

### Act 5 (optional): forget, mode cascade

```
Step 15. Write j) "Runbook: rollout window is Tuesday", 0.90; k) "Chat paraphrase: maybe
Wednesday", 0.40, sources [j]; l) "Agent plan: schedule the rollout", 0.95, sources [k].
Step 16. Forget k with mode cascade. Print the receipt. Then get l.
```

Expect: ids `m010`–`m012`. Both `m011` and `m012` under `forgotten`, and no deltas — cascade
forgot the descendant rather than re-bounding it. `get l` reports forgotten; `j` survives.

### Act 6: a mistyped source is rejected

```
Step 17. List the memories in scope demo. Then write "Summary of the incident", declared
0.80, with sources ["m999"]. Show the exact error. List the memories again and say
whether anything changed.
```

Expect: the error reads `unresolved_source: source 'm999' does not resolve in scope 'demo'`;
the two lists are identical. The code before the colon is what a client branches on.

### Act 7 (optional): another scope cannot see it

```
Step 18. For this step only, use the scopes I name. In scope "hr" write "Employee on leave
through Friday", 0.90. Then, in scope "ops", get that id. Then, in scope "ops", get "m999".
Print the two results side by side.
```

Expect: id `m013` for the write. Both reads from `ops` return exactly
`{"outcome": "not_found", "record": null}` — nothing tells apart a record that is there and
hidden from one that never existed. **This act needs an unbound server.** If yours was started
with `--scope` or `AMR_MCP_SCOPE`, the write to `hr` is refused with the `scope:` code instead,
which is the binding working; skip the act.

## 4. Checklist

| Check | Expected |
|---|---|
| Effective of `c` (a → b → c) | 0.40 while declared is 0.95 |
| After revising `a` to 0.20 | `b` and `c` become 0.20 |
| Forget `e`, tombstone | `f` stays 0.40; `get e` says forgotten |
| Forget `h`, erase | `i` rises 0.40 → 0.95 |
| Mistyped source | `unresolved_source`; nothing written |
| Forgotten vs never existed | distinct outcomes (`forgotten` vs `not_found`) |

## 5. Variant: let Claude pick its own confidence

Repeat Act 1 with new ids, replacing rule 4 with: *"Choose your own honest confidence. b is
hearsay from a chat message; c is your summary of b."* The numbers will vary. These must hold
on every run: `effective(c) ≤ effective(b) ≤ declared(b)`. That is the point. Whatever the
model claims, the layer bounds it by what the claim rests on.

## 6. If something looks wrong

| Symptom | Fix |
|---|---|
| Ids don't start at `m001` | The server wasn't fresh. Quit and reopen Desktop, rerun from Act 0. |
| No tools appear | Validate the JSON, use absolute paths, check `~/Library/Logs/Claude/mcp-server-amr-memory.log`. |
| Claude makes extra calls or retries | Re-paste the rules, or restart. |
| A value differs from "Expect" | Ask Claude to print the raw tool result. If it still differs, that is a finding. Open an issue with the transcript. |

## 7. What this shows and doesn't

The confidences are scripted so the run is reproducible. Claude relays; the layer computes.
The server trusts the caller to name its own scope: the layer enforces isolation between
scopes, but this server does not establish who is calling.

## 8. Two options worth knowing

**Bind a scope.** Add `"--scope", "demo"` to the `args` in the config above, or set
`AMR_MCP_SCOPE=demo`, and the connection acts in that scope whatever the caller asks for. A
call naming a different scope is refused with the `scope:` code rather than redirected — the
server does not quietly decide where a record belongs. With a scope bound you can drop rule 2
and skip Act 7, which needs two scopes.

**Record the session.** Add `"--trace", "<repo>/run.jsonl"`, or set `AMR_MCP_TRACE` to a path,
and the server appends one line per tool call: the sequence number, the tool, its arguments,
and the result or the error code. No timestamps. Afterwards, from the terminal:

```
amr replay run.jsonl
```

That re-executes your calls against a fresh system and compares every value with the one
recorded, exiting non-zero if anything differs. It is the honest way to answer "did Claude
really get that number?" — and the file is also what you attach to an issue when a value
differs from "Expect". A trace holds the content of everything written, so read it before you
send it anywhere; see [examples/traces/README.md](../examples/traces/README.md).
