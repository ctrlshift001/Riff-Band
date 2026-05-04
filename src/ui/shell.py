"""Interactive shell for the AOrchestra multi-agent system."""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from uuid import uuid4

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from base.engine.logs import logger
from config import AgentConfig
from core.session import ConversationSession
from modes.router import ModeRouter
from project import build_agent_project, build_single_agent_project
from ui.render import MessageRenderer

VALID_MODES = {"single", "multi", "auto"}


class AOrchestraShell:
    """Interactive REPL for the AOrchestra agent runtime."""

    def __init__(self, config_path: str | Path):
        load_dotenv()

        # Silence logger console output — TUI handles its own display
        from base.engine.logs import logger as base_logger
        base_logger.console_output = False

        self._config_path = Path(config_path)
        self._cfg = AgentConfig.load(self._config_path)
        self._cfg.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self._console = Console()
        self._renderer = MessageRenderer(self._console)

        # Session
        self._work_dir = self._cfg.workspace_dir.resolve()
        self._session: Optional[ConversationSession] = None

        # Runtime state (created lazily on first prompt)
        self._main_agent = None
        self._state_restored = False  # True only after explicit /resume
        self._profile_name = self._cfg.profile_name or "generic"
        self._mode = self._cfg.mode or "auto"
        self._env = None

        # Cancellation
        self._cancel_event = asyncio.Event()
        self._task_running = False

        # Setup
        self._work_dir.mkdir(parents=True, exist_ok=True)
        (self._work_dir / "sessions").mkdir(parents=True, exist_ok=True)
        (self._work_dir / "output").mkdir(parents=True, exist_ok=True)

    # ── signal handling ────────────────────────────────────────────

    def _install_signal_handlers(self):
        """Install SIGINT handler for task cancellation.

        First Ctrl+C cancels the running task and returns to the prompt.
        Second Ctrl+C exits the shell.
        """
        loop = asyncio.get_running_loop()

        def _on_sigint():
            if self._task_running:
                self._cancel_event.set()
                self._console.print()
                self._console.print(
                    "[yellow]Cancelling... (Ctrl+C again to exit)[/]"
                )
            else:
                self._console.print()
                self._console.print("[yellow]Exiting...[/]")
                loop.stop()

        try:
            loop.add_signal_handler(signal.SIGINT, _on_sigint)
        except NotImplementedError:
            # Windows fallback: use signal.signal
            signal.signal(signal.SIGINT, lambda sig, frame: _on_sigint())

    def _uninstall_signal_handlers(self):
        """Restore default SIGINT behaviour."""
        loop = asyncio.get_running_loop()
        try:
            loop.remove_signal_handler(signal.SIGINT)
        except NotImplementedError:
            signal.signal(signal.SIGINT, signal.SIG_DFL)

    # ── entry point ───────────────────────────────────────────────

    async def run(self):
        """Start the interactive shell."""
        self._install_signal_handlers()
        self._setup_readline_completion()
        try:
            self._print_banner()
            await self._init_or_resume_session()
            await self._repl()
        finally:
            self._uninstall_signal_handlers()

    # ── session lifecycle ─────────────────────────────────────────

    def _setup_readline_completion(self):
        """Enable Tab completion for slash commands via readline."""
        try:
            import readline
        except ImportError:
            return  # readline not available (common on Windows)

        COMMANDS = [
            "/help", "/mode", "/model", "/setup", "/status", "/session",
            "/sessions", "/resume", "/clear", "/exit", "/quit",
        ]

        def completer(text: str, state: int) -> str | None:
            matches = [c for c in COMMANDS if c.startswith(text)]
            if state < len(matches):
                return matches[state]
            return None

        readline.set_completer(completer)
        readline.parse_and_bind("tab: complete")

    async def _init_or_resume_session(self):
        """Create a new session or resume an existing one."""
        sessions = ConversationSession.list_sessions(self._work_dir)
        if sessions:
            latest = sessions[0]
            self._session = ConversationSession.load(
                latest["session_id"], self._work_dir
            )
            if self._session:
                self._console.print(
                    f"[dim]Resumed session [bold]{self._session.session_id}[/]"
                    f" ({self._session.turn_count} turns)[/]"
                )
                return

        sid = uuid4().hex[:12]
        self._session = ConversationSession.create(
            session_id=sid,
            work_dir=self._work_dir,
            profile_name=self._profile_name,
            mode=self._mode,
        )
        self._session.save()
        self._console.print(f"[dim]New session [bold]{sid}[/][/]")

    # ── REPL ──────────────────────────────────────────────────────

    async def _repl(self):
        """Main read-eval-print loop."""
        while True:
            try:
                user_input = self._read_prompt()
            except (EOFError, KeyboardInterrupt):
                self._console.print()
                break

            stripped = user_input.strip()
            if not stripped:
                continue

            # Slash commands
            if stripped.startswith("/"):
                if self._handle_command(stripped):
                    break
                continue

            # Route mode if auto
            if self._mode == "auto":
                router = ModeRouter()
                norm = router.normalize_requested_mode("auto")
                # We keep auto for the actual routing below

            # Execute the turn
            try:
                await self._execute_turn(stripped)
            except Exception as exc:
                self._console.print(
                    Panel(
                        Text(str(exc), style="red"),
                        title="[bold red]Error[/]",
                        border_style="red",
                    )
                )
                logger.error(f"Turn failed: {exc}")

        # Cleanup
        self._save_state()
        self._console.print("[dim]Goodbye.[/]")

    # ── input ─────────────────────────────────────────────────────

    def _read_prompt(self) -> str:
        """Read a single line from the user."""
        prompt_text = Text.assemble(
            ("\n", ""),
            ("AOrchestra", "bold green"),
            (" [", "dim"),
            (self._mode, "cyan"),
            ("]", "dim"),
            (" [dim]Ctrl+C to cancel[/]", ""),
            (" > ", "dim"),
        )
        self._console.print(prompt_text, end="")

        try:
            line = input()
        except EOFError:
            return ""
        self._console.print()
        return line.strip()

    # ── commands ──────────────────────────────────────────────────

    def _handle_command(self, raw: str) -> bool:
        """Handle a slash command.  Returns True if the shell should exit."""
        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit", "/q"):
            return True

        elif cmd == "/help":
            self._show_help()

        elif cmd == "/mode":
            self._set_mode(arg)

        elif cmd == "/status":
            self._show_status()

        elif cmd == "/clear":
            os.system("cls" if os.name == "nt" else "clear")

        elif cmd == "/session":
            self._show_session_info()

        elif cmd == "/sessions":
            self._list_sessions()

        elif cmd == "/resume":
            self._resume_session(arg)

        elif cmd == "/model":
            self._set_model(arg)

        elif cmd == "/setup":
            self._rerun_onboarding()

        else:
            self._console.print(f"[red]Unknown command: {cmd}[/]")
            self._console.print("[dim]Type /help for available commands.[/]")

        return False

    def _show_help(self):
        table = Table(title="Commands", border_style="dim")
        table.add_column("Command", style="bold cyan")
        table.add_column("Description")
        for cmd, desc in [
            ("/help", "Show this help"),
            ("/mode single|multi|auto", "Switch execution mode"),
            ("/model name", "Switch LLM model for next turn"),
            ("/setup", "Re-run the setup wizard"),
            ("/status", "Show current agent state"),
            ("/session", "Show session info"),
            ("/sessions", "List saved sessions"),
            ("/resume id", "Resume a previous session"),
            ("/clear", "Clear screen"),
            ("/exit, /quit, /q", "Exit the shell"),
        ]:
            table.add_row(cmd, desc)
        self._console.print(table)

    def _set_mode(self, arg: str):
        mode = arg.strip().lower()
        if mode not in VALID_MODES:
            self._console.print(
                f"[red]Invalid mode '{mode}'. Use: single, multi, auto[/]"
            )
            return
        self._mode = mode
        if self._session:
            self._session.mode = mode
            self._session.save()
        # Save state before rebuild so findings/report persist to disk
        self._save_state()
        self._main_agent = None
        self._main_project = None
        self._console.print(
            f"[green]Mode set to [bold]{mode}[/] (next turn)[/]"
        )
        if self._session and self._session.turn_count > 0:
            self._console.print(
                "[dim]Note: agent memory will reset, but findings and report are preserved.[/]"
            )

    def _resume_session(self, arg: str):
        """Switch to a previously saved session."""
        sid = arg.strip()
        if not sid:
            # Show sessions and let user pick
            sessions = ConversationSession.list_sessions(self._work_dir)
            if not sessions:
                self._console.print("[dim]No saved sessions.[/]")
                return
            self._list_sessions()
            self._console.print("[dim]Usage: /resume <session_id>[/]")
            return

        # Partial match
        sessions = ConversationSession.list_sessions(self._work_dir)
        matched = [s for s in sessions if s["session_id"].startswith(sid)]
        if not matched:
            self._console.print(f"[red]Session not found: {sid}[/]")
            return
        if len(matched) > 1:
            self._console.print(
                f"[yellow]Multiple matches for '{sid}'. Be more specific:[/]"
            )
            for s in matched:
                self._console.print(f"  [dim]{s['session_id']}[/]")
            return

        target_id = matched[0]["session_id"]

        # Save current session before switching
        self._save_state()

        # Load target session
        new_session = ConversationSession.load(target_id, self._work_dir)
        if new_session is None:
            self._console.print(f"[red]Failed to load session: {target_id}[/]")
            return

        self._session = new_session
        self._mode = new_session.mode
        self._profile_name = new_session.profile_name
        self._state_restored = True

        # Discard current project so next turn rebuilds
        self._main_agent = None
        self._main_project = None

        # Try to restore agent state from session
        # (state will be loaded on next _build_first_project if _main_agent is still None)
        self._console.print(
            f"[green]Resumed session [bold]{target_id}[/]"
            f" ({self._session.turn_count} turns)[/]"
        )

    def _set_model(self, arg: str):
        """Switch the LLM model for subsequent turns."""
        model = arg.strip()
        if not model:
            self._console.print(f"[dim]Current model: {self._cfg.main_model}[/]")
            self._console.print(
                f"[dim]Available in config: {', '.join(self._cfg.sub_models)}[/]"
            )
            return

        self._cfg.main_model = model

        # Ensure model is also in sub_models
        if model not in self._cfg.sub_models:
            self._cfg.sub_models.insert(0, model)

        # Force rebuild on next turn
        self._main_agent = None
        self._main_project = None

        self._console.print(f"[green]Model set to [bold]{model}[/] (next turn)[/]")

    def _rerun_onboarding(self):
        """Re-run the setup wizard to update config and .env."""
        from ui.onboarding import run_onboarding

        env_path = Path(".env")
        ok = run_onboarding(self._config_path, env_path)
        if ok:
            # Reload config
            self._cfg = AgentConfig.load(self._config_path)
            self._profile_name = self._cfg.profile_name or "generic"
            self._mode = self._cfg.mode or "auto"
            self._work_dir = self._cfg.workspace_dir.resolve()
            self._work_dir.mkdir(parents=True, exist_ok=True)
            (self._work_dir / "sessions").mkdir(parents=True, exist_ok=True)
            (self._work_dir / "output").mkdir(parents=True, exist_ok=True)
            self._main_agent = None
            self._main_project = None

    def _show_status(self):
        if self._main_agent is None:
            self._console.print("[dim]No active agent. Send a task to start.[/]")
            return

        table = Table(title="Agent Status", border_style="dim")
        table.add_column("Field", style="bold")
        table.add_column("Value")
        table.add_row("Instruction", (self._main_agent.instruction or "")[:100])
        table.add_row("Mode", self._mode)
        table.add_row("Profile", self._profile_name)

        if hasattr(self._main_agent, "attempt"):
            table.add_row("Attempt", str(self._main_agent.attempt))
        if hasattr(self._main_agent, "task_entries"):
            table.add_row("Task entries", str(len(self._main_agent.task_entries)))
        if hasattr(self._main_agent, "_current_phase"):
            table.add_row("Phase", self._main_agent._current_phase())
        if hasattr(self._main_agent, "task_plan_executor"):
            plan = self._main_agent.task_plan_executor.snapshot()
            for task in plan.get("tasks", [])[:10]:
                icon = {
                    "queued": "○",
                    "running": "◎",
                    "succeeded": "[green]✓[/]",
                    "failed": "[red]✗[/]",
                    "cancelled": "[dim]✗[/]",
                }.get(task.get("state", ""), "?")
                table.add_row(
                    f"  {icon} {task['task_id']}",
                    f"{task['state']} | {task.get('model', '')}",
                )
        self._console.print(table)

    def _show_session_info(self):
        if not self._session:
            self._console.print("[dim]No active session.[/]")
            return
        table = Table(title="Session", border_style="dim")
        table.add_column("Field", style="bold")
        table.add_column("Value")
        table.add_row("ID", self._session.session_id)
        table.add_row("Created", self._session.created_at)
        table.add_row("Turns", str(self._session.turn_count))
        table.add_row("Mode", self._session.mode)
        table.add_row("Profile", self._session.profile_name)
        table.add_row("Instruction", (self._session.instruction or "")[:100])
        self._console.print(table)

    def _list_sessions(self):
        sessions = ConversationSession.list_sessions(self._work_dir)
        if not sessions:
            self._console.print("[dim]No saved sessions.[/]")
            return
        table = Table(title="Saved Sessions", border_style="dim")
        table.add_column("ID", style="bold cyan")
        table.add_column("Turns")
        table.add_column("Updated")
        table.add_column("Instruction")
        for s in sessions[:20]:
            table.add_row(
                s["session_id"][:12],
                str(s["turn_count"]),
                s.get("updated_at", "")[:16] or s.get("created_at", "")[:16],
                (s.get("instruction", "") or "")[:60],
            )
        self._console.print(table)

    # ── execution ─────────────────────────────────────────────────

    async def _execute_turn(self, user_input: str):
        """Run one conversation turn."""
        # Build or reuse project
        if self._main_agent is None:
            await self._build_first_project(user_input)
        else:
            self._prepare_next_turn(user_input)

        # Reset cancellation state for this turn
        self._cancel_event.clear()
        self._task_running = True

        try:
            # Stream and render
            self._console.print(
                Rule(style="dim", characters="─")
            )

            async for msg in self._main_project.stream(
                cancel_event=self._cancel_event
            ):
                renderable = self._renderer.render(msg)
                if renderable is not None:
                    self._console.print(renderable)

            self._console.print()

            # Track turn
            if self._main_project._run_result:
                final = self._main_project._run_result.get("final_result")
                if final and final.get("quality_gate_passed"):
                    self._console.print(
                        Panel(
                            Text(
                                final.get("executive_summary", "Task completed.")[:500],
                            ),
                            title="[bold green]✓ Done[/]",
                            border_style="green",
                        )
                    )

            self._session.turn_count += 1
            self._session.instruction = user_input
            self._save_state()

        finally:
            self._task_running = False

    async def _build_first_project(self, user_input: str):
        """Create the agent project on the first turn."""
        self._console.print(f"[dim]Routing mode: {self._mode}...[/]")

        output_dir = self._work_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        if self._mode == "auto":
            router = ModeRouter.from_model_name(self._cfg.main_model)
            decision = await router.decide(user_input)
            selected_mode = decision.mode
            self._console.print(
                f"[dim]  → {selected_mode} ({decision.source}: {decision.reason})[/]"
            )
        else:
            selected_mode = self._mode

        if selected_mode == "single":
            self._main_project = build_single_agent_project(
                main_model=self._cfg.main_model,
                sub_models=self._cfg.sub_models,
                brief_text=user_input,
                sources_dir=self._cfg.sources_dir,
                output_dir=output_dir,
                max_subagent_steps=self._cfg.max_subagent_steps,
                subagent_process_timeout_seconds=self._cfg.subagent_process_timeout_seconds,
                profile_name=self._profile_name,
            )
            self._main_agent = self._main_project.sub_agent
        else:
            self._main_project = build_agent_project(
                main_model=self._cfg.main_model,
                sub_models=self._cfg.sub_models,
                brief_text=user_input,
                sources_dir=self._cfg.sources_dir,
                output_dir=output_dir,
                max_attempts=self._cfg.max_attempts,
                max_subagent_steps=self._cfg.max_subagent_steps,
                subagent_process_timeout_seconds=self._cfg.subagent_process_timeout_seconds,
                profile_name=self._profile_name,
            )
            self._main_agent = self._main_project.main_agent

        # Only restore state when explicitly resumed via /resume
        if self._state_restored and self._session and self._session.agent_state_file.exists():
            if self._main_agent is not None and hasattr(self._main_agent, "load_state"):
                self._session.load_agent_state(self._main_agent)
                self._console.print(
                    "[dim]Restored agent state from session.[/]"
                )
                self._state_restored = False

        self._console.print(f"[dim]Profile: {self._profile_name}[/]")

    def _prepare_next_turn(self, user_input: str):
        """Prepare the agent for a subsequent conversation turn."""
        self._main_agent.instruction = user_input
        if hasattr(self._main_agent, "soft_reset"):
            self._main_agent.soft_reset(user_input)
        self._main_project._run_result = None

    def _save_state(self):
        """Persist session and agent state to disk."""
        if self._session and self._main_agent is not None:
            if hasattr(self._main_agent, "meta"):
                self._session.meta = dict(self._main_agent.meta)
            self._session.save()
            if hasattr(self._main_agent, "dump_state"):
                self._session.save_agent_state(self._main_agent)

    # ── banner ────────────────────────────────────────────────────

    def _print_banner(self):
        self._console.print(
            Panel(
                Text.assemble(
                    ("AOrchestra  ", "bold green"),
                    ("Multi-Agent Shell\n", "bold"),
                    ("Type a task to start, or ", "dim"),
                    ("/help", "bold cyan"),
                    (" for commands.", "dim"),
                ),
                border_style="green",
            )
        )


# ── entry point ───────────────────────────────────────────────────


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="AOrchestra interactive shell")
    parser.add_argument("--config", default="aorchestra.yaml", help="Path to config YAML")
    args = parser.parse_args()

    config_path = Path(args.config)

    # First run? Show onboarding
    if not config_path.exists():
        from ui.onboarding import run_onboarding

        env_path = Path(".env")
        ok = run_onboarding(config_path, env_path)
        if not ok:
            return 1

    shell = AOrchestraShell(config_path)
    await shell.run()


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
