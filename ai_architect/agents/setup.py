"""AGENT-SETUP: connect ArchAI to Claude Code and Codex.

Prints the exact commands by default. Writes nothing unless asked:
  --install-skill  copies the ArchAI skill into the agents' skill folders
  --register       runs `claude mcp add` / `codex mcp add` for you
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

SKILL_DIR = Path(__file__).resolve().parent / "skills" / "archai"

# Where each agent looks for skills (both follow the open agent-skills standard).
SKILL_HOMES = {
    "claude": {"user": Path.home() / ".claude" / "skills", "project": Path(".claude") / "skills"},
    "codex": {"user": Path.home() / ".agents" / "skills", "project": Path(".agents") / "skills"},
}


def server_command() -> List[str]:
    """The launcher if it is on PATH, otherwise this interpreter running the module."""
    launcher = shutil.which("ai-architect-mcp")
    return [launcher] if launcher else [sys.executable, "-m", "ai_architect.agents.mcp_server"]


def _auth_env() -> Dict[str, str]:
    if os.environ.get("ARCHAI_LICENSE"):
        return {"ARCHAI_LICENSE": os.environ["ARCHAI_LICENSE"]}
    if os.environ.get("ARCHAI_DEV_MODE"):
        return {"ARCHAI_DEV_MODE": "1"}
    return {}


def _quote(parts: List[str]) -> str:
    return " ".join(f'"{p}"' if (" " in p or "\\" in p) else p for p in parts) if os.name == "nt" else shlex.join(parts)


def registration_commands(env_display: Dict[str, str]) -> Dict[str, List[str]]:
    cmd = server_command()
    claude = ["claude", "mcp", "add", "archai", "--scope", "user"]
    codex = ["codex", "mcp", "add", "archai"]
    for k, v in env_display.items():
        claude += ["-e", f"{k}={v}"]
        codex += ["--env", f"{k}={v}"]
    return {"claude": claude + ["--"] + cmd, "codex": codex + ["--"] + cmd}


def codex_toml(env: Dict[str, str]) -> str:
    """config.toml snippet. JSON strings are valid TOML basic strings, so Windows paths escape correctly."""
    cmd = server_command()
    env_items = ", ".join(f"{k} = {json.dumps(v)}" for k, v in env.items())
    return (f"[mcp_servers.archai]\ncommand = {json.dumps(cmd[0])}\nargs = {json.dumps(cmd[1:])}\n"
            f"env = {{ {env_items} }}\n")


def install_skill(agents: List[str], scope: str, project: Path, force: bool) -> List[str]:
    """Copies SKILL.md and reference.md. Refuses to overwrite a changed copy unless force."""
    written = []
    for agent in agents:
        home = SKILL_HOMES[agent][scope]
        dest = (home if scope == "user" else project / home) / "archai"
        for src in sorted(SKILL_DIR.glob("*.md")):
            target = dest / src.name
            if target.exists() and target.read_bytes() != src.read_bytes() and not force:
                raise FileExistsError(f"{target} exists and differs from ArchAI's skill; use --force to replace it.")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
            written.append(str(target))
    return written


def agent_setup(args: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="AGENT-SETUP", add_help=False)
    parser.add_argument("--agent", choices=["claude", "codex", "both"], default="both")
    parser.add_argument("--install-skill", action="store_true")
    parser.add_argument("--scope", choices=["user", "project"], default="user",
                        help="skill location: your home folder (all projects) or --project")
    parser.add_argument("--project", default=".", help="project folder for --scope project")
    parser.add_argument("--register", action="store_true", help="run claude/codex mcp add")
    parser.add_argument("--force", action="store_true")
    try:
        opts = parser.parse_args(args)
    except SystemExit:
        print("Usage: AGENT-SETUP [--agent claude|codex|both] [--install-skill [--scope user|project] "
              "[--project DIR] [--force]] [--register]")
        return 2
    agents = ["claude", "codex"] if opts.agent == "both" else [opts.agent]

    auth = _auth_env()
    shown = {k: ("YOUR_TOKEN" if k == "ARCHAI_LICENSE" else v) for k, v in auth.items()} or {"ARCHAI_LICENSE": "YOUR_TOKEN"}
    cmds = registration_commands(shown)
    print("ArchAI MCP server command:\n  " + _quote(server_command()) + "\n")
    for agent in agents:
        print(f"Register with {'Claude Code' if agent == 'claude' else 'Codex'}:\n  {_quote(cmds[agent])}\n")
    if "codex" in agents:
        print("Or add to ~/.codex/config.toml:\n" + "\n".join("  " + l for l in codex_toml(shown).splitlines()) + "\n")

    if opts.install_skill:
        try:
            written = install_skill(agents, opts.scope, Path(opts.project), opts.force)
        except FileExistsError as e:
            print(f"AGENT-SETUP: {e}")
            return 2
        print("Installed the ArchAI skill:\n" + "\n".join(f"  {w}" for w in written) + "\n")
    else:
        homes = ", ".join(str(SKILL_HOMES[a][opts.scope] / "archai") for a in agents)
        print(f"Skill: run AGENT-SETUP --install-skill to copy it to {homes}\n")

    if opts.register:
        if not auth:
            print("AGENT-SETUP: set ARCHAI_LICENSE (or ARCHAI_DEV_MODE=1 for local development) before --register.")
            return 2
        real = registration_commands(auth)
        status = 0
        for agent in agents:
            exe = shutil.which(agent)
            if not exe:
                print(f"AGENT-SETUP: '{agent}' is not on PATH; register manually with the command above.")
                status = 2
                continue
            result = subprocess.run([exe] + real[agent][1:], capture_output=True, text=True)
            ok = result.returncode == 0
            print(f"{'Registered' if ok else 'Could not register'} with {agent}."
                  + ("" if ok else f" {result.stderr.strip() or result.stdout.strip()}"))
            status = status or (0 if ok else 2)
        return status
    return 0
