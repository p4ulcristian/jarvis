# Jarvis - Tasks

## In Progress
- [ ] Set up keyd + systemd on Paul's machine

## Todo
- [ ] Add audio feedback (beep on start/stop recording)
- [ ] Add Waybar/status indicator support
- [ ] Test with different audio inputs
- [ ] Add language configuration option

## Done
- [x] Core daemon with signal-based PTT
- [x] PipeWire audio recording
- [x] Parakeet TDT 0.6B v2 integration
- [x] wtype/wl-clipboard output
- [x] keyd config for CapsLock binding
- [x] systemd user service
- [x] install.sh script
- [x] Tested STT - working!

---

## Tech Stack

| Component | Choice |
|-----------|--------|
| STT Model | NVIDIA Parakeet TDT 0.6B v2 |
| Framework | NeMo |
| Audio | PipeWire/sounddevice |
| Output | wtype + wl-clipboard |
| Hotkey | keyd (CapsLock) |
| Service | systemd user service |
