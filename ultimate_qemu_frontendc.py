import sys
import os
import subprocess
import json
import requests
import threading
import shutil
import platform
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QFileDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QSpinBox, QComboBox, QTextEdit, QMessageBox, QListWidget,
    QInputDialog, QProgressBar, QCheckBox, QGroupBox, QMenuBar, QAction
)
from PyQt5.QtCore import Qt, QTimer

# ===== App Info & Changelog =====
APP_VERSION = "v1.0"
APP_AUTHOR = "Daniel Kaiser"
APP_CONTACT = "daniel.kaiser.dev@gmail.com"
APP_WEBSITE = ""
CHANGELOG = """
- v1.0 Initial public release
- Profiles, ISO download/library, USB passthrough, OVMF/UEFI, network UI, snapshots
- QEMU/ISO update checker, hot plug ISOs, and more!
- About box & changelog bar added
"""

try:
    import usb.core
    import usb.util
    pyusb_available = True
except ImportError:
    pyusb_available = False

CONFIG_FILE = "ultimate_qemu_profiles.json"

ISO_LIST = [
    {
        "name": "Ubuntu 24.04 LTS Desktop",
        "url": "https://releases.ubuntu.com/24.04/ubuntu-24.04-desktop-amd64.iso",
        "filename": "ubuntu-24.04-desktop-amd64.iso"
    },
    {
        "name": "Fedora Workstation 40",
        "url": "https://download.fedoraproject.org/pub/fedora/linux/releases/40/Workstation/x86_64/iso/Fedora-Workstation-Live-x86_64-40-1.14.iso",
        "filename": "Fedora-Workstation-Live-x86_64-40-1.14.iso"
    },
    {
        "name": "Debian 12.5.0 netinst",
        "url": "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.5.0-amd64-netinst.iso",
        "filename": "debian-12.5.0-amd64-netinst.iso"
    },
    {
        "name": "Windows 11 (Eval, English, x64)",
        "url": "https://software-download.microsoft.com/download/pr/22621.1.220506-1250.ni_release_CLIENT_CONSUMER_x64FRE_en-us.iso",
        "filename": "Win11_English_x64.iso"
    }
]

QEMU_WIN_URL = "https://qemu.weilnetz.de/w64/"
UBUNTU_URL = "https://releases.ubuntu.com/"
FEDORA_URL = "https://getfedora.org/en/workstation/download/"
DEBIAN_URL = "https://www.debian.org/CD/http-ftp/"

class QemuProfile:
    def __init__(self, name="Default VM"):
        self.name = name
        self.qemu_path = ""
        self.arch = "x86_64"
        self.iso = ""
        self.disk = ""
        self.ram = 2048
        self.cpus = 2
        self.boot = "ISO (cdrom)"
        self.extra = ""
        self.network_mode = "user"
        self.network_options = ""
        self.usb_devices = []
        self.ovmf_enabled = False
        self.ovmf_path = ""
        self.snapshots = []
        self.secondary_isos = []
        self.iso_library_dir = ""
    def to_dict(self):
        return self.__dict__
    @staticmethod
    def from_dict(d):
        p = QemuProfile()
        p.__dict__.update(d)
        if not hasattr(p, "usb_devices"):
            p.usb_devices = []
        if not hasattr(p, "snapshots"):
            p.snapshots = []
        if not hasattr(p, "secondary_isos"):
            p.secondary_isos = []
        if not hasattr(p, "iso_library_dir"):
            p.iso_library_dir = ""
        return p
class UltimateQemuFrontend(QWidget):
    def __init__(self):
        super().__init__()

        # --- Menu Bar with About ---
        menubar = QMenuBar(self)
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about_dialog)
        menubar.addAction(about_action)

        self.setWindowTitle("Ultimate QEMU Frontend")
        self.setMinimumSize(920, 650)
        self.layout = QHBoxLayout()
        self.profile_list = QListWidget()
        self.profile_list.setMaximumWidth(220)
        self.profile_list_label = QLabel("VM Profiles")
        self.profile_list_label.setAlignment(Qt.AlignCenter)
        self.profile_layout = QVBoxLayout()
        self.profile_layout.addWidget(self.profile_list_label)
        self.profile_layout.addWidget(self.profile_list)
        self.new_profile_btn = QPushButton("New Profile")
        self.delete_profile_btn = QPushButton("Delete Profile")
        self.profile_layout.addWidget(self.new_profile_btn)
        self.profile_layout.addWidget(self.delete_profile_btn)
        self.layout.addLayout(self.profile_layout)
        self.right_layout = QVBoxLayout()
        self.fields = {}
        self.add_form_field("VM Name", QLineEdit, "Name of this VM profile", "Default VM")
        self.add_form_field("QEMU Executable", QLineEdit, "Path to qemu-system-ARCH.exe", "")
        self.browse_qemu_btn = QPushButton("Browse QEMU")
        self.browse_qemu_btn.clicked.connect(self.browse_qemu)
        self.add_form_field("Architecture", QComboBox, "Emulated CPU architecture", "x86_64")
        self.fields["Architecture"].addItems(["x86_64", "i386", "aarch64", "arm", "ppc", "mips", "riscv64"])
        self.add_form_field("ISO Image", QLineEdit, "Bootable ISO file", "")
        self.browse_iso_btn = QPushButton("Browse ISO")
        self.browse_iso_btn.clicked.connect(self.browse_iso)
        self.download_iso_btn = QPushButton("Download ISO")
        self.download_iso_btn.clicked.connect(self.download_iso_dialog)
        self.add_form_field("Disk Image", QLineEdit, "Hard disk file", "")
        self.browse_disk_btn = QPushButton("Browse Disk")
        self.browse_disk_btn.clicked.connect(self.browse_disk)
        self.create_disk_btn = QPushButton("Create Disk")
        self.create_disk_btn.clicked.connect(self.create_disk)
        self.add_form_field("RAM (MB)", QSpinBox, "Memory for VM", 2048)
        self.fields["RAM (MB)"].setRange(128, 131072)
        self.add_form_field("CPUs", QSpinBox, "CPU Cores", 2)
        self.fields["CPUs"].setRange(1, 64)
        self.add_form_field("Boot Device", QComboBox, "Where to boot from", "ISO (cdrom)")
        self.fields["Boot Device"].addItems(["ISO (cdrom)", "Disk image"])
        self.add_form_field("Extra QEMU Options", QLineEdit, "Other QEMU CLI options", "")
        self.ovmf_checkbox = QCheckBox("Enable UEFI/OVMF")
        self.ovmf_checkbox.stateChanged.connect(self.ovmf_toggled)
        self.ovmf_path_input = QLineEdit("")
        self.ovmf_path_input.setPlaceholderText("OVMF/UEFI firmware file (OVMF_CODE.fd)")
        self.browse_ovmf_btn = QPushButton("Browse OVMF")
        self.browse_ovmf_btn.clicked.connect(self.browse_ovmf)
        self.network_group = QGroupBox("Network Settings")
        self.network_layout = QHBoxLayout()
        self.network_mode_combo = QComboBox()
        self.network_mode_combo.addItems(["user (NAT)", "bridged (TAP)", "custom"])
        self.network_mode_combo.setToolTip("User = NAT (default), bridged = needs TAP setup, custom = enter manually")
        self.network_options_input = QLineEdit()
        self.network_options_input.setPlaceholderText("e.g. -net user,hostfwd=tcp::2222-:22")
        self.network_layout.addWidget(self.network_mode_combo)
        self.network_layout.addWidget(self.network_options_input)
        self.network_group.setLayout(self.network_layout)
        self.usb_group = QGroupBox("USB Passthrough (attach host devices)")
        self.usb_layout = QVBoxLayout()
        self.usb_checkboxes = []
        self.refresh_usb_btn = QPushButton("Refresh USB List")
        self.refresh_usb_btn.clicked.connect(self.refresh_usb_list)
        self.usb_layout.addWidget(self.refresh_usb_btn)
        self.usb_group.setLayout(self.usb_layout)
        self.iso_library_group = QGroupBox("ISO Library")
        self.iso_library_layout = QVBoxLayout()
        self.iso_library_dir_btn = QPushButton("Choose ISO Library Folder")
        self.iso_library_dir_btn.clicked.connect(self.choose_iso_library_dir)
        self.iso_library_list = QListWidget()
        self.iso_library_list.itemDoubleClicked.connect(self.select_iso_from_library)
        self.iso_library_layout.addWidget(self.iso_library_dir_btn)
        self.iso_library_layout.addWidget(self.iso_library_list)
        self.iso_library_group.setLayout(self.iso_library_layout)
        self.snapshot_group = QGroupBox("Snapshots")
        self.snapshot_layout = QHBoxLayout()
        self.snapshot_list_btn = QPushButton("List")
        self.snapshot_list_btn.clicked.connect(self.list_snapshots)
        self.snapshot_create_btn = QPushButton("Create")
        self.snapshot_create_btn.clicked.connect(self.create_snapshot)
        self.snapshot_revert_btn = QPushButton("Revert")
        self.snapshot_revert_btn.clicked.connect(self.revert_snapshot)
        self.snapshot_delete_btn = QPushButton("Delete")
        self.snapshot_delete_btn.clicked.connect(self.delete_snapshot)
        self.snapshot_name_input = QLineEdit()
        self.snapshot_name_input.setPlaceholderText("Snapshot name")
        self.snapshot_layout.addWidget(self.snapshot_list_btn)
        self.snapshot_layout.addWidget(self.snapshot_create_btn)
        self.snapshot_layout.addWidget(self.snapshot_revert_btn)
        self.snapshot_layout.addWidget(self.snapshot_delete_btn)
        self.snapshot_layout.addWidget(self.snapshot_name_input)
        self.snapshot_group.setLayout(self.snapshot_layout)
        self.hotplug_group = QGroupBox("Hot Attach/Detach Drives/ISOs")
        self.hotplug_layout = QVBoxLayout()
        self.attach_iso_btn = QPushButton("Attach ISO as CD-ROM")
        self.attach_iso_btn.clicked.connect(self.hot_attach_iso)
        self.detach_iso_btn = QPushButton("Eject CD-ROM")
        self.detach_iso_btn.clicked.connect(self.hot_detach_iso)
        self.hotplug_layout.addWidget(self.attach_iso_btn)
        self.hotplug_layout.addWidget(self.detach_iso_btn)
        self.hotplug_group.setLayout(self.hotplug_layout)
        self.check_update_btn = QPushButton("Check for QEMU/ISO Updates")
        self.check_update_btn.clicked.connect(self.check_updates)
        self.start_btn = QPushButton("Start VM")
        self.stop_btn = QPushButton("Stop All VMs")
        self.save_profile_btn = QPushButton("Save Profile")
        h_btns = QHBoxLayout()
        h_btns.addWidget(self.start_btn)
        h_btns.addWidget(self.stop_btn)
        h_btns.addWidget(self.save_profile_btn)
        h_btns.addWidget(self.check_update_btn)
        self.output_label = QLabel("Output Log:")
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.right_layout.addWidget(QLabel("VM Name:"))
        self.right_layout.addWidget(self.fields["VM Name"])
        self.right_layout.addWidget(QLabel("QEMU Executable:"))
        h_qemu = QHBoxLayout()
        h_qemu.addWidget(self.fields["QEMU Executable"])
        h_qemu.addWidget(self.browse_qemu_btn)
        self.right_layout.addLayout(h_qemu)
        self.right_layout.addWidget(QLabel("Architecture:"))
        self.right_layout.addWidget(self.fields["Architecture"])
        self.right_layout.addWidget(QLabel("ISO Image:"))
        h_iso = QHBoxLayout()
        h_iso.addWidget(self.fields["ISO Image"])
        h_iso.addWidget(self.browse_iso_btn)
        h_iso.addWidget(self.download_iso_btn)
        self.right_layout.addLayout(h_iso)
        self.right_layout.addWidget(QLabel("Disk Image:"))
        h_disk = QHBoxLayout()
        h_disk.addWidget(self.fields["Disk Image"])
        h_disk.addWidget(self.browse_disk_btn)
        h_disk.addWidget(self.create_disk_btn)
        self.right_layout.addLayout(h_disk)
        self.right_layout.addWidget(QLabel("RAM (MB):"))
        self.right_layout.addWidget(self.fields["RAM (MB)"])
        self.right_layout.addWidget(QLabel("CPUs:"))
        self.right_layout.addWidget(self.fields["CPUs"])
        self.right_layout.addWidget(QLabel("Boot Device:"))
        self.right_layout.addWidget(self.fields["Boot Device"])
        self.right_layout.addWidget(QLabel("Extra QEMU Options:"))
        self.right_layout.addWidget(self.fields["Extra QEMU Options"])
        self.right_layout.addWidget(self.ovmf_checkbox)
        h_ovmf = QHBoxLayout()
        h_ovmf.addWidget(self.ovmf_path_input)
        h_ovmf.addWidget(self.browse_ovmf_btn)
        self.right_layout.addLayout(h_ovmf)
        self.right_layout.addWidget(self.network_group)
        self.right_layout.addWidget(self.usb_group)
        self.right_layout.addWidget(self.iso_library_group)
        self.right_layout.addWidget(self.snapshot_group)
        self.right_layout.addWidget(self.hotplug_group)
        self.right_layout.addLayout(h_btns)
        self.right_layout.addWidget(self.output_label)
        self.right_layout.addWidget(self.output_text)
        self.layout.addLayout(self.right_layout)

        # Connect signals
        self.start_btn.clicked.connect(self.start_vm)
        self.save_profile_btn.clicked.connect(self.save_profile)
        self.stop_btn.clicked.connect(self.stop_all_vms)
        self.new_profile_btn.clicked.connect(self.new_profile)
        self.delete_profile_btn.clicked.connect(self.delete_profile)
        self.profile_list.currentRowChanged.connect(self.load_profile_to_form)
        self.profiles = self.load_profiles()
        if not self.profiles:
            self.profiles.append(QemuProfile())
        self.refresh_profile_list()
        self.load_profile_to_form(0)
        self.running_processes = []
        #self.refresh_usb_list()
        #self.timer = QTimer()
        #self.timer.timeout.connect(self.refresh_usb_list)
        #self.timer.start(10000) # USB refresh every 10 seconds

        # ---- Layout with menu at the very end ----
        main_layout = QVBoxLayout()
        main_layout.setMenuBar(menubar)
        main_layout.addLayout(self.layout)
        self.setLayout(main_layout)
    def show_about_dialog(self):
        text = (
            f"<b>Ultimate QEMU Frontend {APP_VERSION}</b><br>"
            f"Author: {APP_AUTHOR}<br>"
            f"Contact: {APP_CONTACT}<br>"
            f"Website: <a href='{APP_WEBSITE}'>{APP_WEBSITE}</a><br><br>"
            "A full-featured, open-source QEMU virtual machine manager for Windows.<br><br>"
            f"<b>Changelog:</b><br><pre>{CHANGELOG}</pre>"
        )
        QMessageBox.about(self, "About Ultimate QEMU Frontend", text)

    def add_form_field(self, label, widget_type, tooltip, default_value):
        if widget_type is QLineEdit:
            w = QLineEdit()
            w.setText(default_value)
        elif widget_type is QComboBox:
            w = QComboBox()
        elif widget_type is QSpinBox:
            w = QSpinBox()
            w.setValue(default_value)
        else:
            w = widget_type()
        w.setToolTip(tooltip)
        self.fields[label] = w

    def browse_qemu(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Select QEMU executable', '', 'Executable (*.exe)')
        if fname:
            self.fields["QEMU Executable"].setText(fname)

    def browse_iso(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Select ISO image', '', 'ISO Files (*.iso);;All Files (*)')
        if fname:
            self.fields["ISO Image"].setText(fname)

    def browse_disk(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Select Disk image', '', 'All Files (*)')
        if fname:
            self.fields["Disk Image"].setText(fname)

    def browse_ovmf(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Select OVMF firmware file', '', 'All Files (*)')
        if fname:
            self.ovmf_path_input.setText(fname)

    def download_iso_dialog(self):
        items = [iso["name"] for iso in ISO_LIST]
        item, ok = QInputDialog.getItem(self, "Download ISO", "Select an ISO to download:", items, 0, False)
        if ok and item:
            for iso in ISO_LIST:
                if iso["name"] == item:
                    self.download_iso(iso)
                    break

    def download_iso(self, iso):
        save_path, _ = QFileDialog.getSaveFileName(self, "Save ISO As", iso["filename"], "ISO Files (*.iso)")
        if not save_path:
            return
        url = iso["url"]
        self.output_text.append(f"Downloading {iso['name']} from {url} ...")
        def run():
            r = requests.get(url, stream=True)
            total = int(r.headers.get('content-length', 0))
            with open(save_path, 'wb') as f:
                downloaded = 0
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            self.output_text.append(f"Downloaded {iso['name']} to {save_path}")
            self.fields["ISO Image"].setText(save_path)
        t = threading.Thread(target=run)
        t.start()

    def create_disk(self):
        fname, _ = QFileDialog.getSaveFileName(self, 'Create Disk Image', '', 'QCOW2 Files (*.qcow2);;Raw Files (*.img *.raw);;All Files (*)')
        if fname:
            size, ok = QInputDialog.getInt(self, "Disk Size", "Size in GB:", 10, 1, 2048)
            if not ok:
                return
            qemu_img = self.fields["QEMU Executable"].text().replace('qemu-system-', 'qemu-img')
            if not os.path.exists(qemu_img):
                QMessageBox.warning(self, "qemu-img Not Found", "Could not find qemu-img. Please check your QEMU installation.")
                return
            fmt = "qcow2" if fname.endswith(".qcow2") else "raw"
            cmd = [qemu_img, "create", "-f", fmt, fname, f"{size}G"]
            try:
                subprocess.check_call(cmd)
                self.fields["Disk Image"].setText(fname)
                self.output_text.append(f"Created disk image {fname}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to create disk: {e}")

    def choose_iso_library_dir(self):
        dirname = QFileDialog.getExistingDirectory(self, "Select ISO Library Folder")
        if dirname:
            self.current_profile().iso_library_dir = dirname
            self.refresh_iso_library()

    def refresh_iso_library(self):
        dir = self.current_profile().iso_library_dir
        self.iso_library_list.clear()
        if dir and os.path.isdir(dir):
            for f in os.listdir(dir):
                if f.lower().endswith(".iso"):
                    self.iso_library_list.addItem(f)

    def select_iso_from_library(self, item):
        dir = self.current_profile().iso_library_dir
        if dir:
            self.fields["ISO Image"].setText(os.path.join(dir, item.text()))

    def ovmf_toggled(self, state):
        enabled = state == Qt.Checked
        self.current_profile().ovmf_enabled = enabled
        self.ovmf_path_input.setEnabled(enabled)
        self.browse_ovmf_btn.setEnabled(enabled)
    def current_profile(self):
        idx = self.profile_list.currentRow()
        if idx < 0 or idx >= len(self.profiles):
            return self.profiles[0]
        return self.profiles[idx]

    def refresh_profile_list(self):
        self.profile_list.clear()
        for prof in self.profiles:
            self.profile_list.addItem(prof.name)

    def load_profile_to_form(self, idx):
        if idx < 0 or idx >= len(self.profiles):
            return
        prof = self.profiles[idx]
        self.fields["VM Name"].setText(prof.name)
        self.fields["QEMU Executable"].setText(prof.qemu_path)
        self.fields["Architecture"].setCurrentText(prof.arch)
        self.fields["ISO Image"].setText(prof.iso)
        self.fields["Disk Image"].setText(prof.disk)
        self.fields["RAM (MB)"].setValue(prof.ram)
        self.fields["CPUs"].setValue(prof.cpus)
        self.fields["Boot Device"].setCurrentText(prof.boot)
        self.fields["Extra QEMU Options"].setText(prof.extra)
        self.ovmf_checkbox.setChecked(prof.ovmf_enabled)
        self.ovmf_path_input.setText(prof.ovmf_path)
        self.network_mode_combo.setCurrentText(prof.network_mode if "bridged" in prof.network_mode else "user (NAT)")
        self.network_options_input.setText(prof.network_options)
        self.refresh_iso_library()

    def save_profile(self):
        idx = self.profile_list.currentRow()
        if idx < 0:
            return
        prof = self.profiles[idx]
        prof.name = self.fields["VM Name"].text()
        prof.qemu_path = self.fields["QEMU Executable"].text()
        prof.arch = self.fields["Architecture"].currentText()
        prof.iso = self.fields["ISO Image"].text()
        prof.disk = self.fields["Disk Image"].text()
        prof.ram = self.fields["RAM (MB)"].value()
        prof.cpus = self.fields["CPUs"].value()
        prof.boot = self.fields["Boot Device"].currentText()
        prof.extra = self.fields["Extra QEMU Options"].text()
        prof.ovmf_enabled = self.ovmf_checkbox.isChecked()
        prof.ovmf_path = self.ovmf_path_input.text()
        prof.network_mode = self.network_mode_combo.currentText()
        prof.network_options = self.network_options_input.text()
        self.refresh_profile_list()
        self.profile_list.setCurrentRow(idx)
        self.save_profiles()

    def new_profile(self):
        prof = QemuProfile()
        self.profiles.append(prof)
        self.refresh_profile_list()
        self.profile_list.setCurrentRow(len(self.profiles)-1)

    def delete_profile(self):
        idx = self.profile_list.currentRow()
        if idx < 0 or len(self.profiles) <= 1:
            return
        del self.profiles[idx]
        self.refresh_profile_list()
        self.profile_list.setCurrentRow(max(0, idx-1))
        self.save_profiles()

    def load_profiles(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return [QemuProfile.from_dict(d) for d in json.load(f)]
        return []

    def save_profiles(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump([p.to_dict() for p in self.profiles], f, indent=2)

    # ============ USB Passthrough ===============
    def refresh_usb_list(self):
        if not pyusb_available:
            return
        for c in self.usb_checkboxes:
            self.usb_layout.removeWidget(c)
            c.setParent(None)
        self.usb_checkboxes.clear()
        try:
            devs = usb.core.find(find_all=True)
            for dev in devs:
                name = f"{hex(dev.idVendor)}:{hex(dev.idProduct)}"
                cb = QCheckBox(name)
                self.usb_layout.addWidget(cb)
                self.usb_checkboxes.append(cb)
        except Exception as e:
            self.output_text.append(f"USB error: {e}")

    # ============ QEMU Control ==================
    def start_vm(self):
        prof = self.current_profile()
        exe = prof.qemu_path
        if not exe or not os.path.exists(exe):
            QMessageBox.warning(self, "QEMU Not Found", "Set the correct QEMU executable.")
            return
        cmd = [exe]
        cmd += ["-m", str(prof.ram)]
        cmd += ["-smp", str(prof.cpus)]
        if prof.boot == "ISO (cdrom)":
            if prof.iso:
                cmd += ["-cdrom", prof.iso]
            if prof.disk:
                cmd += ["-drive", f"file={prof.disk},format=qcow2"]
        else:
            if prof.disk:
                cmd += ["-drive", f"file={prof.disk},format=qcow2"]
            if prof.iso:
                cmd += ["-cdrom", prof.iso]
        if prof.ovmf_enabled and prof.ovmf_path:
            cmd += ["-drive", f"if=pflash,format=raw,readonly=on,file={prof.ovmf_path}"]
        if prof.extra:
            cmd += prof.extra.split()
        # USB
        if pyusb_available:
            for c in self.usb_checkboxes:
                if c.isChecked():
                    cmd += ["-device", f"usb-host,hostdevice={c.text()}"]
        # Networking
        if prof.network_mode == "user (NAT)":
            cmd += ["-net", "nic", "-net", "user"]
        elif prof.network_mode == "bridged (TAP)":
            cmd += ["-net", "nic", "-net", "tap"]
        elif prof.network_mode == "custom" and prof.network_options:
            cmd += prof.network_options.split()
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.running_processes.append(proc)
            self.output_text.append(f"Started VM: {' '.join(cmd)}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not start VM: {e}")

    def stop_all_vms(self):
        for proc in self.running_processes:
            try:
                proc.terminate()
            except Exception:
                pass
        self.output_text.append("Stopped all running VMs.")
        self.running_processes.clear()

    # ============ Snapshot, Hotplug, and Updates =============
    def list_snapshots(self):
        QMessageBox.information(self, "Not Implemented", "Snapshot list not implemented in this sample.")

    def create_snapshot(self):
        QMessageBox.information(self, "Not Implemented", "Snapshot creation not implemented in this sample.")

    def revert_snapshot(self):
        QMessageBox.information(self, "Not Implemented", "Snapshot revert not implemented in this sample.")

    def delete_snapshot(self):
        QMessageBox.information(self, "Not Implemented", "Snapshot delete not implemented in this sample.")

    def hot_attach_iso(self):
        QMessageBox.information(self, "Not Implemented", "Hot attach not implemented in this sample.")

    def hot_detach_iso(self):
        QMessageBox.information(self, "Not Implemented", "Hot detach not implemented in this sample.")

    def check_updates(self):
        QMessageBox.information(self, "Not Implemented", "Update checker not implemented in this sample.")

# ---- Main Entry Point ----
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = UltimateQemuFrontend()
    window.show()
    sys.exit(app.exec_())
