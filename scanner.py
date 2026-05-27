"""
scanner.py — Automated Nmap runner

Executes: nmap -sV --open -oX <out.xml> <target>
Returns path to generated XML for parser.py to consume.

Security:
  - Target validated by allowlist regex before execution
  - subprocess called with list (no shell=True) — no injection possible
  - Temp file path generated from sanitized target + timestamp only
"""

import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

# Allowlist: IPs, CIDR, hostnames, port ranges, IPv6 brackets
_SAFE_TARGET_RE = re.compile(r'^[a-zA-Z0-9.\-/:_\[\]]+$')


def validate_target(target: str) -> None:
    """
    Reject targets with chars outside the safe allowlist.

    Raises:
        ValueError: Target contains suspicious characters.
    """
    if not target or not _SAFE_TARGET_RE.match(target.strip()):
        raise ValueError(
            f"Unsafe target: {target!r}\n"
            "Allowed: IPs, CIDR (192.168.1.0/24), hostnames, ranges (1.1.1.1-254)"
        )


def run_nmap_scan(target: str, output_dir: str | None = None) -> Path:
    """
    Run nmap -sV against target. Save XML output. Return path.

    Args:
        target:     IP, hostname, CIDR, or range string.
        output_dir: Directory to write XML (default: system temp).

    Returns:
        pathlib.Path to the generated .xml file.

    Raises:
        ValueError:  Invalid target string.
        RuntimeError: nmap not found, scan failed, or timed out.
    """
    validate_target(target)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_slug = re.sub(r'[^a-zA-Z0-9]', '_', target.strip())[:40]
    filename = f"recon_{safe_slug}_{timestamp}.xml"

    base_dir = Path(output_dir) if output_dir else Path(tempfile.gettempdir())
    out_path = base_dir / filename

    cmd = [
        "nmap",
        "-sV",            # service + version detection
        "--open",         # open ports only — smaller XML payload
        "-oX", str(out_path),
        target.strip(),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5-minute hard cap
        )
    except FileNotFoundError:
        raise RuntimeError(
            "nmap not found in PATH.\n"
            "  Windows : https://nmap.org/download.html\n"
            "  Debian  : sudo apt install nmap\n"
            "  macOS   : brew install nmap"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("nmap scan timed out after 5 minutes.")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(
            f"nmap exited with code {result.returncode}.\n{stderr}"
        )

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError(
            f"nmap ran but produced no output at {out_path}\n"
            "Target may be unreachable or permissions insufficient.\n"
            "Tip: on Linux/macOS run with sudo for SYN scan."
        )

    return out_path
