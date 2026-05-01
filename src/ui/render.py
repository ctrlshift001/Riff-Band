"""Rich-based terminal renderer for AOrchestra ShellMessages."""

from __future__ import annotations

from typing import Dict, List, Optional

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.rule import Rule
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from core.message import (
    ContentPart,
    ErrorMessage,
    OrchestratorDecision,
    OrchestratorThinking,
    PhaseTransition,
    SubAgentCreated,
    SubAgentResult,
    SubAgentStart,
    SubAgentStepEnd,
    TaskCancelled,
    TaskComplete,
    WorkerCompleted,
    WorkerSpawned,
    WorkerWaitEnd,
    WorkerWaitStart,
)

# Mapping status → icon
_STATUS_ICONS: Dict[str, str] = {
    "done": "[bold green]✓[/]",
    "partial": "[bold yellow]~[/]",
    "blocked": "[bold red]✗[/]",
    "timeout": "[bold red]⏱[/]",
    "failed": "[bold red]✗[/]",
    "running": "[bold cyan]◎[/]",
    "succeeded": "[bold green]✓[/]",
}


class MessageRenderer:
    """Render ShellMessage objects to Rich renderables."""

    def __init__(self, console: Console):
        self._console = console
        self._worker_labels: Dict[str, str] = {}  # session_id → label

    # ── helpers ───────────────────────────────────────────────────

    def _icon_for(self, status: str) -> str:
        return _STATUS_ICONS.get(status, "[dim]?[/]")

    def _label_for(self, session_id: str) -> str:
        return self._worker_labels.get(session_id, session_id[:8])

    # ── per-message renderers ─────────────────────────────────────

    def render(self, msg) -> Optional[RenderableType]:
        """Dispatch to the correct render method."""
        method = getattr(self, f"_render_{type(msg).__name__}", None)
        if method is not None:
            return method(msg)
        return None

    def _render_OrchestratorThinking(self, msg: OrchestratorThinking) -> RenderableType:
        return Spinner(
            "dots",
            text=(
                f"[dim]  [{msg.attempt}/{msg.max_attempts}][/] "
                f"[bold]MainAgent[/] thinking..."
            ),
        )

    def _render_OrchestratorDecision(self, msg: OrchestratorDecision) -> RenderableType:
        action = msg.action or "unknown"
        reasoning = msg.reasoning or ""
        lines: List[RenderableType] = [
            Text.assemble(
                ("  ", "dim"),
                (f"[{msg.attempt}]" if hasattr(msg, "attempt") else "", "dim"),
                (" → ", "bold cyan"),
                (action, "bold white"),
            )
        ]
        if reasoning:
            lines.append(Text(reasoning[:200], style="dim italic"))
        return Group(*lines)

    def _render_PhaseTransition(self, msg: PhaseTransition) -> RenderableType:
        return Rule(
            f"[bold]Phase: {msg.from_phase} → {msg.to_phase}[/]",
            style="yellow",
            align="left",
        )

    def _render_WorkerSpawned(self, msg: WorkerSpawned) -> RenderableType:
        if msg.session_id and msg.label:
            self._worker_labels[msg.session_id] = msg.label
        short_task = (msg.task_instruction or "")[:60]
        return Text.assemble(
            ("  [>] ", "bold cyan"),
            (f"{msg.label}", "bold"),
            (f"\n      {short_task}" if short_task else "", "dim"),
        )

    def _render_WorkerCompleted(self, msg: WorkerCompleted) -> RenderableType:
        icon = self._icon_for(msg.status)
        label = self._label_for(msg.session_id)
        parts = [f"  {icon} {label} | status={msg.status}"]
        if msg.steps_taken:
            parts.append(f"steps={msg.steps_taken}")
        if msg.cost:
            parts.append(f"cost=${msg.cost:.4f}")
        text = Text(" ".join(parts))
        if msg.issues:
            for issue in msg.issues[:3]:
                text.append(f"\n      [dim]! {issue}[/]")
        return text

    def _render_WorkerWaitStart(self, msg: WorkerWaitStart) -> RenderableType:
        n = len(msg.session_ids) or "all"
        return Text(f"  [wait] Waiting for {n} workers ({msg.timeout_seconds}s)...", style="dim")

    def _render_WorkerWaitEnd(self, msg: WorkerWaitEnd) -> RenderableType:
        return Text(
            f"  [wait] collected={msg.completed} still_running={msg.still_running}",
            style="dim",
        )

    def _render_SubAgentCreated(self, msg: SubAgentCreated) -> RenderableType:
        """Show agent assembly with four-tuple info."""
        lines: List[RenderableType] = [
            Text.assemble(
                ("  [+] ", "bold green"),
                (f"Agent {msg.agent_id or 'sub'} assembled", "bold"),
            ),
            Text.assemble(
                ("      Task:  ", "dim"),
                (msg.task_label or msg.task_instruction[:40], ""),
            ),
            Text.assemble(
                ("      Model: ", "dim"),
                (msg.model or "default", ""),
            ),
        ]
        if msg.tools:
            lines.append(
                Text.assemble(
                    ("      Tools: ", "dim"),
                    (", ".join(msg.tools[:6]), ""),
                )
            )
        return Group(*lines)

    def _render_ContentPart(self, msg: ContentPart) -> RenderableType:
        """Streaming text — suppress in TUI to avoid raw JSON noise."""
        return None  # Only show structured messages, not raw LLM tokens

    def _render_SubAgentStart(self, msg: SubAgentStart) -> RenderableType:
        return Text.assemble(
            ("  [sub] ", "cyan"),
            (f"{msg.label} ", "bold"),
            (f"({msg.model})", "dim"),
        )

    def _render_SubAgentStepEnd(self, msg: SubAgentStepEnd) -> RenderableType:
        if not msg.done:
            return None
        label = getattr(msg, "agent_label", "") or ""
        return Text(
            f"  [sub] {label} step {msg.current_step}/{msg.max_steps} → {msg.action_taken} (done)",
            style="dim",
        )

    def _render_SubAgentResult(self, msg: SubAgentResult) -> RenderableType:
        icon = self._icon_for(msg.finish_status)
        parts = [
            f"  {icon} sub done: {msg.label} | status={msg.finish_status}",
            f"steps={msg.steps_taken}",
            f"cost=${msg.cost:.4f}",
        ]
        text = Text(" ".join(parts))
        if msg.finish_message:
            text.append(f"\n      {msg.finish_message[:200]}", style="dim")
        return text

    def _render_TaskComplete(self, msg: TaskComplete) -> RenderableType:
        icon = "[bold green]✓[/]" if msg.success else "[bold red]✗[/]"
        table = Table.grid(padding=(0, 2))
        table.add_column(style="dim")
        table.add_column()
        table.add_row("Status", f"{icon} {'PASSED' if msg.quality_gate_passed else 'FAILED'}")
        table.add_row("Attempts", str(msg.attempts))
        table.add_row("Total cost", f"${msg.total_cost:.4f}")
        if msg.summary:
            table.add_row("Summary", msg.summary[:200])
        return Panel(
            table,
            title="[bold]Task Complete[/]",
            border_style="green" if msg.success else "red",
        )

    def _render_TaskCancelled(self, msg: TaskCancelled) -> RenderableType:
        return Panel(
            Text(msg.message, style="yellow"),
            title="[bold yellow]Cancelled[/]",
            border_style="yellow",
        )

    def _render_ErrorMessage(self, msg: ErrorMessage) -> RenderableType:
        return Panel(
            Text(f"{msg.error_type}: {msg.message}", style="red"),
            border_style="red",
            title="[bold red]Error[/]",
        )


# ── lightweight renderer (no dependency on rich Console) ──────────

class SimpleRenderer:
    """Text-only renderer that prints directly to stdout (no Rich)."""

    def render(self, msg) -> None:
        method = getattr(self, f"_render_{type(msg).__name__}", None)
        if method is not None:
            method(msg)

    def _render_OrchestratorThinking(self, msg):
        print(f"  [think] MainAgent deciding (attempt {msg.attempt}/{msg.max_attempts})...")

    def _render_OrchestratorDecision(self, msg):
        action = getattr(msg, "action", "") or ""
        reasoning = getattr(msg, "reasoning", "") or ""
        print(f"  [decide] → {action}")
        if reasoning:
            print(f"           {reasoning[:120]}")

    def _render_PhaseTransition(self, msg):
        print(f"  [phase] {msg.from_phase} → {msg.to_phase}")

    def _render_WorkerSpawned(self, msg):
        print(f"  [>] {msg.label} | {msg.model} | {msg.session_id}")

    def _render_WorkerCompleted(self, msg):
        icon = "✓" if msg.status == "done" else "✗"
        print(f"  [{icon}] {msg.label} | status={msg.status} steps={msg.steps_taken} cost=${msg.cost:.4f}")

    def _render_WorkerWaitStart(self, msg):
        print(f"  [wait] waiting for {len(msg.session_ids) or 'all'} workers ({msg.timeout_seconds}s)...")

    def _render_WorkerWaitEnd(self, msg):
        print(f"  [wait] collected={msg.completed} still_running={msg.still_running}")

    def _render_SubAgentCreated(self, msg):
        tools = ", ".join(msg.tools[:4]) if msg.tools else "all"
        task = msg.task_label or msg.task_instruction[:30]
        print(f"  [+] Agent {msg.agent_id or 'sub'} | {task} | {msg.model} | {tools}")

    def _render_ContentPart(self, msg):
        pass  # suppress raw LLM tokens in TUI

    def _render_SubAgentStart(self, msg):
        print(f"  [sub] start: {msg.label} ({msg.model})")

    def _render_SubAgentStepEnd(self, msg):
        if msg.done:
            label = getattr(msg, "agent_label", "") or ""
            print(f"  [sub] {label} step {msg.current_step}/{msg.max_steps} → {msg.action_taken} (done)")

    def _render_SubAgentResult(self, msg):
        icon = "✓" if msg.finish_status == "done" else "✗"
        print(f"  [{icon}] sub done: {msg.label} | status={msg.finish_status} steps={msg.steps_taken} cost=${msg.cost:.4f}")

    def _render_TaskComplete(self, msg):
        icon = "✓" if msg.success else "✗"
        print(f"\n  [{icon}] Task complete | quality_gate_passed={msg.quality_gate_passed} | attempts={msg.attempts} | cost=${msg.total_cost:.4f}")

    def _render_TaskCancelled(self, msg):
        print(f"\n  [!] Cancelled — {msg.message}")

    def _render_ErrorMessage(self, msg):
        print(f"  [!] error: {msg.error_type} — {msg.message}")
