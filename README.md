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
sudo pacman -S keyd wtype wl-clipboard

# Clone and install
git clone https://github.com/p4ulcristian/jarvis.git
cd jarvis
uv venv && uv pip install -e .

# Run install script
./install.sh
```

## Usage

Start the service:
```bash
systemctl --user start jarvis
```

Then hold CapsLock and speak. Text appears at cursor.

## Config

Environment variables:
- `JARVIS_OUTPUT_MODE` - `clipboard` (default) or `type`
