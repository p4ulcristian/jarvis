#!/usr/bin/env python3
"""Iris floating bubble overlay using GTK4 + layer-shell."""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')

from gi.repository import Gtk, Gdk, GLib, Gtk4LayerShell as LayerShell
from pathlib import Path
import math
import os
import signal
import threading
from evdev import InputDevice, ecodes, list_devices

# Bubble settings
BUBBLE_SIZE = 120  # Bigger for label space
MARGIN_TOP = 20
MARGIN_RIGHT = 20

# State file for communication with server
STATE_FILE = Path("/tmp/iris-state")

# Colors (RGB 0-1)
NEON_CYAN = (0.0, 1.0, 1.0)
NEON_MAGENTA = (1.0, 0.0, 0.8)
NEON_PINK = (1.0, 0.2, 0.6)
ELECTRIC_BLUE = (0.1, 0.5, 1.0)
DARK_PURPLE = (0.15, 0.05, 0.2)
GOLD = (1.0, 0.85, 0.0)
GOLD_DARK = (0.8, 0.6, 0.0)
WARM_ORANGE = (1.0, 0.6, 0.2)

# X button settings
X_SIZE = 12
X_MARGIN = 8
X_HIT_RADIUS = 15


def find_keyboard():
    """Find a keyboard device."""
    for path in list_devices():
        try:
            device = InputDevice(path)
            caps = device.capabilities()
            if ecodes.EV_KEY in caps:
                keys = caps[ecodes.EV_KEY]
                if ecodes.KEY_CAPSLOCK in keys:
                    return device
        except Exception:
            pass
    return None


class IrisBubble(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.iris.bubble')
        self.window = None
        self.drawing_area = None
        self.pulse_phase = 0.0
        self.loading_phase = 0.0
        self.is_listening = False  # User speaking (CapsLock)
        self.is_speaking = False   # Iris speaking (TTS)
        self.is_loading = True     # Model loading
        self.animation_id = None
        self.evdev_thread = None
        self.state_thread = None
        # Mouse tracking for X button
        self.mouse_x = -1
        self.mouse_y = -1
        self.x_hovered = False

    def do_activate(self):
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_default_size(BUBBLE_SIZE, BUBBLE_SIZE)

        # Set up layer shell
        LayerShell.init_for_window(self.window)
        LayerShell.set_layer(self.window, LayerShell.Layer.OVERLAY)
        LayerShell.set_anchor(self.window, LayerShell.Edge.TOP, True)
        LayerShell.set_anchor(self.window, LayerShell.Edge.RIGHT, True)
        LayerShell.set_margin(self.window, LayerShell.Edge.TOP, MARGIN_TOP)
        LayerShell.set_margin(self.window, LayerShell.Edge.RIGHT, MARGIN_RIGHT)
        LayerShell.set_exclusive_zone(self.window, 0)

        self.window.add_css_class('transparent-window')

        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_size_request(BUBBLE_SIZE, BUBBLE_SIZE)
        self.drawing_area.set_draw_func(self.draw_bubble)
        self.window.set_child(self.drawing_area)

        # Mouse tracking
        motion_controller = Gtk.EventControllerMotion()
        motion_controller.connect('motion', self.on_mouse_motion)
        motion_controller.connect('leave', self.on_mouse_leave)
        self.drawing_area.add_controller(motion_controller)

        click_controller = Gtk.GestureClick()
        click_controller.connect('pressed', self.on_click)
        self.drawing_area.add_controller(click_controller)

        self.load_css()
        self.start_evdev_listener()
        self.start_state_listener()
        self.animation_id = GLib.timeout_add(16, self.animate)

        self.window.present()

    def load_css(self):
        css = b".transparent-window { background: transparent; }"
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def get_x_center(self):
        return (BUBBLE_SIZE - X_MARGIN - X_SIZE // 2, X_MARGIN + X_SIZE // 2)

    def on_mouse_motion(self, controller, x, y):
        self.mouse_x = x
        self.mouse_y = y
        x_cx, x_cy = self.get_x_center()
        dist = math.sqrt((x - x_cx) ** 2 + (y - x_cy) ** 2)
        self.x_hovered = dist <= X_HIT_RADIUS

    def on_mouse_leave(self, controller):
        self.mouse_x = -1
        self.mouse_y = -1
        self.x_hovered = False

    def on_click(self, gesture, n_press, x, y):
        x_cx, x_cy = self.get_x_center()
        dist = math.sqrt((x - x_cx) ** 2 + (y - x_cy) ** 2)
        if dist <= X_HIT_RADIUS:
            print("X clicked - shutting down Iris", flush=True)
            os.kill(os.getppid(), signal.SIGTERM)

    def start_evdev_listener(self):
        """Listen for CapsLock (user speaking)."""
        def listener():
            device = find_keyboard()
            if not device:
                print("No keyboard found for evdev!", flush=True)
                return
            print(f"Listening on {device.name}", flush=True)
            try:
                for event in device.read_loop():
                    if event.type == ecodes.EV_KEY and event.code == ecodes.KEY_CAPSLOCK:
                        self.is_listening = event.value == 1
            except Exception as e:
                print(f"Evdev error: {e}", flush=True)

        self.evdev_thread = threading.Thread(target=listener, daemon=True)
        self.evdev_thread.start()

    def start_state_listener(self):
        """Poll state file for server status."""
        def poll_state():
            import time
            while True:
                try:
                    if STATE_FILE.exists():
                        state = STATE_FILE.read_text().strip()
                        self.is_loading = state == "loading"
                        self.is_speaking = state == "speaking"
                    else:
                        self.is_loading = True
                except Exception:
                    pass
                time.sleep(0.1)

        self.state_thread = threading.Thread(target=poll_state, daemon=True)
        self.state_thread.start()

    def animate(self):
        # Loading animation (slow rotation)
        self.loading_phase += 0.03
        if self.loading_phase > 2 * math.pi:
            self.loading_phase -= 2 * math.pi

        # Active animation (faster pulse)
        if self.is_listening or self.is_speaking:
            self.pulse_phase += 0.15
            if self.pulse_phase > 2 * math.pi:
                self.pulse_phase -= 2 * math.pi
        else:
            if self.pulse_phase > 0:
                self.pulse_phase = max(0, self.pulse_phase - 0.08)

        self.drawing_area.queue_draw()
        return True

    def draw_bubble(self, area, cr, width, height):
        import cairo
        cx, cy = width / 2, height / 2 - 10  # Shift up to make room for label
        radius = 25

        # Clear background
        cr.set_operator(0)
        cr.paint()
        cr.set_operator(1)

        # Determine colors based on state
        if self.is_listening:
            primary = NEON_CYAN
            secondary = ELECTRIC_BLUE
            accent = NEON_MAGENTA
        elif self.is_speaking:
            primary = GOLD
            secondary = GOLD_DARK
            accent = WARM_ORANGE
        else:
            primary = NEON_MAGENTA
            secondary = DARK_PURPLE
            accent = NEON_PINK

        # === LOADING STATE ===
        if self.is_loading and not self.is_listening:
            # Rotating dots around the bubble
            num_dots = 8
            dot_radius = 3
            orbit_radius = radius + 12
            for i in range(num_dots):
                angle = self.loading_phase + (i * 2 * math.pi / num_dots)
                dx = cx + math.cos(angle) * orbit_radius
                dy = cy + math.sin(angle) * orbit_radius
                # Fade dots based on position
                alpha = 0.3 + 0.5 * ((math.sin(angle - self.loading_phase * 2) + 1) / 2)
                cr.set_source_rgba(*NEON_CYAN, alpha)
                cr.arc(dx, dy, dot_radius, 0, 2 * math.pi)
                cr.fill()

        # === ACTIVE STATE (listening or speaking) ===
        if self.is_listening or self.is_speaking or self.pulse_phase > 0:
            pulse = (math.sin(self.pulse_phase) + 1) / 2
            pulse2 = (math.sin(self.pulse_phase * 2) + 1) / 2

            # Outer glow
            glow_r = radius + 15 + pulse * 5
            pattern = cairo.RadialGradient(cx, cy, radius, cx, cy, glow_r)
            pattern.add_color_stop_rgba(0, *accent, 0.6 * pulse + 0.2)
            pattern.add_color_stop_rgba(0.5, *primary, 0.3 * pulse)
            pattern.add_color_stop_rgba(1, *accent, 0)
            cr.set_source(pattern)
            cr.arc(cx, cy, glow_r, 0, 2 * math.pi)
            cr.fill()

            # Inner glow ring
            glow_r2 = radius + 10 + pulse2 * 4
            pattern = cairo.RadialGradient(cx, cy, radius * 0.8, cx, cy, glow_r2)
            pattern.add_color_stop_rgba(0, *primary, 0.7 * pulse + 0.3)
            pattern.add_color_stop_rgba(0.6, *secondary, 0.4 * pulse)
            pattern.add_color_stop_rgba(1, *primary, 0)
            cr.set_source(pattern)
            cr.arc(cx, cy, glow_r2, 0, 2 * math.pi)
            cr.fill()

            # Core base
            cr.set_source_rgba(*DARK_PURPLE, 1.0)
            cr.arc(cx, cy, radius, 0, 2 * math.pi)
            cr.fill()

            # Core gradient
            pattern = cairo.RadialGradient(cx - radius * 0.3, cy - radius * 0.3, 0, cx, cy, radius)
            if self.is_speaking:
                pattern.add_color_stop_rgba(0, 1.0, 0.95, 0.7, 1.0)  # Warm center
            else:
                pattern.add_color_stop_rgba(0, 0.7, 0.9, 1.0, 1.0)  # Cool center
            pattern.add_color_stop_rgba(0.3, *primary, 1.0)
            pattern.add_color_stop_rgba(0.7, *accent, 1.0)
            pattern.add_color_stop_rgba(1, *DARK_PURPLE, 1.0)
            cr.set_source(pattern)
            cr.arc(cx, cy, radius, 0, 2 * math.pi)
            cr.fill()

            # Inner shine
            shine_color = (1.0, 0.95, 0.8) if self.is_speaking else (0.8, 0.95, 1.0)
            cr.set_source_rgba(*shine_color, 0.5 + pulse * 0.3)
            cr.arc(cx - radius * 0.25, cy - radius * 0.25, radius * 0.2, 0, 2 * math.pi)
            cr.fill()

        else:
            # === IDLE STATE ===
            # Subtle outer glow
            pattern = cairo.RadialGradient(cx, cy, radius, cx, cy, radius + 12)
            pattern.add_color_stop_rgba(0, *NEON_MAGENTA, 0.3)
            pattern.add_color_stop_rgba(1, *DARK_PURPLE, 0)
            cr.set_source(pattern)
            cr.arc(cx, cy, radius + 12, 0, 2 * math.pi)
            cr.fill()

            # Base circle
            cr.set_source_rgba(*DARK_PURPLE, 1.0)
            cr.arc(cx, cy, radius, 0, 2 * math.pi)
            cr.fill()

            # Core gradient
            pattern = cairo.RadialGradient(cx - radius * 0.3, cy - radius * 0.3, 0, cx, cy, radius)
            pattern.add_color_stop_rgba(0, 0.5, 0.3, 0.6, 1.0)
            pattern.add_color_stop_rgba(1, *DARK_PURPLE, 1.0)
            cr.set_source(pattern)
            cr.arc(cx, cy, radius, 0, 2 * math.pi)
            cr.fill()

            # Highlight
            cr.set_source_rgba(1, 1, 1, 0.25)
            cr.arc(cx - radius * 0.2, cy - radius * 0.2, radius * 0.2, 0, 2 * math.pi)
            cr.fill()

        # === LABEL with dark background ===
        label_text = "Iris"
        label_y = cy + radius + 28  # Lower position

        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13)
        extents = cr.text_extents(label_text)
        text_x = cx - extents.width / 2 - extents.x_bearing
        text_y = label_y

        # Dark background pill
        padding_x = 8
        padding_y = 4
        bg_x = text_x - padding_x
        bg_y = text_y - extents.height - padding_y + 2
        bg_w = extents.width + padding_x * 2
        bg_h = extents.height + padding_y * 2
        bg_radius = bg_h / 2

        cr.set_source_rgba(0, 0, 0, 0.6)
        # Draw rounded rectangle
        cr.new_path()
        cr.arc(bg_x + bg_radius, bg_y + bg_radius, bg_radius, math.pi, 1.5 * math.pi)
        cr.arc(bg_x + bg_w - bg_radius, bg_y + bg_radius, bg_radius, 1.5 * math.pi, 2 * math.pi)
        cr.arc(bg_x + bg_w - bg_radius, bg_y + bg_h - bg_radius, bg_radius, 0, 0.5 * math.pi)
        cr.arc(bg_x + bg_radius, bg_y + bg_h - bg_radius, bg_radius, 0.5 * math.pi, math.pi)
        cr.close_path()
        cr.fill()

        # Text glow
        label_color = GOLD if self.is_speaking else NEON_CYAN
        for alpha in [0.15, 0.25, 0.4]:
            cr.set_source_rgba(*label_color, alpha)
            cr.move_to(text_x, text_y)
            cr.show_text(label_text)

        # Main text
        cr.set_source_rgba(*label_color, 0.95)
        cr.move_to(text_x, text_y)
        cr.show_text(label_text)

        # === X BUTTON ===
        x_cx, x_cy = self.get_x_center()
        half = X_SIZE // 2
        x_alpha = 0.9 if self.x_hovered else 0.4

        if self.x_hovered:
            cr.set_source_rgba(*NEON_MAGENTA, 0.4)
            cr.arc(x_cx, x_cy, X_HIT_RADIUS, 0, 2 * math.pi)
            cr.fill()

        cr.set_line_width(2.5 if self.x_hovered else 2.0)
        cr.set_line_cap(1)
        cr.set_source_rgba(1, 1, 1, x_alpha)
        cr.move_to(x_cx - half, x_cy - half)
        cr.line_to(x_cx + half, x_cy + half)
        cr.stroke()
        cr.move_to(x_cx + half, x_cy - half)
        cr.line_to(x_cx - half, x_cy + half)
        cr.stroke()


def main():
    app = IrisBubble()
    app.run()


if __name__ == '__main__':
    main()
