# Platform Compatibility Notes

Known differences across AI agent platforms. Each platform's AI should handle adaptation during setup (see SETUP.md).

## OpenClaw (primary target)

| Feature | Status | Notes |
|---------|--------|-------|
| Frontmatter | Native | `user-invocable` at top level, `metadata` as single-line JSON |
| Tool: exec | `exec` | |
| Tool: spawn | `sessions_spawn` | True parallel execution |
| Tool: web_search | `web_search` / `web_fetch` | Browser headless mode configurable |
| Batch processing | Full | Parallel spawn waves work as designed |

## Claude Code

| Feature | Status | Notes |
|---------|--------|-------|
| Frontmatter | Adaptation needed | Nested YAML under `metadata.openclaw` |
| Tool: exec | `Bash` | Different name |
| Tool: spawn | `Agent` | Supports true parallel execution — multiple Agent tool calls in one message run concurrently. Also supports `run_in_background` for async execution |
| Tool: web_search | `WebSearch` / `WebFetch` | Different casing |
| Batch processing | Full | Parallel spawn waves work via multiple Agent calls in one message |

## Other Platforms

For platforms not listed above, follow the adaptation guide in SETUP.md. The flat spawn topology (main session → direct spawns) is designed to work on any platform that supports subagents.

## Adaptation Strategy

Rather than maintaining multiple SKILL.md versions, we use a **single source + AI-driven adaptation** approach:

1. `SKILL.md` is maintained in OpenClaw format (primary development platform)
2. `SETUP.md` guides each platform's AI to adapt frontmatter and tool mappings
3. Platform-specific limitations (e.g., no spawn) are handled by adjusting `batch_config.json`

This avoids the maintenance burden of multiple branches while supporting all platforms.
