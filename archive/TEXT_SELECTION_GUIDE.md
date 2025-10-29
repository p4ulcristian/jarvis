# JARVIS Terminal UI - Text Selection & Export Guide

## Problem Solved
Previously, you couldn't copy text from the JARVIS Terminal UI because the Textual framework takes over terminal control, disabling normal text selection.

## Solutions Implemented

### 1. Mouse Text Selection (Recommended)
**How to use:** Hold `Shift` while dragging your mouse to select text

This works in most modern terminal emulators:
- ✓ GNOME Terminal
- ✓ Konsole (KDE)
- ✓ xterm
- ✓ iTerm2 (macOS)
- ✓ Windows Terminal
- ✓ Alacritty

**To copy selected text:**
- Linux/GNOME: Automatically copied, or use `Ctrl+Shift+C`
- KDE/Konsole: Automatically copied, or use `Ctrl+Shift+C`
- macOS: `Cmd+C`
- Windows: `Ctrl+Shift+C`

**Note:** Some terminals may use different modifier keys:
- Try `Alt+Mouse` if Shift doesn't work
- Try `Ctrl+Shift+Mouse` in some terminals
- Check your terminal's preferences/documentation

### 2. Export to File (Universal Solution)
**How to use:** Press `e` while the UI is running

**What happens:**
- All transcriptions and system logs are exported to a timestamped file
- Files are saved to: `~/jarvis_exports/jarvis_logs_YYYYMMDD_HHMMSS.txt`
- A confirmation message appears in the System Logs panel
- You can then open the file in any text editor and copy what you need

**Example export location:**
```
~/jarvis_exports/jarvis_logs_20251019_143522.txt
```

## UI Enhancements

### Updated Help Text
The UI now shows helpful information in the widget borders:

**Transcription panel:**
```
[>>] Transcription
scroll: ↑↓ pgup/pgdn | export: e | select: shift+mouse
```

**System Logs panel:**
```
[==] System Logs
export: e | select: shift+mouse
```

**Footer:**
The footer automatically shows available keyboard shortcuts, including the new export function.

## Technical Changes

### Modified Files
- `source-code/ui/terminal_ui.py` - Added export functionality and help text

### Key Changes:
1. **New keyboard binding:** `e` key triggers export
2. **Export function:** `action_export_logs()` method
3. **Help text:** Border subtitles updated with usage instructions
4. **Documentation:** Module docstring updated with selection info

### Code Structure:
```python
BINDINGS = [
    ("ctrl+c", "quit", "Quit"),
    ("e", "export_logs", "Export Logs"),  # NEW
]

def action_export_logs(self) -> None:
    """Export transcriptions and system logs to a file"""
    # Creates ~/jarvis_exports/ directory
    # Exports all logs with timestamp
    # Shows success/error message in UI
```

## Testing

### Syntax Check
✓ Python syntax validated - no errors

### Export Directory
✓ Export directory created successfully at `~/jarvis_exports/`

### Manual Testing Steps:
1. Run JARVIS Terminal UI: `python3 source-code/main.py`
2. Generate some transcriptions and logs
3. Press `e` to export
4. Check `~/jarvis_exports/` for the exported file
5. Try Shift+Mouse to select text directly in the UI

## Troubleshooting

### Text selection doesn't work with Shift+Mouse
**Try:**
1. Alt+Mouse instead of Shift+Mouse
2. Ctrl+Shift+Mouse
3. Check your terminal's mouse settings
4. Use the export feature (`e` key) as an alternative

### Export fails
**Check:**
1. Home directory is writable
2. Error message in System Logs panel
3. File permissions on `~/jarvis_exports/`

### Export file is empty
**Possible causes:**
1. No logs have been generated yet
2. RichLog widget hasn't received data
3. Check the test script: `python3 test_export_feature.py`

## Summary

You now have **two ways** to copy text from JARVIS Terminal UI:

1. **Quick selection:** `Shift+Mouse` (works in most terminals)
2. **Export all logs:** Press `e` (universal, saves to file)

Both methods work independently, so use whichever is more convenient for your workflow!
