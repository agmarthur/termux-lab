"""Ponto de entrada: python3 -m vitualizador [--selftest]"""

from __future__ import annotations

import sys

from . import build as B
from . import arch as A
from .model import Disk, PortForward, VMConfig


def selftest() -> int:
    """Valida o gerador de comandos sem abrir a GUI."""
    arches = A.discover_architectures()
    print(f"arquiteturas detectadas: {len(arches)}")
    for key, meta in sorted(arches.items()):
        machines = [m for m, _ in A.list_machines(meta.binary)]
        cpus = A.list_cpus(meta.binary)
        print(f"  {key:<14} máquinas={len(machines):>4}  cpus={len(cpus):>3}  "
              f"padrão={A.default_machine(meta.binary) or '-'}")

    failures = 0
    for key, meta in sorted(arches.items()):
        cfg = VMConfig(name=f"teste-{key}", arch=key, ram_mb=512, smp=1,
                       display="none", net_mode="none")
        plan = B.build(cfg, meta)
        print(f"\n[{key}] {plan.pretty()}")
        for w in plan.warnings:
            print(f"    aviso: {w}")

    # configuração "completa" para x86_64
    for key in ("x86_64", "i386", "riscv64", "m68k", "avr"):
        if key not in arches:
            continue
        cfg = VMConfig(
            name=f"completa-{key}", arch=key, ram_mb=1024, smp=2,
            disks=[Disk("/tmp/d1.qcow2", "qcow2", "virtio"),
                   Disk("/tmp/d2.qcow2", "qcow2", "scsi"),
                   Disk("/tmp/d3.img", "raw", "ide")],
            isos=["/tmp/instalador.iso"],
            net_mode="user", forwards=[PortForward("tcp", 2222, 22)],
            display="gtk", boot_order="cd", usb_tablet=True, share_path="/tmp",
            extra_args="", snapshot=False,
        )
        plan = B.build(cfg, arches[key])
        print(f"\n[completa:{key}] {plan.pretty()}")
        for w in plan.warnings:
            print(f"    aviso: {w}")
        if not plan.argv or plan.argv[0] != arches[key].binary:
            failures += 1

    print("\nselftest ok" if not failures else f"\nselftest FALHOU ({failures})")
    return 0 if not failures else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    from PyQt6.QtWidgets import QApplication

    from . import arch as A
    from .splash import Splash
    from .theme import apply_dark
    from .ui import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Termux Lab")
    app.setApplicationDisplayName("Termux Lab")
    apply_dark(app)

    splash = Splash(len(A.discover_architectures()), A.kvm_usable())
    app.setQuitOnLastWindowClosed(False)
    splash.show()
    app.processEvents()

    win = MainWindow()

    def reveal() -> None:
        win.show()
        win.raise_()
        win.activateWindow()
        app.setQuitOnLastWindowClosed(True)

    splash.finished.connect(reveal)
    splash.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
