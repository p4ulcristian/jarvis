# Jarvis

Push-to-talk speech-to-text for Wayland. Hold CapsLock, speak, release, text appears at cursor.

## Requirements

- Hyprland (or any Wayland compositor)
- NVIDIA GPU with CUDA
- Python 3.10+
- keyd
- wtype, wl-clipboard

## Install

```bash
# System deps (Arch)
sudo pacman -S keyd wtype wl-clipboard python

# Enable keyd
sudo systemctl enable --now keyd

# Install jarvis
pip install -e .
```

## Setup

### keyd

```bash
sudo cp config/keyd.conf /etc/keyd/default.conf
sudo systemctl restart keyd
```

### Scripts

```bash
sudo cp scripts/jarvis-start scripts/jarvis-stop /usr/local/bin/
```

### Systemd (optional)

```bash
cp config/jarvis.service ~/.config/systemd/user/
systemctl --user enable --now jarvis
```

## Usage

Run manually:
```bash
python -m jarvis.daemon
```

Or with systemd:
```bash
systemctl --user start jarvis
```

Then hold CapsLock and speak.

## Config

Environment variables:
- `JARVIS_OUTPUT_MODE` - `clipboard` (default) or `type`
