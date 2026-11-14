"""Modelo de configuração de uma máquina virtual (serializável em JSON)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any


@dataclass
class Disk:
    path: str = ""
    fmt: str = "qcow2"
    interface: str = "virtio"   # virtio | scsi | ide | usb
    size_gb: int = 20           # usado só ao criar o arquivo
    readonly: bool = False

    def exists(self) -> bool:
        return bool(self.path) and __import__("os").path.exists(self.path)


@dataclass
class PortForward:
    proto: str = "tcp"          # tcp | udp
    host: int = 2222
    guest: int = 22

    def to_qemu(self) -> str:
        return f"hostfwd={self.proto}::{self.host}-:{self.guest}"


@dataclass
class VMConfig:
    name: str = "Nova VM"
    arch: str = "x86_64"
    machine: str = ""            # "" = padrão da arquitetura
    cpu: str = ""                # "" = automático
    accel: str = "auto"          # auto | kvm | tcg
    smp: int = 2
    ram_mb: int = 2048

    firmware: str = ""           # "" = BIOS padrão | caminho do UEFI/OpenSBI
    kernel: str = ""
    initrd: str = ""
    append: str = ""
    boot_order: str = "cd"       # cd | disk | network

    disks: list[Disk] = field(default_factory=list)
    isos: list[str] = field(default_factory=list)

    net_mode: str = "user"       # none | user | bridge | tap
    net_model: str = ""          # "" = padrão da arquitetura
    mac: str = ""
    forwards: list[PortForward] = field(default_factory=list)
    bridge: str = "virbr0"
    tap: str = "tap0"

    display: str = "gtk"         # gtk | sdl | vnc | none
    vga: str = ""                # "" = padrão | std | qxl | virtio | cirrus | none
    vnc_display: str = ":0"
    show_menu: bool = True
    serial_console: bool = False
    usb_tablet: bool = False
    audio: bool = False
    snapshot: bool = False
    rtc_localtime: bool = True
    share_path: str = ""
    share_tag: str = "hostshare"
    extra_args: str = ""

    # ---------- serialização ----------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VMConfig":
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in data.items() if k in known}
        data["disks"] = [Disk(**_filter(Disk, d)) for d in data.get("disks", [])]
        data["forwards"] = [PortForward(**_filter(PortForward, f))
                            for f in data.get("forwards", [])]
        return cls(**data)

    def clone(self, new_name: str) -> "VMConfig":
        data = self.to_dict()
        data["name"] = new_name
        return VMConfig.from_dict(data)


def _filter(dc: type, data: dict[str, Any]) -> dict[str, Any]:
    known = {f.name for f in fields(dc)}
    return {k: v for k, v in data.items() if k in known}
