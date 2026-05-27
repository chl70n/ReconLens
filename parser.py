"""
parser.py — Nmap XML → lean dict

Extracts only: ip, port, proto, service, version (open ports only).
Drops all Nmap metadata, timing, scripts, OS info.

Security:
  - defusedxml.ElementTree blocks XXE, DTD injection, billion-laughs
  - pathlib.Path.resolve() canonicalizes path (prevents traversal)
  - Extension check + file size guard before parse
"""

import json
from pathlib import Path

import defusedxml.ElementTree as ET

_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


def parse_nmap_xml(filepath: str) -> dict:
    """
    Parse a local Nmap XML file into a minimal dict.

    Args:
        filepath: Absolute or relative path to an Nmap .xml scan file.

    Returns:
        {
            "hosts": [
                {
                    "ip": "10.0.0.1",
                    "open_ports": [
                        {"port": 22, "proto": "tcp", "service": "ssh", "version": "OpenSSH 7.6p1"}
                    ]
                }
            ]
        }
        Only hosts with at least one open port are included.

    Raises:
        FileNotFoundError: path does not exist.
        ValueError:        not a .xml file, exceeds size limit, or malformed XML.
    """
    path = Path(filepath).resolve()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() != ".xml":
        raise ValueError(f"Expected .xml extension, got: {path.suffix!r}")

    size = path.stat().st_size
    if size > _MAX_FILE_BYTES:
        raise ValueError(
            f"File too large ({size / 1024 / 1024:.1f} MB). Limit is 10 MB."
        )

    try:
        tree = ET.parse(str(path))
    except ET.ParseError as exc:
        raise ValueError(f"Malformed XML: {exc}") from exc

    root = tree.getroot()
    hosts = []

    for host in root.findall("host"):
        addr_el = host.find("address[@addrtype='ipv4']")
        if addr_el is None:
            continue
        ip = addr_el.get("addr", "unknown")

        open_ports = []
        ports_container = host.find("ports")
        if ports_container is not None:
            for port in ports_container.findall("port"):
                state_el = port.find("state")
                if state_el is None or state_el.get("state") != "open":
                    continue  # skip closed/filtered

                portid = int(port.get("portid", 0))
                proto = port.get("protocol", "tcp")

                svc_el = port.find("service")
                if svc_el is not None:
                    service = svc_el.get("name", "unknown")
                    product = svc_el.get("product", "").strip()
                    version = svc_el.get("version", "").strip()
                    version_str = f"{product} {version}".strip() or "unknown"
                else:
                    service = "unknown"
                    version_str = "unknown"

                open_ports.append(
                    {
                        "port": portid,
                        "proto": proto,
                        "service": service,
                        "version": version_str,
                    }
                )

        if open_ports:
            hosts.append({"ip": ip, "open_ports": open_ports})

    return {"hosts": hosts}


def payload_to_json(payload: dict) -> str:
    """Serialize payload to compact JSON (no whitespace) for API submission."""
    return json.dumps(payload, separators=(",", ":"))
