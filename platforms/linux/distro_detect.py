"""Linux distribution family detection from /etc/os-release."""

from __future__ import annotations

from pathlib import Path

DEBIAN_IDS = frozenset({
    "debian", "ubuntu", "linuxmint", "pop", "elementary", "zorin", "kali", "raspbian",
})
RHEL_IDS = frozenset({
    "rhel", "fedora", "centos", "rocky", "almalinux", "ol", "scientific", "amzn",
})
ARCH_IDS = frozenset({
    "arch", "manjaro", "endeavouros", "artix", "garuda", "cachyos", "archlinux",
})
SUSE_IDS = frozenset({
    "suse", "opensuse", "opensuse-leap", "opensuse-tumbleweed", "sles",
})

FAMILY_BY_TOKEN = {
    "debian": "debian",
    "ubuntu": "debian",
    "rhel": "rhel",
    "fedora": "rhel",
    "centos": "rhel",
    "arch": "arch",
    "suse": "suse",
    "opensuse": "suse",
}


def parseOsRelease(osReleasePath: str = "/etc/os-release") -> dict[str, str]:
    """Parse key=value pairs from an os-release file."""
    releasePath = Path(osReleasePath)
    if not releasePath.is_file():
        return {}

    parsed: dict[str, str] = {}
    try:
        content = releasePath.read_text(encoding="utf-8")
    except OSError:
        return {}

    for rawLine in content.splitlines():
        line = rawLine.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def detectDistroFamily(osReleasePath: str = "/etc/os-release") -> str:
    """
    Map the running distro to a family: debian, rhel, arch, suse, or unknown.

    Prefers ``ID``, then tokens in ``ID_LIKE``.
    """
    fields = parseOsRelease(osReleasePath)
    if not fields:
        return "unknown"

    distroId = fields.get("ID", "").lower()
    if distroId in DEBIAN_IDS:
        return "debian"
    if distroId in RHEL_IDS:
        return "rhel"
    if distroId in ARCH_IDS:
        return "arch"
    if distroId in SUSE_IDS:
        return "suse"

    idLike = fields.get("ID_LIKE", "").lower().split()
    for token in idLike:
        if token in FAMILY_BY_TOKEN:
            return FAMILY_BY_TOKEN[token]
        if token in DEBIAN_IDS:
            return "debian"
        if token in RHEL_IDS:
            return "rhel"
        if token in ARCH_IDS:
            return "arch"
        if token in SUSE_IDS:
            return "suse"

    return "unknown"


def getDistroInfo(osReleasePath: str = "/etc/os-release") -> dict:
    """Return parsed os-release fields plus detected family."""
    fields = parseOsRelease(osReleasePath)
    family = detectDistroFamily(osReleasePath)
    return {
        "id": fields.get("ID", ""),
        "idLike": fields.get("ID_LIKE", ""),
        "name": fields.get("NAME", ""),
        "prettyName": fields.get("PRETTY_NAME", ""),
        "versionId": fields.get("VERSION_ID", ""),
        "family": family,
        "isConfident": bool(fields) and family != "unknown",
    }
