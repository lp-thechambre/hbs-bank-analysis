# HBS-Bank-Depth Setup & Platform Adaptation

When this skill is first installed, ask your AI to perform the following checks and adaptations. No scripts needed — your AI can handle all of this with its built-in tools.

## 1. Environment Check

Have your AI verify:

- **Python 3.9+**: `python3 --version`. If missing, guide the user to install via Homebrew or python.org.
- **PDF extraction**: Check `import pdfplumber` or `import PyPDF2`. If neither is available: `pip install pdfplumber`.
- **requests library**: Check `import requests`. If missing: `pip install requests`.
- **Web search backend**: Check if searXNG is reachable at `http://localhost:8888`. If not, the platform's built-in web_search tool will be used as fallback.
- **Disk space**: At least 2GB free for PDF downloads (annual reports can be 20-40MB each × 6 documents × N banks).

Report any issues to the user with the exact fix command. Continue with whatever is available — the pipeline degrades gracefully.

## 2. Platform Adaptation

Have your AI check and adapt:

- **Frontmatter format**: Does `SKILL.md`'s YAML frontmatter match your platform's expected schema?
  - OpenClaw: `user-invocable` at top level, `metadata` as single-line JSON
  - Claude Code: nested YAML under `metadata.openclaw`
  - Other platforms: adapt as needed. If unsure, ask the user.
- **Tool name mapping**: Platform-specific tool names may differ:
  - `exec` → `Bash` (Claude Code)
  - `sessions_spawn` → `Task`/`Agent` (Claude Code) or may not exist
  - `web_search` / `web_fetch` → platform equivalents
- **Spawn support**: If your platform lacks spawn/parallel subagent support, set `batch_size: 1` in `assets/batch_config.json`. The pipeline will run sequentially but produce the same results.
- **Browser policy**: Ensure headless/API-only mode to avoid visible browser windows.

## 3. Search Engine Configuration (searXNG users)

If using searXNG, have your AI check `settings.yml` (typically `~/.openclaw/searxng-config/settings.yml`):

- **baidu**: MUST be enabled (`disabled: false`) for Chinese financial queries
- **sogou**: MUST be enabled for supplementary Chinese results
- **bing**: `weight: 0.3` (reduced, poor Chinese financial query quality)
- **timeout**: `request_timeout: 10.0` (default 3.0s is too short)

Without these changes, Chinese financial search relevance drops to 0%.

## 4. Verification

Have your AI run a quick smoke test:

1. Pick one bank code (e.g., SH600036)
2. Run `python3 scripts/discover_pdfs.py --codes SH600036 --data-dir data/smoke-test/`
3. Verify `raw_announcements.json` exists with > 0 items
4. Run `python3 scripts/env_scan.py --data-dir data/smoke-test/`
5. Confirm PDF extraction method is available

Report: "HBS-Bank-Depth is ready. Configured for {platform_name}. {N} PDF extraction methods available. Search backend: {provider}."

## 5. References

- `docs/ARCHITECTURE.md` — Full architecture documentation
- `docs/BRD.md` — Business requirements
- `README.md` — Project overview and search engine configuration guide
- `PLATFORMS.md` — Known platform differences and adaptation notes
