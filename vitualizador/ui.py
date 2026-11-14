"""Janela principal da interface gráfica."""

from __future__ import annotations

import os
import shutil

from PyQt6.QtCore import QProcess, QSettings, Qt, QTimer
from PyQt6.QtGui import QAction, QFont, QKeySequence, QTextCursor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import arch as A
from . import build as B
from . import store
from .model import Disk, PortForward, VMConfig

AUTOMATIC = "automático"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Termux Lab — virtualizador QEMU")
        self.resize(1180, 820)

        self.arches = A.discover_architectures()
        self.current = VMConfig()
        self.current_id: str | None = None
        self._loading = False
        self.proc: QProcess | None = None
        self.plan: B.Plan | None = None
        self._testing = False

        store.ensure_dirs()
        self.settings = QSettings("vitualizador", "vitualizador")
        self._build_ui()
        self._load_vm_list()
        self._install_shortcuts()

        geometry = self.settings.value("geometria")
        if geometry is not None:
            self.restoreGeometry(geometry)
        last = self.settings.value("ultima-vm")
        if last:
            self._select_vm(str(last))
        if self.vm_list.currentRow() < 0:
            if self.vm_list.count():
                self.vm_list.setCurrentRow(0)
            else:
                self.apply_config(self.current)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._build_sidebar())

        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(self._build_tabs())
        right.addWidget(self._build_bottom())
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 2)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 940])
        self.setCentralWidget(splitter)

        self.status_label = QLabel(self._status_text())
        self.statusBar().addWidget(self.status_label)

    def _build_sidebar(self) -> QWidget:
        box = QGroupBox("Minhas máquinas")
        lay = QVBoxLayout(box)

        self.vm_list = QListWidget()
        self.vm_list.currentRowChanged.connect(self._on_vm_selected)
        lay.addWidget(self.vm_list, 1)

        row1 = QHBoxLayout()
        btn_new = QPushButton("Nova")
        btn_dup = QPushButton("Duplicar")
        btn_del = QPushButton("Excluir")
        btn_new.clicked.connect(self.new_vm)
        btn_dup.clicked.connect(self.duplicate_vm)
        btn_del.clicked.connect(self.delete_vm)
        for b in (btn_new, btn_dup, btn_del):
            row1.addWidget(b)
        lay.addLayout(row1)

        btn_save = QPushButton("Salvar configuração")
        btn_save.clicked.connect(self.save_vm)
        lay.addWidget(btn_save)

        run = QHBoxLayout()
        self.btn_start = QPushButton("▶ Iniciar")
        self.btn_start.setObjectName("primario")
        self.btn_start.clicked.connect(self.start_vm)
        self.btn_stop = QPushButton("■ Parar")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_vm)
        run.addWidget(self.btn_start)
        run.addWidget(self.btn_stop)
        lay.addLayout(run)

        missing = A.missing_architectures(self.arches)
        if missing:
            packages = " ".join(sorted({pkg for _arch, pkg in missing}))
            note = QLabel(
                "Não instaladas: " + ", ".join(a for a, _pkg in missing) + "."
            )
            note.setWordWrap(True)
            note.setStyleSheet("color: #6e7681; font-size: 11px;")
            note.setToolTip(f"sudo apt install {packages}")
            lay.addWidget(note)

        return box

    def _build_tabs(self) -> QWidget:
        tabs = QTabWidget()
        tabs.addTab(self._tab_system(), "Sistema")
        tabs.addTab(self._tab_disks(), "Discos e mídia")
        tabs.addTab(self._tab_network(), "Rede")
        tabs.addTab(self._tab_display(), "Vídeo e dispositivos")
        tabs.addTab(self._tab_advanced(), "Avançado")
        return tabs

    def _tab_system(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.in_name = QLineEdit()
        form.addRow("Nome da VM", self.in_name)

        self.in_arch = QComboBox()
        priority = ["x86_64", "i386", "aarch64", "arm", "riscv64", "riscv32",
                    "ppc64le", "ppc64", "s390x", "loongarch64", "m68k"]

        def rank(k: str) -> tuple[int, str]:
            return (priority.index(k) if k in priority else len(priority), k)

        for key in sorted(self.arches, key=rank):
            meta = self.arches[key]
            self.in_arch.addItem(f"{meta.label}  [{key}]", key)
        self.in_arch.currentIndexChanged.connect(self._on_arch_changed)
        self.in_arch.currentIndexChanged.connect(self._changed)
        form.addRow("Arquitetura", self.in_arch)

        self.in_arch_note = QLabel()
        self.in_arch_note.setWordWrap(True)
        self.in_arch_note.setStyleSheet("color: #8b949e; font-size: 11px;")
        form.addRow("", self.in_arch_note)

        self.in_machine = QComboBox()
        self.in_machine.setEditable(True)
        self.in_machine.currentTextChanged.connect(self._changed)
        form.addRow("Máquina (chipset)", self.in_machine)

        self.in_cpu = QComboBox()
        self.in_cpu.setEditable(True)
        self.in_cpu.currentTextChanged.connect(self._changed)
        form.addRow("CPU", self.in_cpu)

        self.in_accel = QComboBox()
        for label, val in (("Automático", "auto"), ("KVM (nativo, rápido)", "kvm"),
                           ("TCG (emulação pura)", "tcg")):
            self.in_accel.addItem(label, val)
        self.in_accel.currentIndexChanged.connect(self._changed)
        form.addRow("Acelerador", self.in_accel)

        row = QHBoxLayout()
        self.in_ram = QSpinBox()
        self.in_ram.setRange(128, 1_048_576)
        self.in_ram.setSingleStep(512)
        self.in_ram.setSuffix(" MB")
        self.in_ram.valueChanged.connect(self._changed)
        self.in_smp = QSpinBox()
        self.in_smp.setRange(1, 256)
        self.in_smp.setSuffix(" vCPU(s)")
        self.in_smp.valueChanged.connect(self._changed)
        row.addWidget(self.in_ram)
        row.addWidget(self.in_smp)
        form.addRow("Memória / processadores", row)

        fw_row = QHBoxLayout()
        self.in_firmware = QComboBox()
        self.in_firmware.addItem("BIOS padrão / automático", "")
        for label, path in A.firmware_candidates():
            self.in_firmware.addItem(label, path)
        self.in_firmware.currentIndexChanged.connect(self._changed)
        btn_fw = QPushButton("…")
        btn_fw.setFixedWidth(32)
        btn_fw.clicked.connect(self._browse_firmware)
        fw_row.addWidget(self.in_firmware, 1)
        fw_row.addWidget(btn_fw)
        form.addRow("Firmware (UEFI/OpenSBI)", fw_row)

        self.in_kernel = self._path_row(form, "Kernel (boot direto)", self._browse_kernel)
        self.in_initrd = self._path_row(form, "Initrd", self._browse_initrd)
        self.in_append = QLineEdit()
        self.in_append.setPlaceholderText("console=ttyS0 root=/dev/vda1 ...")
        self.in_append.textChanged.connect(self._changed)
        form.addRow("Argumentos do kernel", self.in_append)

        self.in_boot = QComboBox()
        for label, val in (("CD / ISO primeiro", "cd"), ("Disco primeiro", "disk"),
                           ("Rede (PXE)", "network")):
            self.in_boot.addItem(label, val)
        self.in_boot.currentIndexChanged.connect(self._changed)
        form.addRow("Ordem de boot", self.in_boot)

        return w

    def _tab_disks(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)

        left = QVBoxLayout()
        left.addWidget(QLabel("Discos"))
        self.disk_list = QListWidget()
        self.disk_list.currentRowChanged.connect(self._on_disk_selected)
        left.addWidget(self.disk_list, 1)
        row = QHBoxLayout()
        for label, slot in (("Criar disco", self.create_disk),
                            ("Anexar disco", self.attach_disk),
                            ("Remover", self.remove_disk)):
            b = QPushButton(label)
            b.clicked.connect(slot)
            row.addWidget(b)
        left.addLayout(row)

        editor = QGroupBox("Detalhes do disco selecionado")
        ef = QFormLayout(editor)
        self.dk_path = QLineEdit()
        self.dk_path.setReadOnly(True)
        ef.addRow("Arquivo", self.dk_path)
        self.dk_fmt = QComboBox()
        for f in ("qcow2", "raw", "vmdk", "vdi", "vpc", "vhdx", "qed"):
            self.dk_fmt.addItem(f)
        self.dk_fmt.currentIndexChanged.connect(self._disk_field_changed)
        ef.addRow("Formato", self.dk_fmt)
        self.dk_iface = QComboBox()
        for label, val in (("VirtIO (recomendado)", "virtio"), ("SCSI (virtio-scsi)", "scsi"),
                           ("IDE (só x86)", "ide"), ("USB", "usb")):
            self.dk_iface.addItem(label, val)
        self.dk_iface.currentIndexChanged.connect(self._disk_field_changed)
        ef.addRow("Interface", self.dk_iface)
        self.dk_size = QLabel("—")
        ef.addRow("Tamanho", self.dk_size)
        self.dk_ro = QCheckBox("Somente leitura")
        self.dk_ro.toggled.connect(self._disk_field_changed)
        ef.addRow("", self.dk_ro)
        left.addWidget(editor)

        right = QVBoxLayout()
        right.addWidget(QLabel("CDs / ISOs (podem ser várias)"))
        self.iso_list = QListWidget()
        right.addWidget(self.iso_list, 1)
        irow = QHBoxLayout()
        b_add = QPushButton("Adicionar ISO")
        b_add.clicked.connect(self.add_iso)
        b_rm = QPushButton("Remover ISO")
        b_rm.clicked.connect(self.remove_iso)
        irow.addWidget(b_add)
        irow.addWidget(b_rm)
        right.addLayout(irow)

        lay.addLayout(left, 1)
        lay.addLayout(right, 1)
        return w

    def _tab_network(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.in_netmode = QComboBox()
        for label, val in (("Sem rede", "none"), ("Usuário / NAT (mais fácil)", "user"),
                           ("Bridge (rede local)", "bridge"), ("TAP (manual)", "tap")):
            self.in_netmode.addItem(label, val)
        self.in_netmode.currentIndexChanged.connect(self._on_netmode_changed)
        self.in_netmode.currentIndexChanged.connect(self._changed)
        form.addRow("Modo", self.in_netmode)

        self.in_netmodel = QComboBox()
        self.in_netmodel.addItem(AUTOMATIC, "")
        for m in ("virtio-net-pci", "e1000", "e1000e", "rtl8139", "virtio-net-device"):
            self.in_netmodel.addItem(m, m)
        self.in_netmodel.currentIndexChanged.connect(self._changed)
        form.addRow("Placa de rede", self.in_netmodel)

        self.in_mac = QLineEdit()
        self.in_mac.setPlaceholderText("52:54:00:12:34:56 (vazio = automático)")
        self.in_mac.textChanged.connect(self._changed)
        form.addRow("MAC", self.in_mac)

        self.in_bridge = QLineEdit("virbr0")
        self.in_bridge.textChanged.connect(self._changed)
        form.addRow("Bridge", self.in_bridge)

        self.in_tap = QLineEdit("tap0")
        self.in_tap.textChanged.connect(self._changed)
        form.addRow("Interface TAP", self.in_tap)

        group = QGroupBox("Encaminhamento de portas (host → convidado)")
        gl = QVBoxLayout(group)
        self.fwd_table = QTableWidget(0, 3)
        self.fwd_table.setHorizontalHeaderLabels(["Protocolo", "Porta host", "Porta convidado"])
        self.fwd_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.fwd_table.verticalHeader().setVisible(False)
        self.fwd_table.itemChanged.connect(self._changed)
        gl.addWidget(self.fwd_table)
        frow = QHBoxLayout()
        b_add = QPushButton("Adicionar regra")
        b_add.clicked.connect(self.add_forward)
        b_rm = QPushButton("Remover regra")
        b_rm.clicked.connect(self.remove_forward)
        frow.addWidget(b_add)
        frow.addWidget(b_rm)
        gl.addLayout(frow)
        form.addRow(group)

        self.in_net_note = QLabel()
        self.in_net_note.setWordWrap(True)
        self.in_net_note.setStyleSheet("color: #8b949e; font-size: 11px;")
        form.addRow("", self.in_net_note)
        return w

    def _tab_display(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.in_display = QComboBox()
        for label, val in (("Janela GTK (janela nativa)", "gtk"), ("Janela SDL", "sdl"),
                           ("VNC (acesso remoto)", "vnc"), ("Sem janela", "none")):
            self.in_display.addItem(label, val)
        self.in_display.currentIndexChanged.connect(self._on_display_changed)
        self.in_display.currentIndexChanged.connect(self._changed)
        form.addRow("Saída de vídeo", self.in_display)

        self.in_vga = QComboBox()
        for label, val in ((AUTOMATIC, ""), ("virtio-gpu (moderno)", "virtio"),
                           ("VGA padrão", "std"), ("QXL (SPICE)", "qxl"),
                           ("Cirrus (antigo)", "cirrus"), ("Sem placa de vídeo", "none")):
            self.in_vga.addItem(label, val)
        self.in_vga.currentIndexChanged.connect(self._changed)
        form.addRow("Placa de vídeo", self.in_vga)

        self.in_vnc = QLineEdit(":0")
        self.in_vnc.textChanged.connect(self._changed)
        form.addRow("Endereço VNC", self.in_vnc)

        row = QHBoxLayout()
        self.chk_serial = QCheckBox("Console serial (nographic)")
        self.chk_usb = QCheckBox("Tablet USB (mouse absoluto)")
        self.chk_audio = QCheckBox("Áudio (x86)")
        for c in (self.chk_serial, self.chk_usb, self.chk_audio):
            c.toggled.connect(self._changed)
            row.addWidget(c)
        form.addRow("Extras", row)

        row2 = QHBoxLayout()
        self.chk_snapshot = QCheckBox("Modo snapshot (descartar alterações)")
        self.chk_rtc = QCheckBox("Relógio local")
        self.chk_menu = QCheckBox("Menu de boot")
        for c in (self.chk_snapshot, self.chk_rtc, self.chk_menu):
            c.toggled.connect(self._changed)
            row2.addWidget(c)
        form.addRow("", row2)

        self.in_share = self._path_row(form, "Pasta compartilhada (9p)", self._browse_share)
        self.in_share_tag = QLineEdit("hostshare")
        self.in_share_tag.textChanged.connect(self._changed)
        form.addRow("Tag do compartilhamento", self.in_share_tag)

        note = QLabel("Dentro do convidado Linux: mount -t 9p -o trans=virtio hostshare /mnt")
        note.setStyleSheet("color: #8b949e; font-size: 11px;")
        form.addRow("", note)
        return w

    def _tab_advanced(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Argumentos adicionais do QEMU (repassados sem alteração):"))
        self.in_extra = QPlainTextEdit()
        self.in_extra.setPlaceholderText("-device usb-host,vendorid=0x1234,productid=0x5678")
        self.in_extra.setMaximumHeight(120)
        self.in_extra.textChanged.connect(self._changed)
        lay.addWidget(self.in_extra)

        help_box = QGroupBox("Referência rápida")
        hl = QVBoxLayout(help_box)
        text = QLabel(
            "• Disco VirtIO é o mais rápido; IDE só existe em máquinas x86.\n"
            "• ARM64/RISC-V normalmente precisam de firmware UEFI para bootar ISO.\n"
            "• KVM só acelera a arquitetura nativa do seu computador; o resto roda em TCG.\n"
            "• Boot direto de kernel: informe kernel + initrd + argumentos (dispensa firmware).\n"
            "• O comando final aparece abaixo, sempre atualizado — copie para usar no terminal."
        )
        text.setWordWrap(True)
        hl.addWidget(text)
        lay.addWidget(help_box)
        lay.addStretch(1)
        return w

    def _build_bottom(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)

        head = QHBoxLayout()
        head.addWidget(QLabel("<b>Comando QEMU</b>"))
        head.addStretch(1)
        self.btn_copy = QPushButton("Copiar")
        self.btn_copy.clicked.connect(self.copy_command)
        self.btn_test = QPushButton("Testar (2 s)")
        self.btn_test.setToolTip("Sobe a VM sem tela por 2 segundos para conferir a configuração.")
        self.btn_test.clicked.connect(self.test_config)
        head.addWidget(self.btn_copy)
        head.addWidget(self.btn_test)
        lay.addLayout(head)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.preview.setMaximumHeight(110)
        font = QFont("monospace")
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        font.setPointSize(9)
        self.preview.setFont(font)
        lay.addWidget(self.preview)

        self.warn_label = QLabel()
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet("color: #f0883e;")
        lay.addWidget(self.warn_label)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(font)
        self.log.document().setMaximumBlockCount(4000)
        self.log.setPlaceholderText("Saída do QEMU aparece aqui.")
        lay.addWidget(self.log, 1)

        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText(
            "Console serial: digite aqui e pressione Enter (a VM precisa estar rodando "
            "com 'Console serial' ligado)")
        self.serial_input.returnPressed.connect(self._send_serial)
        self.serial_input.setVisible(False)
        lay.addWidget(self.serial_input)
        return w

    # --------------------------------------------------------------- helpers

    def _path_row(self, form: QFormLayout, label: str, slot) -> QLineEdit:
        row = QHBoxLayout()
        edit = QLineEdit()
        edit.textChanged.connect(self._changed)
        btn = QPushButton("…")
        btn.setFixedWidth(32)
        btn.clicked.connect(slot)
        row.addWidget(edit, 1)
        row.addWidget(btn)
        form.addRow(label, row)
        return edit

    def _install_shortcuts(self) -> None:
        for seq, slot in (("Ctrl+N", self.new_vm), ("Ctrl+S", self.save_vm),
                          ("F5", self.start_vm), ("Shift+F5", self.stop_vm)):
            act = QAction(self)
            act.setShortcut(QKeySequence(seq))
            act.triggered.connect(slot)
            self.addAction(act)

    def _status_text(self) -> str:
        n = len(self.arches)
        return f"{n} arquiteturas detectadas · KVM {'disponível' if A.kvm_usable() else 'indisponível'}"

    # ------------------------------------------------------------- arquitetura

    @property
    def meta(self) -> A.ArchMeta:
        return self.arches.get(self.in_arch.currentData() or "x86_64",
                               next(iter(self.arches.values())))

    def _on_arch_changed(self) -> None:
        meta = self.meta
        self.in_arch_note.setText(meta.notes)

        self.in_machine.blockSignals(True)
        self.in_machine.clear()
        self.in_machine.addItem(AUTOMATIC, "")
        for name, desc in A.list_machines(meta.binary):
            self.in_machine.addItem(f"{name} — {desc}", name)
        self.in_machine.setCurrentIndex(0)
        self.in_machine.blockSignals(False)
        self.in_machine.setEditable(True)

        self.in_cpu.blockSignals(True)
        self.in_cpu.clear()
        self.in_cpu.addItem(AUTOMATIC, "")
        for cpu in A.list_cpus(meta.binary):
            self.in_cpu.addItem(cpu, cpu)
        self.in_cpu.setCurrentIndex(0)
        self.in_cpu.blockSignals(False)
        self.in_cpu.setEditable(True)

        if not self._loading:
            self._changed()

    # ------------------------------------------------------------- config I/O

    def apply_config(self, cfg: VMConfig) -> None:
        self._loading = True
        try:
            self.current = cfg
            if cfg.arch not in self.arches and self.in_arch.count():
                cfg.arch = self.in_arch.itemData(0)

            idx = self.in_arch.findData(cfg.arch)
            self.in_arch.setCurrentIndex(max(0, idx))
            self._on_arch_changed()

            self.in_name.setText(cfg.name)
            self._set_combo_text(self.in_machine, cfg.machine)
            self._set_combo_text(self.in_cpu, cfg.cpu)
            self._set_combo(self.in_accel, cfg.accel)
            self.in_ram.setValue(cfg.ram_mb)
            self.in_smp.setValue(cfg.smp)

            fw_idx = self.in_firmware.findData(cfg.firmware)
            if fw_idx < 0 and cfg.firmware:
                self.in_firmware.addItem(f"Personalizado: {cfg.firmware}", cfg.firmware)
                fw_idx = self.in_firmware.count() - 1
            self.in_firmware.setCurrentIndex(max(0, fw_idx))

            self.in_kernel.setText(cfg.kernel)
            self.in_initrd.setText(cfg.initrd)
            self.in_append.setText(cfg.append)
            self._set_combo(self.in_boot, cfg.boot_order)

            self._refresh_disk_list()
            self._refresh_iso_list()

            self._set_combo(self.in_netmode, cfg.net_mode)
            self._set_combo(self.in_netmodel, cfg.net_model)
            self.in_mac.setText(cfg.mac)
            self.in_bridge.setText(cfg.bridge)
            self.in_tap.setText(cfg.tap)
            self._refresh_forwards()
            self._on_netmode_changed()

            self._set_combo(self.in_display, cfg.display)
            self._set_combo(self.in_vga, cfg.vga)
            self.in_vnc.setText(cfg.vnc_display)
            self.chk_serial.setChecked(cfg.serial_console)
            self.chk_usb.setChecked(cfg.usb_tablet)
            self.chk_audio.setChecked(cfg.audio)
            self.chk_snapshot.setChecked(cfg.snapshot)
            self.chk_rtc.setChecked(cfg.rtc_localtime)
            self.chk_menu.setChecked(cfg.show_menu)
            self.in_share.setText(cfg.share_path)
            self.in_share_tag.setText(cfg.share_tag)
            self.in_extra.setPlainText(cfg.extra_args)
            self._on_display_changed()
            self._refresh_preview()
        finally:
            self._loading = False

    def collect(self) -> VMConfig:
        cfg = self.current
        cfg.name = self.in_name.text().strip() or "Nova VM"
        cfg.arch = self.in_arch.currentData() or "x86_64"
        cfg.machine = self._combo_text(self.in_machine)
        cfg.cpu = self._combo_text(self.in_cpu)
        cfg.accel = self.in_accel.currentData() or "auto"
        cfg.ram_mb = self.in_ram.value()
        cfg.smp = self.in_smp.value()
        cfg.firmware = self.in_firmware.currentData() or ""
        cfg.kernel = self.in_kernel.text().strip()
        cfg.initrd = self.in_initrd.text().strip()
        cfg.append = self.in_append.text().strip()
        cfg.boot_order = self.in_boot.currentData() or "cd"

        cfg.net_mode = self.in_netmode.currentData() or "user"
        cfg.net_model = self.in_netmodel.currentData() or ""
        cfg.mac = self.in_mac.text().strip()
        cfg.bridge = self.in_bridge.text().strip()
        cfg.tap = self.in_tap.text().strip()
        cfg.forwards = self._read_forwards()

        cfg.display = self.in_display.currentData() or "gtk"
        cfg.vga = self.in_vga.currentData() or ""
        cfg.vnc_display = self.in_vnc.text().strip()
        cfg.serial_console = self.chk_serial.isChecked()
        cfg.usb_tablet = self.chk_usb.isChecked()
        cfg.audio = self.chk_audio.isChecked()
        cfg.snapshot = self.chk_snapshot.isChecked()
        cfg.rtc_localtime = self.chk_rtc.isChecked()
        cfg.show_menu = self.chk_menu.isChecked()
        cfg.share_path = self.in_share.text().strip()
        cfg.share_tag = self.in_share_tag.text().strip() or "hostshare"
        cfg.extra_args = self.in_extra.toPlainText().strip()
        return cfg

    def _changed(self, *_args) -> None:
        if self._loading:
            return
        self.collect()
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        meta = self.meta
        self.plan = B.build(self.current, meta)
        self.preview.setPlainText(self.plan.pretty())
        if self.plan.warnings:
            self.warn_label.setText("⚠ " + "\n⚠ ".join(self.plan.warnings))
        else:
            self.warn_label.setText("")

    # --------------------------------------------------------------- combo IO

    @staticmethod
    def _set_combo(combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    @staticmethod
    def _set_combo_text(combo: QComboBox, value: str) -> None:
        if not value:
            combo.setCurrentIndex(0)
            return
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setEditText(value)

    @staticmethod
    def _combo_text(combo: QComboBox) -> str:
        """Valor efetivo do combo, respeitando texto digitado à mão."""
        text = combo.currentText().strip()
        idx = combo.currentIndex()
        edited = idx >= 0 and combo.itemText(idx).strip() != text
        data = combo.currentData()
        if data and not edited:
            return data
        if not text or text.startswith(AUTOMATIC):
            return ""
        return text

    # ------------------------------------------------------------------ VMs

    def _load_vm_list(self) -> None:
        self.vm_list.blockSignals(True)
        self.vm_list.clear()
        for slug_id, name in store.list_vms():
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, slug_id)
            self.vm_list.addItem(item)
        self.vm_list.blockSignals(False)

    def _on_vm_selected(self, row: int) -> None:
        item = self.vm_list.item(row)
        if item is None:
            return
        slug_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            cfg = store.load(slug_id)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Erro", f"Não foi possível abrir a VM:\n{exc}")
            return
        self.current_id = slug_id
        self.apply_config(cfg)
        self.settings.setValue("ultima-vm", slug_id)

    def new_vm(self) -> None:
        name, ok = QInputDialog.getText(self, "Nova máquina", "Nome da VM:")
        if not ok or not name.strip():
            return
        cfg = VMConfig(name=name.strip())
        self.current_id = store.save(cfg)
        self._load_vm_list()
        self._select_vm(self.current_id)
        self.apply_config(cfg)

    def duplicate_vm(self) -> None:
        if self.current_id is None:
            return
        name, ok = QInputDialog.getText(self, "Duplicar", "Nome da nova VM:",
                                        text=f"{self.collect().name} (cópia)")
        if not ok or not name.strip():
            return
        cfg = self.collect().clone(name.strip())
        self.current_id = store.save(cfg)
        self._load_vm_list()
        self._select_vm(self.current_id)
        self.apply_config(cfg)

    def delete_vm(self) -> None:
        if self.current_id is None:
            return
        name = self.collect().name
        if QMessageBox.question(self, "Excluir",
                                f"Excluir a configuração de “{name}”?\n"
                                "Os arquivos de disco não serão apagados.") != QMessageBox.StandardButton.Yes:
            return
        store.delete(self.current_id)
        self.current_id = None
        self._load_vm_list()
        if self.vm_list.count():
            self.vm_list.setCurrentRow(0)
        else:
            self.current = VMConfig()
            self.apply_config(self.current)

    def save_vm(self) -> None:
        cfg = self.collect()
        self.current_id = store.save(cfg)
        self._load_vm_list()
        self._select_vm(self.current_id)
        self.statusBar().showMessage(f"Salvo: {cfg.name}", 2500)

    def _select_vm(self, slug_id: str | None) -> None:
        for i in range(self.vm_list.count()):
            if self.vm_list.item(i).data(Qt.ItemDataRole.UserRole) == slug_id:
                self.vm_list.setCurrentRow(i)
                return

    # ---------------------------------------------------------------- discos

    def _refresh_disk_list(self) -> None:
        self.disk_list.blockSignals(True)
        self.disk_list.clear()
        for d in self.current.disks:
            text = f"{os.path.basename(d.path)} · {d.fmt} · {d.interface}"
            if d.readonly:
                text += " · RO"
            self.disk_list.addItem(text)
        self.disk_list.blockSignals(False)
        if self.current.disks:
            self.disk_list.setCurrentRow(0)
        else:
            self._on_disk_selected(-1)

    def _on_disk_selected(self, row: int) -> None:
        has = 0 <= row < len(self.current.disks)
        for w in (self.dk_fmt, self.dk_iface, self.dk_ro):
            w.setEnabled(has)
        if not has:
            self.dk_path.setText("")
            self.dk_size.setText("—")
            return
        d = self.current.disks[row]
        prev = self._loading
        self._loading = True
        self.dk_path.setText(d.path)
        idx = self.dk_fmt.findText(d.fmt)
        self.dk_fmt.setCurrentIndex(idx if idx >= 0 else 0)
        self._set_combo(self.dk_iface, d.interface)
        self.dk_ro.setChecked(d.readonly)
        self._loading = prev
        info = store.disk_info(d.path) if os.path.exists(d.path) else {}
        self.dk_size.setText(info.get("virtual", "—"))

    def _disk_field_changed(self, *_args) -> None:
        if self._loading:
            return
        row = self.disk_list.currentRow()
        if not (0 <= row < len(self.current.disks)):
            return
        d = self.current.disks[row]
        d.fmt = self.dk_fmt.currentText() or "qcow2"
        d.interface = self.dk_iface.currentData() or "virtio"
        d.readonly = self.dk_ro.isChecked()
        self._refresh_disk_list()
        self.disk_list.setCurrentRow(row)
        self._changed()

    def create_disk(self) -> None:
        store.ensure_dirs()
        default = str(store.DISK_DIR / f"{store.slug(self.collect().name)}-{len(self.current.disks)}.qcow2")
        path, _ = QFileDialog.getSaveFileName(
            self, "Criar disco", default,
            "QCOW2 (*.qcow2);;RAW (*.raw *.img);;Todos (*)")
        if not path:
            return
        fmt = "qcow2" if path.endswith(".qcow2") else ("raw" if path.endswith((".raw", ".img")) else "qcow2")
        size, ok = QInputDialog.getInt(self, "Tamanho", "Tamanho do disco (GB):", 20, 1, 8192)
        if not ok:
            return
        if os.path.exists(path) and QMessageBox.question(
                self, "Sobrescrever", "O arquivo já existe. Sobrescrever?") != QMessageBox.StandardButton.Yes:
            return
        try:
            out = store.create_disk(path, size, fmt)
        except RuntimeError as exc:
            QMessageBox.critical(self, "qemu-img", str(exc))
            return
        self.log.appendPlainText(f"$ {out}")
        self.current.disks.append(Disk(path=path, fmt=fmt, size_gb=size))
        self._refresh_disk_list()
        self.disk_list.setCurrentRow(len(self.current.disks) - 1)
        self._changed()

    def attach_disk(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Anexar disco", str(store.DISK_DIR),
            "Imagens (*.qcow2 *.raw *.img *.vmdk *.vdi *.vhd *.vhdx);;Todos (*)")
        if not path:
            return
        info = store.disk_info(path)
        fmt = info.get("format", "qcow2")
        self.current.disks.append(Disk(path=path, fmt=fmt))
        self._refresh_disk_list()
        self.disk_list.setCurrentRow(len(self.current.disks) - 1)
        self._changed()

    def remove_disk(self) -> None:
        row = self.disk_list.currentRow()
        if 0 <= row < len(self.current.disks):
            del self.current.disks[row]
            self._refresh_disk_list()
            self._changed()

    def _refresh_iso_list(self) -> None:
        self.iso_list.clear()
        for iso in self.current.isos:
            item = QListWidgetItem(iso)
            item.setData(Qt.ItemDataRole.UserRole, iso)
            self.iso_list.addItem(item)

    def add_iso(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Adicionar ISO", str(store.DISK_DIR),
            "Imagens ISO (*.iso *.img *.raw);;Todos (*)")
        if not paths:
            return
        self.current.isos.extend(paths)
        self._refresh_iso_list()
        self._changed()

    def remove_iso(self) -> None:
        row = self.iso_list.currentRow()
        if 0 <= row < len(self.current.isos):
            del self.current.isos[row]
            self._refresh_iso_list()
            self._changed()

    # ------------------------------------------------------------------ rede

    def _refresh_forwards(self) -> None:
        self.fwd_table.blockSignals(True)
        self.fwd_table.setRowCount(len(self.current.forwards))
        for i, fwd in enumerate(self.current.forwards):
            self.fwd_table.setItem(i, 0, QTableWidgetItem(fwd.proto))
            self.fwd_table.setItem(i, 1, QTableWidgetItem(str(fwd.host)))
            self.fwd_table.setItem(i, 2, QTableWidgetItem(str(fwd.guest)))
        self.fwd_table.blockSignals(False)

    def _read_forwards(self) -> list[PortForward]:
        result: list[PortForward] = []
        for i in range(self.fwd_table.rowCount()):
            def cell(col: int) -> str:
                item = self.fwd_table.item(i, col)
                return item.text().strip() if item else ""
            try:
                result.append(PortForward(cell(0) or "tcp", int(cell(1) or 0), int(cell(2) or 0)))
            except ValueError:
                continue
        return result

    def add_forward(self) -> None:
        self.collect()
        self.current.forwards.append(PortForward("tcp", 2222, 22))
        self._refresh_forwards()
        self._changed()

    def remove_forward(self) -> None:
        row = self.fwd_table.currentRow()
        if row >= 0:
            self.current.forwards.pop(row)
            self._refresh_forwards()
            self._changed()

    def _on_netmode_changed(self) -> None:
        mode = self.in_netmode.currentData()
        self.in_bridge.setEnabled(mode == "bridge")
        self.in_tap.setEnabled(mode == "tap")
        self.fwd_table.setEnabled(mode == "user")
        if mode == "user":
            self.in_net_note.setText(
                "NAT: o convidado acessa a internet; para acessá-lo use uma regra de porta "
                "(ex.: host 2222 → convidado 22).")
        elif mode == "bridge":
            self.in_net_note.setText(
                "Precisa de uma bridge existente (ex.: criada com ip link / brctl) e "
                "do binário qemu-bridge-helper com permissão.")
        elif mode == "tap":
            self.in_net_note.setText(
                "Cria um TAP pré-existente no host. Configure IP/rotas manualmente.")
        else:
            self.in_net_note.setText("Sem rede.")

    def _on_display_changed(self) -> None:
        self.in_vnc.setEnabled(self.in_display.currentData() == "vnc")

    # ----------------------------------------------------------------- ações

    def copy_command(self) -> None:
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.preview.toPlainText())
        self.statusBar().showMessage("Comando copiado.", 2000)

    def _browse_firmware(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Firmware", "/usr/share",
                                              "Firmware (*.fd *.bin *.img *.rom);;Todos (*)")
        if path:
            self.in_firmware.addItem(f"Personalizado: {os.path.basename(path)}", path)
            self.in_firmware.setCurrentIndex(self.in_firmware.count() - 1)

    def _pick_path(self) -> str:
        path, _ = QFileDialog.getOpenFileName(
            self, "Arquivo", str(store.DISK_DIR),
            "Todos (*);;Kernel (*vmlinuz* bzImage* Image*)")
        return path

    def _browse_kernel(self) -> None:
        p = self._pick_path()
        if p:
            self.in_kernel.setText(p)

    def _browse_initrd(self) -> None:
        p = self._pick_path()
        if p:
            self.in_initrd.setText(p)

    def _browse_share(self) -> None:
        p = QFileDialog.getExistingDirectory(self, "Pasta compartilhada", str(store.DISK_DIR))
        if p:
            self.in_share.setText(p)

    # -------------------------------------------------------------- executar

    def _validate(self) -> bool:
        cfg = self.collect()
        if not cfg.name.strip():
            QMessageBox.warning(self, "Configuração", "Dê um nome à VM.")
            return False
        if shutil.which(self.meta.binary) is None:
            QMessageBox.critical(self, "Arquitetura",
                                 f"Binário QEMU não encontrado: {self.meta.binary}")
            return False
        return True

    def start_vm(self) -> None:
        if self.proc is not None:
            return
        if not self._validate():
            return
        self.save_vm()
        self._refresh_preview()
        argv = self.plan.argv if self.plan else B.build(self.collect(), self.meta).argv
        self.log.appendPlainText(f"$ {argv[0]} ...\n{self.preview.toPlainText()}\n")
        self._launch(argv, test=False)

    def test_config(self) -> None:
        if self.proc is not None:
            return
        if not self._validate():
            return
        argv = list(self.plan.argv) + ["-display", "none", "-S"]
        self.log.appendPlainText("— teste de configuração (2 s) —")
        self._launch(argv, test=True)

    def _send_serial(self) -> None:
        if self.proc is None:
            return
        text = self.serial_input.text()
        self.serial_input.clear()
        self.proc.write((text + "\n").encode())
        self.log.appendPlainText(f"> {text}")

    def _launch(self, argv: list[str], test: bool) -> None:
        proc = QProcess(self)
        proc.setProgram(argv[0])
        proc.setArguments(argv[1:])
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(lambda: self._drain(proc))
        proc.readyReadStandardError.connect(lambda: self._drain(proc))
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)
        self.proc = proc
        self._testing = test
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.statusBar().showMessage("Testando configuração…" if test else "VM em execução")
        proc.start()
        self.serial_input.setVisible(bool(self.collect().serial_console) and not test)
        if test:
            QTimer.singleShot(2500, lambda: self._stop_proc(force=True))

    def _drain(self, proc: QProcess) -> None:
        data = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        if data:
            self.log.moveCursor(QTextCursor.MoveOperation.End)
            self.log.insertPlainText(data)

    def stop_vm(self) -> None:
        self._stop_proc(force=False)

    def _stop_proc(self, force: bool) -> None:
        if self.proc is None:
            return
        proc = self.proc
        if force:
            proc.kill()
        else:
            proc.terminate()
            QTimer.singleShot(3000, lambda: proc.kill() if proc.state() !=
                              QProcess.ProcessState.NotRunning else None)

    def _on_finished(self, code: int, _status) -> None:
        was_test = self._testing
        self.proc = None
        self._testing = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.serial_input.setVisible(False)
        self.statusBar().showMessage(f"QEMU encerrado (código {code})")
        self.log.appendPlainText(f"— QEMU encerrado com código {code} —")
        if was_test:
            text = self.log.toPlainText().splitlines()[-40:]
            bad = [ln for ln in text if "error" in ln.lower() or "invalid" in ln.lower()]
            if bad:
                QMessageBox.warning(self, "Teste",
                                    "O QEMU reportou problemas:\n\n" + "\n".join(bad[:5]))
            else:
                QMessageBox.information(self, "Teste",
                                        "Configuração aceita: nenhum erro imediato do QEMU.")

    def _on_error(self, err) -> None:
        self.log.appendPlainText(f"— erro ao executar: {err} —")
        self.proc = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.serial_input.setVisible(False)

    # ---------------------------------------------------------------- fechar

    def closeEvent(self, event) -> None:
        if self.proc is not None:
            if QMessageBox.question(self, "Sair", "A VM está rodando. Encerrar mesmo assim?"
                                    ) != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.proc.kill()
            self.proc.waitForFinished(2000)
        if self.current_id is not None:
            try:
                store.save(self.collect())
            except OSError:
                pass
        self.settings.setValue("geometria", self.saveGeometry())
        event.accept()
