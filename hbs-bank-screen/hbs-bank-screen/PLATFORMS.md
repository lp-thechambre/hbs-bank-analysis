# Platform Compatibility Notes

Known differences across AI agent platforms. Each platform's AI should handle adaptation during setup (see SETUP.md).

## OpenClaw (primary target)

| Feature | Status | Notes |
|---------|--------|-------|
| Frontmatter | Native | `user-invocable` at top level, `metadata` as single-line JSON |
| Tool: exec | `exec` | |
| Tool: spawn | `sessions_spawn` | True parallel execution for Quant+Edge, 5×Qual groups |
| Tool: web_fetch | `web_fetch` | Eastmoney data fetching |
| Tool: web_search | `web_search` | Edge spawn external signals (max 3 calls) |
| Batch processing | Full | Parallel spawn waves work as designed |

## Claude Code

| Feature | Status | Notes |
|---------|--------|-------|
| Frontmatter | Adaptation needed | OpenClaw frontmatter schema differs from Claude Code skill format |
| Tool: exec | `Bash` | Equivalent, different name |
| Tool: spawn | `Agent` | **Supports true parallel execution** — multiple Agent tool calls in one message run concurrently. Also supports `run_in_background` for async execution and `isolation: "worktree"` for git worktree isolation |
| Tool: web_fetch | `WebFetch` | Equivalent, different name |
| Tool: web_search | `WebSearch` | Equivalent, different name |
| Depth limit | Same as OpenClaw | Subagents cannot spawn sub-sub-agents (depth limit = 1). This is the shared constraint that motivated ARCHITECTURE-v2's main session orchestration |
| Batch processing | Full | Parallel spawn waves work via multiple Agent calls in one message. 3–5 parallel subagents is the practical sweet spot |

**v2 compatibility**: The v2 architecture (main session directly spawns Quant+Edge, then 5×Qual, then Synthesis) is fully compatible with Claude Code. The depth limit of 1 is not a problem since v2 no longer uses nested spawns.

## Shared Architectural Constraint

Both OpenClaw and Claude Code enforce a **subagent depth limit of 1**: subagents cannot spawn their own sub-sub-agents. This is the fatal flaw in ARCHITECTURE-v1's scheduler pattern (scheduler spawn tries to spawn worker spawns). ARCHITECTURE-v2 resolves this by having the main session directly orchestrate all three spawn layers — a flat topology that works on both platforms.

## Other Platforms

For platforms not listed above, follow the adaptation guide in SETUP.md. The flat spawn topology (main session → direct spawns) is designed to work on any platform that supports subagents.

## Adaptation Strategy

Rather than maintaining multiple SKILL.md versions, we use a **single source + AI-driven adaptation** approach:

1. `SKILL.md` is maintained in OpenClaw format (primary development platform)
2. `SETUP.md` guides each platform's AI to adapt frontmatter and tool mappings
3. The v2 flat spawn topology works on all platforms that support subagents — no platform-specific degradation needed
4. Tool name mapping is the main adaptation required (exec→Bash, sessions_spawn→Agent, etc.)

This avoids the maintenance burden of multiple branches while supporting all platforms.
