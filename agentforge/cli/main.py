"""AgentForge CLI — review code from the terminal with rich output."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from agentforge.models.database import init_db, list_reviews
from agentforge.models.schemas import ReviewRequest
from agentforge.rag.indexer import index_directory
from agentforge.rag.retriever import get_collection_stats
from agentforge.services.review_service import execute_review, get_review_response, submit_review

app = typer.Typer(
    name="agentforge",
    help="🔥 AgentForge — Multi-Agent Code Review Platform",
    add_completion=False,
)
console = Console()

# Severity colors
SEVERITY_COLORS = {
    "critical": "bold red",
    "warning": "yellow",
    "info": "cyan",
}

SEVERITY_EMOJI = {
    "critical": "🔴",
    "warning": "🟡",
    "info": "🔵",
}


def _score_color(score: int) -> str:
    """Pick a color based on the quality score."""
    if score >= 90:
        return "bold green"
    elif score >= 70:
        return "green"
    elif score >= 50:
        return "yellow"
    else:
        return "bold red"


@app.command()
def review(
    path: str = typer.Argument(..., help="Path to file or directory to review"),
    context: str = typer.Option("", "--context", "-c", help="Additional context for the review"),
):
    """Review code file(s) with the multi-agent pipeline."""
    init_db()
    target = Path(path).resolve()

    if not target.exists():
        console.print(f"[red]Error:[/red] Path not found: {target}")
        raise typer.Exit(1)

    # Collect files
    if target.is_file():
        files = [target]
    else:
        files = sorted(
            f
            for f in target.rglob("*")
            if f.is_file() and f.suffix in {".py", ".js", ".ts", ".java", ".go", ".rs", ".cpp", ".c"}
        )

    if not files:
        console.print("[yellow]No supported code files found.[/yellow]")
        raise typer.Exit(0)

    for filepath in files:
        code = filepath.read_text(encoding="utf-8", errors="ignore")
        request = ReviewRequest(
            code=code,
            filename=filepath.name,
            context=context or None,
        )
        submission = submit_review(request)

        console.print()
        console.rule(f"[bold blue]Reviewing: {filepath.name}[/bold blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold green]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running multi-agent review...", total=None)
            asyncio.run(execute_review(submission.review_id, request))
            progress.update(task, completed=True, description="Review complete!")

        # Display results
        review_record = get_review_response(submission.review_id)
        if not review_record or review_record.get("status") != "completed":
            console.print(f"[red]Review failed for {filepath.name}[/red]")
            continue

        _render_review(ReviewResultProxy(review_record["result"]), filepath.name)


def _render_review(result, filename: str):
    """Render a synthesized review as beautiful terminal output."""
    # Score panel
    score = result.overall_score
    score_text = Text(f"  {score}/100  ", style=_score_color(score))
    console.print(
        Panel(
            score_text,
            title="[bold]Code Quality Score[/bold]",
            border_style=_score_color(score),
            expand=False,
        )
    )

    # Summary
    console.print(Panel(Markdown(result.summary), title="[bold]Summary[/bold]", border_style="blue"))

    # Findings table
    if result.findings:
        table = Table(title="Findings", show_lines=True, expand=True)
        table.add_column("", width=3, justify="center")
        table.add_column("Severity", width=10)
        table.add_column("Category", width=18)
        table.add_column("Description", ratio=2)
        table.add_column("Lines", width=10)
        table.add_column("Fix", ratio=2)

        for f in result.findings:
            severity = _field(f, "severity", "info")
            emoji = SEVERITY_EMOJI.get(severity, "⚪")
            sev_style = SEVERITY_COLORS.get(severity, "white")
            line_start = _field(f, "line_start", 0)
            line_end = _field(f, "line_end", 0)
            lines = f"{line_start}-{line_end}" if line_start else "—"

            table.add_row(
                emoji,
                Text(str(severity), style=sev_style),
                _field(f, "category", ""),
                _field(f, "description", ""),
                lines,
                _field(f, "suggested_fix", "") or "—",
            )

        console.print(table)
    else:
        console.print("[green]✅ No issues found! Code looks great.[/green]")

    # Conflicts
    if result.conflicts:
        console.print()
        console.print("[bold]⚔️ Resolved Conflicts:[/bold]")
        for c in result.conflicts:
            console.print(
                f"  • {', '.join(_field(c, 'agents_involved', []))}: {_field(c, 'description', '')}\n"
                f"    → Resolution: {_field(c, 'resolution', '')}"
            )

    # Agent reports summary
    console.print()
    agent_table = Table(title="Agent Reports", expand=False)
    agent_table.add_column("Agent", style="bold")
    agent_table.add_column("Findings")
    agent_table.add_column("Status")

    for report in result.agent_reports:
        status = "[red]Error[/red]" if _field(report, "error") else "[green]OK[/green]"
        findings = _field(report, "findings", [])
        agent_table.add_row(_field(report, "agent_name", "unknown"), str(len(findings)), status)

    console.print(agent_table)

    # Fix suggestion
    fix = _field(result, "fix_suggestion")
    if fix:
        fixed_code = _field(fix, "fixed_code", "")
        changes_summary = _field(fix, "changes_summary", "")
        findings_addressed = _field(fix, "findings_addressed", 0)

        if fixed_code and fixed_code != "":
            console.print()
            console.print(
                Panel(
                    f"[bold green]✨ {changes_summary}[/bold green]\nFindings addressed: {findings_addressed}",
                    title="[bold]Suggested Fix[/bold]",
                    border_style="green",
                )
            )
            console.print(Syntax(fixed_code, "python", theme="monokai", line_numbers=True))


def _field(item, key: str, default=None):
    """Read a field from either a dict or a model-like object."""
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


class ReviewResultProxy:
    """Small adapter for rendering persisted review dictionaries."""

    def __init__(self, data: dict) -> None:
        self.overall_score = data.get("overall_score", 0)
        self.summary = data.get("summary", "")
        self.findings = data.get("findings", [])
        self.conflicts = data.get("conflicts", [])
        self.agent_reports = data.get("agent_reports", [])
        self.fix_suggestion = data.get("fix_suggestion")


@app.command()
def index(
    directory: str = typer.Argument(..., help="Directory to index into the vector DB"),
):
    """Index a codebase for context-aware reviews."""
    target = Path(directory).resolve()
    if not target.is_dir():
        console.print(f"[red]Error:[/red] Not a directory: {target}")
        raise typer.Exit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold green]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Indexing {target.name}...", total=None)
        count = index_directory(str(target))
        progress.update(task, completed=True, description="Indexing complete!")

    console.print(f"[green]✅ Indexed {count} chunks from {target}[/green]")


@app.command()
def history(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of reviews to show"),
):
    """Show past review history."""
    init_db()
    reviews = list_reviews(limit)

    if not reviews:
        console.print("[yellow]No reviews found yet.[/yellow]")
        return

    table = Table(title="Review History", expand=True)
    table.add_column("ID", width=36)
    table.add_column("Status", width=12)
    table.add_column("Created", width=25)
    table.add_column("Completed", width=25)

    for r in reviews:
        status_style = {
            "completed": "green",
            "pending": "yellow",
            "failed": "red",
        }.get(r["status"], "white")
        table.add_row(
            r["id"],
            Text(r["status"], style=status_style),
            r["created_at"] or "—",
            r["completed_at"] or "—",
        )

    console.print(table)


@app.command()
def stats():
    """Show index and feedback statistics."""
    init_db()
    coll_stats = get_collection_stats()
    console.print(
        Panel(
            f"Indexed chunks: {coll_stats['count']}\nCollection exists: {coll_stats['indexed']}",
            title="[bold]Vector DB Stats[/bold]",
            border_style="blue",
        )
    )


if __name__ == "__main__":
    app()
