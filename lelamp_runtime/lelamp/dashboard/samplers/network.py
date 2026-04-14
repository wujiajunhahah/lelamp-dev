"""Reachable local URL helpers for the dashboard."""

from __future__ import annotations

import socket
import subprocess


def build_reachable_urls(host: str, port: int, *, ip_list: list[str] | None = None) -> list[str]:
    urls: list[str] = []

    if host == "0.0.0.0":
        urls.append(f"http://127.0.0.1:{port}")
        addresses = _local_ipv4_addresses() if ip_list is None else ip_list
        for address in addresses:
            urls.append(f"http://{_format_host(address)}:{port}")
    elif host == "::":
        urls.append(f"http://[::1]:{port}")
        addresses = _local_ipv4_addresses() if ip_list is None else ip_list
        for address in addresses:
            urls.append(f"http://{_format_host(address)}:{port}")
    else:
        urls.append(f"http://{_format_host(host)}:{port}")

    deduped: list[str] = []
    for url in urls:
        if url not in deduped:
            deduped.append(url)
    return deduped


def _local_ipv4_addresses() -> list[str]:
    addresses: list[str] = []

    try:
        addresses.extend(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass

    addresses.extend(_hostname_command_ipv4_addresses())

    deduped: list[str] = []
    for address in addresses:
        if "." not in address or address.startswith("127."):
            continue
        if address not in deduped:
            deduped.append(address)
    return deduped


def _hostname_command_ipv4_addresses() -> list[str]:
    try:
        result = subprocess.run(
            ["hostname", "-I"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []

    if result.returncode != 0:
        return []

    return [part for part in result.stdout.split() if "." in part]


def _format_host(address: str) -> str:
    if ":" in address and not address.startswith("["):
        return f"[{address}]"
    return address
