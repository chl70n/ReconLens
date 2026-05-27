"""
main.py — ReconLens CLI entry point

Two modes:
  --file   : parse existing Nmap XML
  --target : run nmap automatically, then analyze

Usage:
  python main.py -f scan.xml                    # parse existing XML
  python main.py -f scan.xml -v                 # verbose: show payload
  python main.py -f scan.xml -o report.md       # save report to file
  python main.py -t 192.168.1.0/24              # auto-scan + analyze
  python main.py -t scanme.nmap.org -v -o r.md  # full pipeline
"""

import sys
import json
import argparse
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

from config import LOCAL_MODEL_NAME
from parser import parse_nmap_xml
from client import query_ollama
from scanner import run_nmap_scan

console = Console()

BANNER = "[bold cyan]ReconLens[/] — Nmap → Ollama Vulnerability Insights"


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="reconlens",
        description=(
            "ReconLens: parse Nmap XML (or auto-scan a target) and get "
            f"local AI vulnerability insights via {LOCAL_MODEL_NAME} on Ollama."
        ),
    )

    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "-f", "--file",
        metavar="NMAP_XML",
        help="Path to an existing Nmap XML scan file",
    )
    source.add_argument(
        "-t", "--target",
        metavar="TARGET",
        help="Auto-scan: run nmap -sV against TARGET then analyze (e.g. 192.168.1.0/24)",
    )

    p.add_argument(
        "-o", "--output",
        metavar="REPORT_MD",
        help="Save analysis report to a markdown file",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print compressed JSON payload before querying Ollama",
    )
    return p


def main() -> None:
    args = build_arg_parser().parse_args()

    console.print(BANNER)
    console.print(f"[dim]Model:[/] {LOCAL_MODEL_NAME} [dim](local · ollama)[/]")
    console.rule()

    # ── 1. Resolve XML source ──────────────────────────────────────────────────
    if args.target:
        console.print(
            f"[bold]Auto-scan mode[/] · target: [cyan]{args.target}[/]\n"
            f"[dim]Running:[/] nmap -sV --open {args.target}"
        )
        try:
            xml_path = run_nmap_scan(args.target)
        except (ValueError, RuntimeError) as exc:
            console.print(f"[bold red]Scan Error:[/] {exc}")
            sys.exit(1)
        console.print(f"[green]✓[/] Scan complete → [dim]{xml_path}[/]")
        filepath = str(xml_path)

    else:
        filepath = args.file
        console.print(f"[dim]Loading:[/] {filepath}")

    # ── 2. Parse XML → compressed payload ─────────────────────────────────────
    try:
        payload = parse_nmap_xml(filepath)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[bold red]Parse Error:[/] {exc}")
        sys.exit(1)

    host_count = len(payload["hosts"])
    port_count = sum(len(h["open_ports"]) for h in payload["hosts"])
    console.print(
        f"[green]✓[/] {host_count} host(s) · {port_count} open port(s) extracted"
    )

    if args.verbose:
        console.print(f"\n[bold]Compressed payload → {LOCAL_MODEL_NAME}:[/]")
        console.print_json(json.dumps(payload))
        console.print()

    # ── 3. Query local Ollama ──────────────────────────────────────────────────
    console.print(f"[dim]Querying {LOCAL_MODEL_NAME} via Ollama...[/]")
    try:
        analysis = query_ollama(payload)
    except RuntimeError as exc:
        console.print(f"[bold red]Ollama Error:[/] {exc}")
        sys.exit(1)

    # ── 4. Render ──────────────────────────────────────────────────────────────
    console.rule()
    console.print(Markdown(analysis))
    console.rule()

    # ── 5. Save report ─────────────────────────────────────────────────────────
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(analysis, encoding="utf-8")
        console.print(f"\n[green]✓[/] Report saved → [bold]{out_path}[/]")


if __name__ == "__main__":
    main()
