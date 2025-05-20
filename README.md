# Ultimate QEMU Frontend

A full-featured, open-source graphical frontend for [QEMU](https://www.qemu.org/) virtual machines, built with PyQt5 for Windows.

## Features

- Easy creation and management of VM profiles
- Download ISOs (Ubuntu, Fedora, Debian, Windows, and more) directly in-app
- USB passthrough (attach host devices to VMs)
- OVMF/UEFI support for modern guest OSes
- Snapshot management (UI stubs)
- Built-in QEMU/ISO update checker (UI stub)
- Hot plug ISOs and drive images (UI stub)
- Simple network UI for NAT and bridged modes
- Extensive form fields for VM hardware configuration

## Getting Started

### 1. Requirements

- **Windows 10 or later**
- **[QEMU for Windows](https://qemu.weilnetz.de/w64/)**
- **Python 3.7+**
- **[PyQt5](https://pypi.org/project/PyQt5/)**
- **requests** (for ISO downloading)
- (Optional) **pyusb** (for USB passthrough support)

### 2. Install Dependencies

Open Command Prompt or PowerShell and run:

```sh
pip install PyQt5 requests pyusb
```

### 3. Download QEMU

Download the latest QEMU for Windows from:  
https://qemu.weilnetz.de/w64/

Extract it somewhere convenient and remember the folder path.

### 4. Run the App

- Download or clone this repository.
- Open a terminal in the project folder.
- Run:

```sh
python ultimate_qemu_frontendc.py
```

### 5. First Steps in the App

1. **Set QEMU Executable:**  
   Click "Browse QEMU" and select `qemu-system-x86_64.exe` or another QEMU system binary from your extracted QEMU folder.

2. **Create/Edit a VM Profile:**  
   - Name your VM, select architecture, set RAM/CPUs, choose boot device, etc.
   - Download or browse to an ISO file (use the app's download feature or your own images).
   - Set up a virtual disk (browse to one or use "Create Disk").

3. **(Optional) Enable UEFI/OVMF:**  
   - Check the box and browse to your OVMF firmware file if needed.

4. **(Optional) USB Passthrough:**  
   - Install `pyusb` and click "Refresh USB List" to see host devices.

5. **Start the VM:**  
   - Click "Start VM" to launch your configured guest OS.

### 6. Saving and Loading Profiles

- All VM profiles are stored in `ultimate_qemu_profiles.json` in the project folder.
- Use "Save Profile" to keep your settings.

## Troubleshooting

- Make sure QEMU and Python are both in your system PATH, or browse to their full paths in the app.
- Some advanced features (snapshots, hot plug, update checker) may be stubs/not fully implemented.
- For issues with PyQt5 installation, ensure you’re using a supported version of Python.

## Contributing

Pull requests, bug reports, and feature suggestions are welcome!

## License

[MIT License](LICENSE)

## Contact

- **Author:** Daniel Kaiser
- **Email:** daniel.kaiser.dev@gmail.com

---

*This project is not affiliated with or endorsed by QEMU.*
