import argparse
import asyncio
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from mcp.orchestrator import run_pipeline


DEMO_QUERIES: List[Dict[str, Any]] = [
    {
        "question": "Is Kedarkantha safe in December?",
        "highlights": ["Weather", "Winter", "Snow"],
    },
    {
        "question": "What permits do I need for Valley of Flowers?",
        "highlights": ["Permit", "Booking", "Best time"],
    },
    {
        "question": "Accommodation options near Triund",
        "highlights": ["Camping", "Guesthouse", "Booking"],
    },
    {
        "question": "Difficulty level and fitness required for Hampta Pass",
        "highlights": ["River", "Altitude", "Training"],
    },
    {
        "question": "Best time to climb Kalsubai",
        "highlights": ["Monsoon", "Night trek", "Weather"],
    },
]


console = Console()


async def run_one(question: str) -> Tuple[Dict[str, Any], List[str], float]:
    logs: List[str] = []

    async def on_progress(msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        logs.append(f"[{ts}] {msg}")
        console.print(f"[dim]{ts}[/dim] • {msg}")

    start = time.perf_counter()
    result = await run_pipeline(question, on_progress)
    elapsed = time.perf_counter() - start
    return result, logs, elapsed


def contains_any(text: str, keys: List[str]) -> int:
    lower = (text or "").lower()
    return sum(1 for k in keys if k.lower() in lower)


def verify_highlights(result: Dict[str, Any], highlights: List[str]) -> Tuple[int, int]:
    total = len(highlights)
    found = 0
    # Check final answer
    found += contains_any(result.get("final_answer") or result.get("answer", ""), highlights)
    # Check retrieved context
    for item in result.get("retrieved_context", []) or []:
        found += contains_any(str(item), highlights)
    # Check raw documents
    for item in result.get("raw_documents", []) or []:
        found += contains_any(str(item), highlights)
    # Cap at total so reporting is clear
    return min(found, total), total


def write_markdown_report(rows: List[Dict[str, Any]], path: str) -> None:
    lines: List[str] = ["# PeakPilot Demo Results", ""]
    for r in rows:
        lines.append(f"## {r['question']}")
        lines.append("")
        lines.append(f"Time: {r['time_s']:.2f}s  ")
        lines.append(f"Progress messages: {r['progress_count']}  ")
        lines.append(f"Highlights: {r['highlights_found']}/{r['highlights_total']}  ")
        lines.append("")
        lines.append("### Answer")
        lines.append("")
        lines.append(r.get("final_answer", r.get("answer", "(no answer)")))
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


async def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="PeakPilot Demo Runner")
    parser.add_argument("--all", action="store_true", help="Run all demo queries")
    parser.add_argument("--index", type=int, default=None, help="Run a single demo by index (0-based)")
    parser.add_argument("--question", type=str, default=None, help="Run a single custom question")
    parser.add_argument("--save", type=str, default="demo/demo_results.md", help="Markdown output path")
    args = parser.parse_args()

    to_run: List[Dict[str, Any]]
    if args.question:
        to_run = [{"question": args.question, "highlights": []}]
    elif args.index is not None:
        to_run = [DEMO_QUERIES[args.index]]
    else:
        to_run = DEMO_QUERIES if args.all or args.index is None else [DEMO_QUERIES[0]]

    results_for_md: List[Dict[str, Any]] = []

    console.rule("[bold]PeakPilot Demo")
    for i, item in enumerate(to_run):
        q = item["question"]
        highlights = item.get("highlights", [])

        console.print(Panel.fit(f"[bold]Query {i+1}[/bold]: {q}", style="cyan"))
        result, logs, elapsed = await run_one(q)

        found, total = verify_highlights(result, highlights)

        table = Table(title=f"Result {i+1}")
        table.add_column("Metric", style="bold")
        table.add_column("Value")
        table.add_row("Time", f"{elapsed:.2f}s")
        table.add_row("Progress msgs", str(len(logs)))
        table.add_row("Highlights", f"{found}/{total}")
        table.add_row("Docs indexed", str(len(result.get("raw_documents", []))))
        table.add_row("Context retrieved", str(len(result.get("retrieved_context", []))))
        console.print(table)

        ok = len((result.get("final_answer") or result.get("answer", "")).strip()) > 0
        if ok:
            console.print("[green]✓ Success[/green]")
        else:
            console.print("[red]✗ Failed[/red]")

        results_for_md.append({
            "question": q,
            "time_s": elapsed,
            "progress_count": len(logs),
            "highlights_found": found,
            "highlights_total": total,
            "final_answer": result.get("final_answer") or result.get("answer", ""),
        })

    # Save report
    os.makedirs(os.path.dirname(args.save), exist_ok=True)
    write_markdown_report(results_for_md, args.save)
    console.print(f"[dim]Saved report to {args.save}[/dim]")


if __name__ == "__main__":
    asyncio.run(main())

