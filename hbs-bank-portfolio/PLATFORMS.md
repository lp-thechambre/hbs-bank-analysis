# Platform Compatibility Notes

Known differences across AI agent platforms. Each platform's AI should handle adaptation during setup (see SETUP.md).

## OpenClaw (primary target)

| Feature | Status | Notes |
|---------|--------|-------|
| Frontmatter | Native | `user-invocable` at top level, `metadata` as single-line JSON |
| Tool: exec | `exec` | Python scripts, mkdir, date |
| Tool: spawn | `sessions_spawn` | Parallel execution for L1 macro + cross-evaluation spawns |
| Tool: web_search | `web_search` | L1 macro search (rate direction, credit cycle) |
| Tool: web_fetch | `web_fetch` | External macro data if needed |
| Batch processing | Full | Parallel spawn waves work as designed |
| Browser policy | `headless` | Configured in SKILL.md frontmatter |

## Claude Code

| Feature | Status | Notes |
|---------|--------|-------|
| Frontmatter | Adaptation needed | OpenClaw frontmatter schema differs from Claude Code skill format |
| Tool: exec | `Bash` | Equivalent, different name |
| Tool: spawn | `Agent` | Supports true parallel execution — multiple Agent tool calls in one message run concurrently. Also supports `run_in_background` for async execution |
| Tool: web_search | `WebSearch` | Equivalent, different casing |
| Tool: web_fetch | `WebFetch` | Equivalent, different casing |
| Depth limit | Same as OpenClaw | Subagents cannot spawn sub-sub-agents (depth limit = 1). Flat topology works on both platforms |
| Batch processing | Full | Parallel spawn waves work via multiple Agent calls in one message |

## Shared Architectural Constraint

Both OpenClaw and Claude Code enforce a **subagent depth limit of 1**: subagents cannot spawn their own sub-sub-agents. The Portfolio pipeline's flat topology (main session → direct L1/L3 spawns) respects this constraint. L1 may internally split into 2-3 parallel spawns for banks > 8, but those are all launched from the main session.

## Pipeline-Specific Notes

### L1 Cross-Evaluation

- **OpenClaw**: Use 1 `sessions_spawn` for macro, then 1-3 `sessions_spawn` for cross-evaluation (split if > 8 banks)
- **Claude Code**: Use 1 `Agent` for macro, then 1-3 `Agent` calls in one message for cross-evaluation (parallel)

### Python Script Execution

All Python scripts run in the main session via `exec` (OpenClaw) or `Bash` (Claude Code). No subagent involved.

### Web Search Budget

L1 macro spawn uses `web_search` (max 5 calls). This is a directional macro assessment, not exhaustive research.

## Other Platforms

For platforms not listed above, follow the adaptation guide in SETUP.md. The flat spawn topology (main session → direct spawns) is designed to work on any platform that supports subagents.

## Adaptation Strategy

Rather than maintaining multiple SKILL.md versions, we use a **single source + AI-driven adaptation** approach:

1. `SKILL.md` is maintained in OpenClaw format (primary development platform)
2. `SETUP.md` guides each platform's AI to adapt frontmatter and tool mappings
3. The flat spawn topology works on all platforms that support subagents — no platform-specific degradation needed
4. Tool name mapping is the main adaptation required (exec→Bash, sessions_spawn→Agent, etc.)

This avoids the maintenance burden of multiple branches while supporting all platforms.
