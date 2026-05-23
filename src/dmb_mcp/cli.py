"""CLI for dmb-mcp-server."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dmb_mcp.context import AppContext
from dmb_mcp.settings import package_root


def cmd_auth(args: argparse.Namespace) -> int:
    app = AppContext.create()
    try:
        if args.cookie:
            app.session.save_cookie(args.cookie)
            print(f"Saved cookie to {app.settings.session_path}")
            return 0
        status = app.session.auth_status()
        print(json.dumps(status, indent=2))
        return 0 if status.get("valid") else 1
    finally:
        app.close()


def cmd_scrape(args: argparse.Namespace) -> int:
    app = AppContext.create()
    try:
        result = app.scraper.run(args.entry_team_id, mode=args.mode, verbose=True)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    finally:
        app.close()


def cmd_init_team(args: argparse.Namespace) -> int:
    team_dir = Path(args.team_dir)
    team_dir.mkdir(parents=True, exist_ok=True)
    cursor_dir = team_dir / ".cursor"
    rules_dir = cursor_dir / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    pkg = package_root()
    mcp_json = {
        "mcpServers": {
            "dmb": {
                "command": sys.executable,
                "args": ["-m", "dmb_mcp.server"],
                "env": {
                    "PYTHONPATH": str(pkg / "src"),
                    "DMB_DB_PATH": str(Path(args.diamondmind_root) / "data" / "is_scout.db"),
                    "DMB_SESSION_PATH": str(Path(args.diamondmind_root) / ".is_session"),
                    "DMB_CONFIG_PATH": str(pkg / "config" / "leagues.json"),
                    "DMB_ENTRY_TEAM_ID": args.entry_team_id,
                },
            }
        }
    }
    (cursor_dir / "mcp.json").write_text(json.dumps(mcp_json, indent=2) + "\n")

    rule = f"""---
description: Team context for {args.name}
alwaysApply: true
---

# {args.name}

- Entry team ID: `{args.entry_team_id}`
- MCP server scoped via `DMB_ENTRY_TEAM_ID`
- Use `standings://mine`, `roster://mine`, and `scrape(mode=\"refresh\")` for this team/league.
"""
    (rules_dir / "team-context.mdc").write_text(rule)
    readme = team_dir / "README.md"
    if not readme.exists():
        readme.write_text(f"# {args.name}\n\nTeam workspace for Diamond Mind Baseball MCP tools.\n")
    print(f"Initialized team workspace at {team_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dmb-mcp")
    sub = p.add_subparsers(dest="command", required=True)

    auth = sub.add_parser("auth", help="Set or check session cookie")
    auth.add_argument("--cookie", help="Session cookie value or header")
    auth.set_defaults(func=cmd_auth)

    scrape = sub.add_parser("scrape", help="Scrape one league")
    scrape.add_argument("--entry-team-id", required=True)
    scrape.add_argument(
        "--mode",
        choices=["full", "refresh", "tracker"],
        default="refresh",
    )
    scrape.set_defaults(func=cmd_scrape)

    init_team = sub.add_parser("init-team", help="Scaffold a team workspace")
    init_team.add_argument("name")
    init_team.add_argument("--entry-team-id", required=True)
    init_team.add_argument("--team-dir", required=True)
    init_team.add_argument(
        "--diamondmind-root",
        default=".",
        help="Root folder for DB/session paths (default: current directory)",
    )
    init_team.set_defaults(func=cmd_init_team)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    code = args.func(args)
    sys.exit(code)


if __name__ == "__main__":
    main()
