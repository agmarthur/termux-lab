"""Descoberta de arquiteturas, máquinas, CPUs e firmwares do QEMU instalado."""

from __future__ import annotations

import functools
import glob
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArchMeta:
    key: str                 # x86_64, aarch64, riscv64, ...
    binary: str              # qemu-system-...
    label: str               # nome amigável
    family: str              # x86 | arm | riscv | ppc | s390 | mips | sparc | loong | m68k | other
    default_machine: str = ""    # "" => primeira máquina oferecida pela build
    default_vga: str = ""        # "" => padrão da build
    cdrom_mode: str = "none"     # ide | scsi | none
    net_model: str = "virtio-net-pci"
    supports_kvm: bool = False
    min_ram_mb: int = 0
    max_smp: int = 0            # 0 = sem limite conhecido
    needs_note: str = ""        # aviso: exige kernel/ROM externa no host
    notes: str = ""


# Metadados por sufixo do binário. A presença real é detectada no PATH.
_META: dict[str, dict] = {
    "x86_64": dict(label="x86_64 (PC 64 bits)", family="x86", default_machine="q35",
                   default_vga="std", cdrom_mode="ide", supports_kvm=True,
                   notes="Roda Windows/Linux modernos com KVM quase nativo."),
    "x86_64-microvm": dict(label="x86_64 microvm (leve)", family="x86", default_machine="microvm",
                           default_vga="none", cdrom_mode="none", supports_kvm=True,
                           notes="Boot mínimo, sem PCI. Ideal para kernels diretos."),
    "x86_64-spice": dict(label="x86_64 com SPICE", family="x86", default_machine="q35",
                         default_vga="qxl", cdrom_mode="ide", supports_kvm=True),
    "i386": dict(label="x86 (PC 32 bits)", family="x86", default_machine="pc",
                 default_vga="std", cdrom_mode="ide", supports_kvm=True,
                 notes="Para sistemas 32 bits antigos (DOS, Win9x, Linux antigo)."),
    "aarch64": dict(label="ARM64 / AArch64", family="arm", default_machine="virt",
                    default_vga="virtio-gpu-pci", cdrom_mode="scsi",
                    supports_kvm=True, notes="Precisa de firmware UEFI (QEMU_EFI) para bootar ISO."),
    "arm": dict(label="ARM 32 bits", family="arm", default_machine="virt",
                default_vga="virtio-gpu-pci", cdrom_mode="scsi",
                notes="Precisa de firmware/kernel próprio na maioria dos casos."),
    "riscv64": dict(label="RISC-V 64 bits", family="riscv", default_machine="virt",
                    default_vga="virtio-gpu-pci", cdrom_mode="scsi",
                    notes="Use OpenSBI (padrão) + UEFI ou boot direto de kernel."),
    "riscv32": dict(label="RISC-V 32 bits", family="riscv", default_machine="virt",
                    default_vga="virtio-gpu-pci", cdrom_mode="scsi"),
    "ppc64": dict(label="PowerPC 64 bits (big endian)", family="ppc", default_machine="pseries",
                  cdrom_mode="scsi"),
    "ppc64le": dict(label="PowerPC 64 bits little endian", family="ppc", default_machine="pseries",
                    cdrom_mode="scsi"),
    "ppc": dict(label="PowerPC 32 bits", family="ppc", default_machine="mac99",
                default_vga="std", cdrom_mode="ide"),
    "s390x": dict(label="IBM Z (s390x)", family="s390", default_machine="s390-ccw-virtio"),
    "mips64": dict(label="MIPS 64 bits", family="mips", default_machine="malta", default_vga="std",
                   cdrom_mode="ide"),
    "mips64el": dict(label="MIPS 64 bits little endian", family="mips", default_machine="malta",
                     default_vga="std", cdrom_mode="ide"),
    "mips": dict(label="MIPS 32 bits", family="mips", default_machine="malta", default_vga="std",
                 cdrom_mode="ide"),
    "mipsel": dict(label="MIPS 32 bits little endian", family="mips", default_machine="malta",
                   default_vga="std", cdrom_mode="ide"),
    "sparc64": dict(label="SPARC 64 bits", family="sparc", default_machine="sun4u"),
    "sparc": dict(label="SPARC 32 bits", family="sparc", default_machine="sun4m"),
    "loongarch64": dict(label="LoongArch 64 bits", family="loong", default_machine="virt",
                        default_vga="virtio-gpu-pci", cdrom_mode="scsi", min_ram_mb=2048),
    "loong64": dict(label="LoongArch 64 bits (alias)", family="loong", default_machine="virt",
                    default_vga="virtio-gpu-pci", cdrom_mode="scsi", min_ram_mb=2048),
    "m68k": dict(max_smp=1, label="Motorola 68k", family="m68k", default_machine="q800"),
    "alpha": dict(label="DEC Alpha", family="other", default_machine="clipper"),
    "hppa": dict(label="HP PA-RISC", family="other", default_machine="B160L"),
    "rx": dict(max_smp=1, label="Renesas RX", family="other",
               default_machine="gdbsim-r5f562n7",
               needs_note="Máquinas RX exigem BIOS/kernel para iniciar."),
    "tricore": dict(max_smp=1, label="Infineon TriCore", family="other",
                    default_machine="tricore_testboard"),
    "avr": dict(max_smp=1, label="AVR (microcontrolador)", family="other",
                default_machine="arduino-uno", net_model="",
                notes="Simula placas Arduino; não é um PC."),
    "cris": dict(max_smp=1, label="Axis CRIS", family="other",
                 needs_note="Máquinas CRIS exigem imagem de kernel."),
    "microblaze": dict(max_smp=1, label="Xilinx MicroBlaze", family="other"),
    "microblazeel": dict(max_smp=1, label="Xilinx MicroBlaze (LE)", family="other"),
    "nios2": dict(max_smp=1, label="Altera Nios II", family="other"),
    "or1k": dict(label="OpenRISC 1000", family="other"),
    "sh4": dict(max_smp=1, label="SuperH SH-4", family="other",
                needs_note="A máquina shix exige shix_bios.bin no host."),
    "sh4eb": dict(max_smp=1, label="SuperH SH-4 (big endian)", family="other",
                  needs_note="A máquina shix exige shix_bios.bin no host."),
    "xtensa": dict(label="Tensilica Xtensa", family="other"),
    "xtensaeb": dict(label="Tensilica Xtensa (BE)", family="other"),
}

# Pacotes Debian/Ubuntu que trazem as arquiteturas ausentes.
_PACKAGES = [
    ("aarch64", "qemu-system-arm"),
    ("arm", "qemu-system-arm"),
    ("ppc64", "qemu-system-ppc"),
    ("s390x", "qemu-system-s390x"),
    ("mips", "qemu-system-mips"),
    ("sparc", "qemu-system-sparc"),
    ("m68k", "qemu-system-misc"),
]


def _host_arches() -> set[str]:
    m = platform.machine().lower()
    return {
        "x86_64": {"x86_64", "i386", "amd64", "intel"},
        "amd64": {"x86_64", "i386", "amd64"},
        "aarch64": {"aarch64", "arm"},
        "arm64": {"aarch64", "arm"},
        "armv7l": {"arm", "aarch64"},
        "riscv64": {"riscv64", "riscv32"},
        "ppc64le": {"ppc64le", "ppc64"},
        "s390x": {"s390x"},
    }.get(m, {m})


def discover_architectures() -> dict[str, ArchMeta]:
    """Todas as arquiteturas presentes no PATH, com metadados."""
    found: dict[str, ArchMeta] = {}
    host = _host_arches()
    for path in sorted(glob.glob("/usr/bin/qemu-system-*") + glob.glob("/usr/local/bin/qemu-system-*")):
        key = os.path.basename(path)[len("qemu-system-"):]
        if not os.access(path, os.X_OK) or key in ("aarch64",) and False:
            continue
        meta = _META.get(key, {})
        family = meta.get("family", "other")
        found[key] = ArchMeta(
            key=key,
            binary=os.path.basename(path),
            label=meta.get("label", key),
            family=family,
            default_machine=meta.get("default_machine", ""),
            default_vga=meta.get("default_vga", ""),
            cdrom_mode=meta.get("cdrom_mode", "none"),
            net_model=meta.get("net_model", "virtio-net-pci"),
            supports_kvm=meta.get("supports_kvm", False) or (family in ("x86", "arm") and key in host),
            min_ram_mb=meta.get("min_ram_mb", 0),
            max_smp=meta.get("max_smp", 0),
            needs_note=meta.get("needs_note", ""),
            notes=meta.get("notes", ""),
        )
    return found


def missing_architectures(available: dict[str, ArchMeta]) -> list[tuple[str, str]]:
    """Arquiteturas comuns que não estão instaladas, com o pacote sugerido."""
    return [(a, p) for a, p in _PACKAGES if a not in available]


@functools.lru_cache(maxsize=None)
def list_machines(binary: str) -> list[tuple[str, str]]:
    """(nome, descrição) das máquinas suportadas pela build."""
    out = _run([binary, "-machine", "help"])
    machines: list[tuple[str, str]] = []
    for line in out.splitlines()[1:]:
        line = line.rstrip()
        if not line.strip():
            continue
        parts = line.split(None, 1)
        name = parts[0]
        desc = parts[1].strip() if len(parts) > 1 else ""
        if name == "none":
            continue
        machines.append((name, desc))
    return machines


@functools.lru_cache(maxsize=None)
def default_machine(binary: str) -> str:
    for name, desc in list_machines(binary):
        if "(default)" in desc:
            return name
    return ""


@functools.lru_cache(maxsize=None)
def list_cpus(binary: str) -> list[str]:
    out = _run([binary, "-cpu", "help"])
    cpus: list[str] = []
    skip_prefix = {"x86", "PowerPC", "ARM", "MIPS", "s390", "RISC-V", "TriCore", "HPPA", "CRIS"}
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("Available") or line.startswith("Recognized"):
            continue
        parts = line.split()
        if parts[0] in skip_prefix and len(parts) > 1:
            name = parts[1]
        else:
            name = parts[0]
        if name and name not in cpus:
            cpus.append(name)
    return cpus


@functools.lru_cache(maxsize=None)
def list_display_backends(binary: str) -> list[str]:
    out = _run([binary, "-display", "help"])
    return [ln.strip() for ln in out.splitlines() if ln.strip() and not ln.startswith("Available")]


@functools.lru_cache(maxsize=None)
def has_accel(binary: str, accel: str) -> bool:
    out = _run([binary, "-accel", "help"])
    return any(ln.strip() == accel for ln in out.splitlines())


def kvm_usable() -> bool:
    return os.path.exists("/dev/kvm") and os.access("/dev/kvm", os.R_OK | os.W_OK)


def _run(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return proc.stdout + proc.stderr
    except (OSError, subprocess.SubprocessError):
        return ""


def firmware_candidates() -> list[tuple[str, str]]:
    """(rótulo, caminho do arquivo de código) dos firmwares UEFI encontrados."""
    candidates: list[tuple[str, str]] = []
    for path in (
        "/usr/share/OVMF/OVMF_CODE_4M.fd",
        "/usr/share/OVMF/OVMF_CODE.fd",
        "/usr/share/qemu/OVMF.fd",
        "/usr/share/edk2/x64/OVMF_CODE.4m.fd",
        "/usr/share/edk2/x64/OVMF_CODE.fd",
    ):
        if os.path.exists(path):
            candidates.append(("UEFI / OVMF (x86_64)", path))
            break
    for path in (
        "/usr/share/qemu-efi-aarch64/QEMU_EFI.fd",
        "/usr/share/AAVMF/AAVMF_CODE.fd",
        "/usr/share/edk2/aarch64/QEMU_EFI.fd",
        "/usr/share/edk2/aarch64/QEMU_EFI-pflash.raw",
    ):
        if os.path.exists(path):
            candidates.append(("UEFI / AAVMF (ARM64)", path))
            break
    for path in (
        "/usr/share/qemu/opensbi-riscv64-generic-fw_dynamic.bin",
        "/usr/share/opensbi/lp64/generic/firmware/fw_dynamic.bin",
    ):
        if os.path.exists(path):
            candidates.append(("OpenSBI (RISC-V)", path))
            break
    return candidates


def firmware_vars_for(code_path: str) -> str | None:
    """Arquivo de variáveis (NVRAM) correspondente ao código UEFI, se houver."""
    d, base = os.path.split(code_path)
    for name in ("OVMF_VARS_4M.fd", "OVMF_VARS.fd", "AAVMF_VARS.fd", "QEMU_VARS.fd"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None
