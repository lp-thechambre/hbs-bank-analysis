# HBS-Bank-Screen Setup & Platform Adaptation

When this skill is first installed, ask your AI to perform the following checks and adaptations. No scripts needed — your AI can handle all of this with its built-in tools.

## 1. Environment Check

Have your AI verify:

- **Python 3.9+**: `python3 --version`. If missing, guide the user to install via Homebrew or python.org.
- **requests library**: Check `import requests`. If missing: `pip install requests`.
- **Standard library**: json, math, statistics, pathlib, csv (all stdlib — should always be present).

Run the automated scan:
```bash
python3 scripts/env_scan.py
```

Report any issues to the user with the exact fix command. The pipeline requires `requests`; all other dependencies are stdlib.

## 2. Platform Adaptation

Have your AI check and adapt:

- **Frontmatter format**: Does `SKILL.md`'s YAML frontmatter match your platform's expected schema?
  - OpenClaw: `user-invocable` at top level, `metadata` as single-line JSON
  - Claude Code: skill definition in `.claude/skills/` or `.claude/agents/`
  - Other platforms: adapt as needed. If unsure, ask the user.
- **Tool name mapping**: Platform-specific tool names may differ:
  - `exec` -> `Bash` (Claude Code)
  - `sessions_spawn` -> `Agent` (Claude Code) — supports parallel execution via multiple Agent calls in one message, plus `run_in_background` for async
  - `web_fetch` -> `WebFetch` (Claude Code)
  - `web_search` -> `WebSearch` (Claude Code)
- **Spawn support**: Both OpenClaw and Claude Code support parallel subagent execution. Multiple Agent calls in a single message run concurrently. ARCHITECTURE-v2's flat spawn topology (main session directly spawns all layers) works on both platforms without degradation.

## 3. Verification

Have your AI run a quick smoke test:

```bash
python3 --version
python3 -c "import requests, json, math, statistics, pathlib, csv; print('OK')"
```

Report: "HBS-Bank-Screen is ready. Configured for {platform_name}. Python {version}. All dependencies available."

## 4. References

- `SKILL.md` — Skill entry point and full execution flow
- `PLATFORMS.md` — Known platform differences and adaptation notes
- `README.md` — Project overview
- `references/scoring_rules.md` — Scoring methodology and thresholds
