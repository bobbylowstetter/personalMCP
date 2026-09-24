# personal-mcp

Personal project scaffold that gives Claude Code (and Cloud Routines) access to personal
data sources through community MCP servers, with Notion (via Composio) as the place
reports get written:

| Server | Package | Access | Used for |
| --- | --- | --- | --- |
| `ynab` | [`@maro-org/ynab-mcp`](https://www.npmjs.com/package/@maro-org/ynab-mcp) | read/write | Daily transaction categorization |
| `loseit` | [`cabird/loseit-mcp`](https://github.com/cabird/loseit-mcp) (pinned to v0.6.0) | read-only | Weekly average weight / pattern report |

No custom server code lives here — this repo is just the project-scoped MCP config
(`.mcp.json`), Claude Code settings, and setup notes.

## Setup

### 1. Credentials

`.mcp.json` (committed, safe) references `${YNAB_API_TOKEN}`, `${LOSEIT_EMAIL}`, and
`${LOSEIT_PASSWORD}` — Claude Code expands these from the environment at connect time.
It does **not** auto-load a `.env` file, so pick one:

- Copy `.env.example` to `.env`, fill it in, then before running Claude Code:
  ```bash
  set -a && source .env && set +a
  ```
- Or export them in your shell profile (`~/.zshrc`).
- For Cloud Routines / Claude Code on the web: add them as environment secrets on the
  environment the routine runs in.

`.env` is gitignored — only `.env.example` is tracked.

### 2. Verify the MCP servers connect

```bash
claude mcp list
```

You should see `ynab` and `loseit` connected. Notion is reached through Composio, which
uses its own OAuth connection.

## YNAB

### Why a PAT, not OAuth

Composio's shared YNAB OAuth app is capped at 25 authorized users and is often already
maxed out. For a single-user pipeline, a YNAB Personal Access Token sidesteps OAuth.

Generate one at YNAB → Account Settings → Developer Settings → New Token, and set it as
`YNAB_API_TOKEN`.

### Write access

`.mcp.json` sets `YNAB_READ_ONLY=false` so the routine can categorize transactions.
Writes are logged with undo entries (`list_undo_history` / `undo_operations`). Set it to
`"true"` to go back to read-only.

## Lose It!

Lose It! has no official API. `loseit-mcp` signs in with your account email/password and
calls the private web-app endpoint (GWT-RPC), so expect it to break occasionally when
Lose It! ships a new web build (the server reports what changed; see its README for
`LOSEIT_STRONG_NAME` / `LOSEIT_POLICY_HASH` overrides).

- **Pinned by commit.** `.mcp.json` runs it with `uvx` from a fixed commit (tag v0.6.0).
  This code receives your Lose It! password — skim the diff before bumping the pin.
- **Read-only by policy.** `.claude/settings.json` allows `get_weight_history`,
  `get_diary`, `search_food`, `describe_food`, `whoami`, `server_status`, and denies
  `log_food`, `log_custom_food`, `log_weight`, `delete_entry`.
- **Network.** In Claude Code on the web, the environment's network policy must allow
  `api.loseit.com` and `www.loseit.com`, plus `github.com` / `pypi.org` for `uvx` to
  install the server.
- The session token is cached at `~/.config/loseit-mcp/session.json` and refreshes itself.

## Cloud Routines

Routines are project-scoped, so a Routine pointed at this repo picks up both MCP servers.
`permissions.defaultMode: dontAsk` plus the `PreToolUse` hook in `.claude/settings.json`
pre-approve the allowed tools so unattended runs don't stall on prompts.

The routine instructions live in Notion (Personal AI hub):

- **YNAB Instructions** → daily categorization, report on *YNAB Transaction Log*.
- **Lose It Instructions** → weekly average weight + patterns, report on *Weight Log*.

Example weekly prompt:

> Follow the "Lose It Instructions" page in Notion: pull my Lose It! weigh-ins and
> diary with the loseit MCP server (read-only) and refresh the Weight Log page.

## Security note

Never commit a literal token or password into `.mcp.json` or anywhere else in this repo —
always go through `${VAR}` expansion and keep the real values in your environment, the
gitignored `.env`, or environment secrets.
