# HBS-Bank-Portfolio Setup & Platform Adaptation

When this skill is first installed, ask your AI to perform the following checks and adaptations. No scripts needed — your AI can handle all of this with its built-in tools.

## 1. Environment Check

Have your AI verify:

- **Python 3.9+**: `python3 --version`. If missing, guide the user to install via Homebrew or python.org.
- **numpy**: Check `import numpy`. If missing: `pip install numpy`.
- **pandas**: Check `import pandas`. If missing: `pip install pandas`.
- **Standard library**: json, math, statistics, pathlib, datetime, csv (all stdlib — should always be present).

Run the automated scan:
```bash
python3 scripts/env_scan.py
```

Report any issues to the user with the exact fix command.

Optional dependencies:
- `akshare` — for automatic market data fetching from Eastmoney. If missing, the skill will prompt the user to provide market data manually.

```bash
pip install akshare
```

## 2. Platform Adaptation

Have your AI check and adapt:

- **Frontmatter format**: Does `SKILL.md`'s YAML frontmatter match your platform's expected schema?
  - OpenClaw: `user-invocable` at top level, `metadata` as single-line JSON
  - Claude Code: skill definition in `.claude/skills/` or invoked via SKILL.md
  - Other platforms: adapt as needed. If unsure, ask the user.

- **Tool name mapping**: Platform-specific tool names may differ:

| OpenClaw (source) | Claude Code | Notes |
|-------------------|-------------|-------|
| `exec` | `Bash` | Shell command execution |
| `Read` | `Read` | File reading (same name) |
| `Write` | `Write` | File writing (same name) |
| `web_fetch` | `WebFetch` | Web page fetching |
| `web_search` | `WebSearch` | Web search |
| `sessions_spawn` | `Agent` | Subagent spawn — supports parallel via multiple Agent calls in one message |

- **Spawn support**: Both OpenClaw and Claude Code support parallel subagent execution. The pipeline's flat topology (main session directly spawns L1 and L3) works on both platforms.
  - Claude Code: Use `Agent` with `run_in_background: true` for async execution
  - Depth limit = 1 on both platforms — subagents cannot spawn sub-sub-agents

- **Web search**: L1 macro assessment uses `web_search` for rate direction, credit cycle, and regulatory context. If unavailable, AI knowledge base is sufficient fallback.

## 3. Depth Skill Locator

Portfolio needs Depth's `final_output.json`. By default, it searches:

```
../hbs-bank-depth/data/*/final_output.json
```

If Depth is installed at a different path, the user will be prompted at runtime. No configuration file needed.

## 4. Verification

Have your AI run a quick smoke test:

```bash
python3 --version
python3 -c "import numpy, pandas, json, math, statistics, pathlib; print('OK')"
```

Report: "HBS-Bank-Portfolio is ready. Configured for {platform_name}. Python {version}. All dependencies available."

## 5. References

- `SKILL.md` — Skill entry point and full execution flow (OpenClaw format, primary source)
- `CLAUDE.md` — Claude Code adaptation guide
- `PLATFORMS.md` — Known platform differences and adaptation notes
- `README.md` — Project overview
