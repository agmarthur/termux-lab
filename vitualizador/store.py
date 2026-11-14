"""Persistência das VMs e operações de disco com qemu-img."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from .model import VMConfig

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "vitualizador"
VM_DIR = CONFIG_DIR / "vms"
_pictures = Path.home() / "Imagens"
DISK_DIR = (_pictures if _pictures.is_dir() else Path.home()) / "VMs"


def ensure_dirs() -> None:
    VM_DIR.mkdir(parents=True, exist_ok=True)
    DISK_DIR.mkdir(parents=True, exist_ok=True)


def slug(name: str) -> str:
    base = re.sub(r"[^\w.-]+", "-", name.strip(), flags=re.UNICODE).strip("-.").lower()
    return base or "vm"


def list_vms() -> list[tuple[str, str]]:
    """Lista (slug, nome de exibição) das VMs salvas."""
    if not VM_DIR.exists():
        return []
    items: list[tuple[str, str]] = []
    for path in sorted(VM_DIR.glob("*.json")):
        name = path.stem
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            name = data.get("name") or path.stem
        except (OSError, json.JSONDecodeError):
            pass
        items.append((path.stem, name))
    return items


def load(slug_id: str) -> VMConfig:
    path = VM_DIR / f"{slug_id}.json"
    with path.open(encoding="utf-8") as fh:
        return VMConfig.from_dict(json.load(fh))


def save(cfg: VMConfig) -> str:
    ensure_dirs()
    slug_id = slug(cfg.name)
    path = VM_DIR / f"{slug_id}.json"
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(cfg.to_dict(), fh, indent=2, ensure_ascii=False)
    tmp.replace(path)
    return slug_id


def delete(slug_id: str) -> None:
    path = VM_DIR / f"{slug_id}.json"
    if path.exists():
        path.unlink()


# --------------------------- qemu-img ---------------------------

def qemu_img() -> str:
    return "qemu-img"


def create_disk(path: str, size_gb: int, fmt: str = "qcow2", preallocate: bool = False) -> str:
    """Cria um disco. Retorna a saída do qemu-img ou levanta RuntimeError."""
    args = [qemu_img(), "create", "-f", fmt]
    if preallocate and fmt == "qcow2":
        args += ["-o", "preallocation=metadata"]
    args += [path, f"{max(1, size_gb)}G"]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip() or "falha no qemu-img")
    return proc.stdout.strip()


def disk_info(path: str) -> dict[str, str]:
    proc = subprocess.run([qemu_img(), "info", "--output=json", path],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        return {}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}
    info = {
        "format": str(data.get("format", "")),
        "virtual": _human(data.get("virtual-size", 0)),
        "real": _human(data.get("actual-size", 0)),
    }
    return info


def _human(num: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(num) < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PiB"
