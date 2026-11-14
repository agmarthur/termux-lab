"""Tradução da configuração para a linha de comando do QEMU."""

from __future__ import annotations

import os
import re
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import arch as A
from .model import VMConfig


@dataclass
class Plan:
    argv: list[str]
    warnings: list[str]

    def pretty(self) -> str:
        return shlex.join(self.argv)


def _default_cpu(cfg: VMConfig, meta: A.ArchMeta, accel: str) -> str:
    if cfg.cpu:
        return cfg.cpu
    if accel == "kvm":
        return "host"
    cpus = A.list_cpus(meta.binary)
    if not cpus:
        return ""            # build sem lista de CPUs: deixa o padrão do QEMU
    return "max" if "max" in cpus else ""


def _machine(cfg: VMConfig, meta: A.ArchMeta) -> str:
    if cfg.machine:
        return cfg.machine
    if meta.default_machine:
        return meta.default_machine
    return A.default_machine(meta.binary)


def _resolve_accel(cfg: VMConfig, meta: A.ArchMeta, warnings: list[str]) -> str:
    if cfg.accel in ("kvm", "tcg"):
        chosen = cfg.accel
    else:
        chosen = "kvm" if (meta.supports_kvm and A.kvm_usable()
                           and A.has_accel(meta.binary, "kvm")) else "tcg"
    if chosen == "kvm":
        if not A.kvm_usable():
            warnings.append("/dev/kvm indisponível — caindo para emulação (TCG).")
            chosen = "tcg"
        elif not A.has_accel(meta.binary, "kvm"):
            warnings.append(f"{meta.binary} não suporta KVM — usando TCG.")
            chosen = "tcg"
        elif not meta.supports_kvm:
            warnings.append("KVM só acelera a arquitetura nativa; usando TCG.")
            chosen = "tcg"
    return chosen


def _pci_device(name: str, machine: str) -> str:
    """virtio-blk-pci em máquinas com PCI, virtio-blk-device no microvm."""
    if machine == "microvm" or machine.startswith("microvm"):
        return f"{name}-device"
    return f"{name}-pci"


def _nvram_copy(code_path: str, vm_name: str) -> str | None:
    """Copia o OVMF_VARS para um arquivo por VM (o original em /usr é do sistema)."""
    source = A.firmware_vars_for(code_path)
    if not source:
        return None
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) \
        / "vitualizador" / "nvram"
    try:
        base.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^\w.-]+", "-", vm_name.strip().lower()) or "vm"
        dest = base / f"{name}.fd"
        if not dest.exists() or dest.stat().st_size != os.path.getsize(source):
            shutil.copyfile(source, dest)
        return str(dest)
    except OSError:
        return source


def build(cfg: VMConfig, meta: A.ArchMeta) -> Plan:
    warnings: list[str] = []
    argv: list[str] = [meta.binary]

    accel = _resolve_accel(cfg, meta, warnings)
    machine = _machine(cfg, meta)
    if not machine:
        warnings.append("Não foi possível determinar a máquina; informe uma manualmente.")
    cpu = _default_cpu(cfg, meta, accel)

    # --- identificação e recursos
    argv += ["-name", cfg.name or "vm"]
    machine_opts = [machine] if machine else []
    machine_opts.append(f"accel={accel}")
    argv += ["-machine", ",".join(machine_opts)]
    if cpu:
        argv += ["-cpu", cpu]
    smp = max(1, cfg.smp)
    if meta.max_smp and smp > meta.max_smp:
        warnings.append(f"{meta.label} só aceita {meta.max_smp} CPU(s); ajustando.")
        smp = meta.max_smp
    if smp > 1:
        argv += ["-smp", str(smp)]
    ram = max(64, cfg.ram_mb)
    if meta.min_ram_mb and ram < meta.min_ram_mb:
        warnings.append(f"{meta.label} exige ao menos {meta.min_ram_mb} MB; "
                        f"ajustando de {ram} MB.")
        ram = meta.min_ram_mb
    argv += ["-m", f"{ram}M"]

    # --- firmware
    if cfg.firmware and cfg.firmware not in ("", "bios"):
        path = cfg.firmware
        if not os.path.exists(path):
            warnings.append(f"Firmware não encontrado: {path}")
        elif path.endswith(".fd") and meta.family == "x86":
            variables = _nvram_copy(path, cfg.name)
            if variables:
                argv += ["-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={path}"]
                argv += ["-drive", f"if=pflash,format=raw,unit=1,file={variables}"]
            else:
                argv += ["-bios", path]
        else:
            argv += ["-bios", path]

    if meta.needs_note:
        warnings.append(meta.needs_note)

    # --- firmware padrão exigido por algumas máquinas
    if not cfg.firmware and not cfg.kernel and meta.family in ("riscv", "arm", "loong"):
        needed = f"opensbi-{meta.key}-generic-fw_dynamic.bin" if meta.family == "riscv" else ""
        if needed and not os.path.exists(f"/usr/share/qemu/{needed}"):
            warnings.append(f"Firmware padrão ausente ({needed}); use boot direto de "
                            f"kernel ou instale o pacote opensbi.")

    # --- boot direto de kernel
    if cfg.kernel:
        if not os.path.exists(cfg.kernel):
            warnings.append(f"Kernel não encontrado: {cfg.kernel}")
        argv += ["-kernel", cfg.kernel]
        if cfg.initrd:
            if not os.path.exists(cfg.initrd):
                warnings.append(f"Initrd não encontrado: {cfg.initrd}")
            argv += ["-initrd", cfg.initrd]
        if cfg.append:
            argv += ["-append", cfg.append]

    # --- ordem de boot
    boot_opts: list[str] = []
    boot = {"cd": "d", "disk": "c", "network": "n"}.get(cfg.boot_order)
    if boot:
        boot_opts.append(f"order={boot}")
    if cfg.show_menu:
        boot_opts.append("menu=on")
    if boot_opts:
        argv += ["-boot", ",".join(boot_opts)]

    # --- discos
    scsi_id = 0
    scsi_controller_added = False
    usb_controller_added = False

    def ensure_scsi() -> None:
        nonlocal scsi_controller_added
        if not scsi_controller_added:
            dev = _pci_device("virtio-scsi", machine)
            argv.extend(["-device", f"{dev},id=scsi0"])
            scsi_controller_added = True

    def ensure_usb() -> None:
        nonlocal usb_controller_added
        if not usb_controller_added:
            argv.extend(["-device", "qemu-xhci,id=xhci0"])
            usb_controller_added = True

    for i, disk in enumerate(cfg.disks):
        if not disk.path:
            continue
        if not os.path.exists(disk.path):
            warnings.append(f"Disco não encontrado: {disk.path}")
        drive_id = f"drv{i}"
        opts = [f"file={disk.path}", f"format={disk.fmt}", "if=none", f"id={drive_id}",
                "cache=writeback"]
        if disk.readonly:
            opts.append("readonly=on")
        iface = disk.interface
        if iface == "ide":
            if meta.family != "x86":
                warnings.append(f"IDE não existe em {meta.key}; disco {disk.path} virou virtio.")
                iface = "virtio"
            else:
                argv += ["-drive", f"file={disk.path},format={disk.fmt},if=ide,index={i}"]
                continue
        argv += ["-drive", ",".join(opts)]
        if iface == "scsi":
            ensure_scsi()
            argv += ["-device", f"scsi-hd,drive={drive_id},bus=scsi0.0,channel=0,"
                                f"scsi-id={scsi_id},lun=0"]
            scsi_id += 1
        elif iface == "usb":
            ensure_usb()
            argv += ["-device", f"usb-storage,drive={drive_id}"]
        else:
            dev = _pci_device("virtio-blk", machine)
            opts = f"{dev},drive={drive_id}"
            if cfg.boot_order == "disk" and i == 0:
                opts += ",bootindex=1"
            argv += ["-device", opts]

    # --- CDs / ISOs
    for j, iso in enumerate(cfg.isos):
        if not iso:
            continue
        if not os.path.exists(iso):
            warnings.append(f"ISO não encontrada: {iso}")
        cd_id = f"cd{j}"
        if meta.cdrom_mode == "ide":
            argv += ["-drive", f"file={iso},format=raw,media=cdrom,if=none,id={cd_id},readonly=on"]
            argv += ["-device", f"ide-cd,drive={cd_id}"]
        elif meta.cdrom_mode == "scsi":
            ensure_scsi()
            argv += ["-drive", f"file={iso},format=raw,media=cdrom,if=none,id={cd_id},readonly=on"]
            argv += ["-device", f"scsi-cd,drive={cd_id},bus=scsi0.0,scsi-id={scsi_id + 5},lun=0"]
            scsi_id += 1
        else:
            warnings.append(f"A arquitetura {meta.key} não tem controlador de CD-ROM.")
            break

    # --- rede
    if cfg.net_mode == "none":
        argv += ["-nic", "none"]
    elif meta.net_model == "":
        pass
    else:
        model = cfg.net_model or meta.net_model
        netdev = ["user", "id=net0"]
        if cfg.net_mode == "user":
            netdev = ["user", "id=net0"]
            for fwd in cfg.forwards:
                netdev.append(fwd.to_qemu())
        elif cfg.net_mode == "bridge":
            netdev = ["bridge", "id=net0", f"br={cfg.bridge}"]
        elif cfg.net_mode == "tap":
            netdev = ["tap", "id=net0", f"ifname={cfg.tap}",
                      "script=no", "downscript=no"]
        argv += ["-netdev", ",".join(netdev)]
        dev = model
        if model.endswith("-pci") and machine.startswith("microvm"):
            dev = model[:-4] + "-device"
        opts = [f"netdev=net0"]
        if cfg.mac:
            opts.append(f"mac={cfg.mac}")
        if cfg.boot_order == "network":
            opts.append("bootindex=2")
        argv += ["-device", f"{dev}," + ",".join(opts)]

    # --- vídeo
    if cfg.serial_console:
        argv += ["-nographic"]
    else:
        if cfg.display == "none":
            argv += ["-display", "none"]
        elif cfg.display == "vnc":
            argv += ["-display", f"vnc={cfg.vnc_display or ':0'}"]
        elif cfg.display in ("gtk", "sdl"):
            argv += ["-display", cfg.display]
        vga = cfg.vga
        if vga == "none":
            argv += ["-vga", "none"]
        elif vga in ("std", "qxl", "cirrus", "vmware"):
            if meta.family != "x86":
                warnings.append("VGA clássica só existe em máquinas x86; usando padrão.")
            else:
                argv += ["-vga", vga]
        elif vga == "virtio":
            dev = _pci_device("virtio-gpu", machine)
            argv += ["-device", f"{dev}"]
        elif vga == "auto" or (not vga and meta.default_vga and meta.family != "x86"):
            devname = meta.default_vga or "virtio-gpu-pci"
            if devname:
                argv += ["-device", devname]

    # --- dispositivos opcionais
    if cfg.usb_tablet:
        ensure_usb()
        argv += ["-device", "usb-tablet"]
    if cfg.audio:
        if meta.family == "x86":
            argv += ["-audiodev", "pa,id=snd0"]
            argv += ["-device", "ich9-intel-hda"]
            argv += ["-device", "hda-duplex,audiodev=snd0"]
        else:
            warnings.append("Áudio configurado apenas para x86 nesta interface.")
    if cfg.snapshot:
        argv += ["-snapshot"]
    if cfg.rtc_localtime:
        argv += ["-rtc", "base=localtime"]
    if cfg.share_path:
        if os.path.isdir(cfg.share_path):
            argv += ["-virtfs", f"local,path={cfg.share_path},"
                                f"mount_tag={cfg.share_tag or 'hostshare'},"
                                f"security_model=mapped-xattr"]
        else:
            warnings.append(f"Pasta compartilhada não encontrada: {cfg.share_path}")

    if cfg.extra_args.strip():
        try:
            argv += shlex.split(cfg.extra_args)
        except ValueError as exc:
            warnings.append(f"Argumentos extras inválidos: {exc}")

    if not shutil.which(meta.binary):
        warnings.append(f"Binário não encontrado no PATH: {meta.binary}")

    return Plan(argv, warnings)
