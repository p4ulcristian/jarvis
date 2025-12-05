#!/usr/bin/env python3
"""Jarvis floating bubble overlay using GTK4 + layer-shell."""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')

from gi.repository import Gtk, Gdk, GLib, Gtk4LayerShell as LayerShell
from pathlib import Path
import math
import threading
from evdev import InputDevice, ecodes, list_devices

# Bubble settings
BUBBLE_SIZE = 100  # Bigger for more glow room
MARGIN_TOP = 20
MARGIN_RIGHT = 20

# Cyberpunk neon colors (RGB 0-1)
NEON_CYAN = (0.0, 1.0, 1.0)
NEON_MAGENTA = (1.0, 0.0, 0.8)
NEON_PINK = (1.0, 0.2, 0.6)
ELECTRIC_BLUE = (0.1, 0.5, 1.0)
DARK_PURPLE = (0.15, 0.05, 0.2)


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


class JarvisBubble(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.jarvis.bubble')
        self.window = None
        self.drawing_area = None
        self.pulse_phase = 0.0
        self.is_active = False
        self.animation_id = None
        self.evdev_thread = None

    def do_activate(self):
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_default_size(BUBBLE_SIZE, BUBBLE_SIZE)

        # Set up layer shell (makes it a floating overlay, not a window)
        LayerShell.init_for_window(self.window)
        LayerShell.set_layer(self.window, LayerShell.Layer.OVERLAY)
        LayerShell.set_anchor(self.window, LayerShell.Edge.TOP, True)
        LayerShell.set_anchor(self.window, LayerShell.Edge.RIGHT, True)
        LayerShell.set_margin(self.window, LayerShell.Edge.TOP, MARGIN_TOP)
        LayerShell.set_margin(self.window, LayerShell.Edge.RIGHT, MARGIN_RIGHT)
        LayerShell.set_exclusive_zone(self.window, 0)  # Don't reserve space

        # Make window transparent
        self.window.add_css_class('transparent-window')

        # Create drawing area for the bubble
        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_size_request(BUBBLE_SIZE, BUBBLE_SIZE)
        self.drawing_area.set_draw_func(self.draw_bubble)
        self.window.set_child(self.drawing_area)

        # Load CSS
        self.load_css()

        # Start evdev listener for CapsLock
        self.start_evdev_listener()

        # Start animation loop
        self.animation_id = GLib.timeout_add(16, self.animate)  # ~60fps

        self.window.present()

    def load_css(self):
        css = b"""
        .transparent-window {
            background: transparent;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def start_evdev_listener(self):
        """Start background thread to listen for CapsLock via evdev."""
        def listener():
            device = find_keyboard()
            if not device:
                print("No keyboard found for evdev!", flush=True)
                return
            print(f"Listening on {device.name}", flush=True)
            try:
                for event in device.read_loop():
                    if event.type == ecodes.EV_KEY and event.code == ecodes.KEY_CAPSLOCK:
                        if event.value == 1:  # Key pressed
                            self.is_active = True
                        elif event.value == 0:  # Key released
                            self.is_active = False
            except Exception as e:
                print(f"Evdev error: {e}", flush=True)

        self.evdev_thread = threading.Thread(target=listener, daemon=True)
        self.evdev_thread.start()

    def animate(self):
        """Update animation phase."""
        if self.is_active:
            self.pulse_phase += 0.2  # Faster pulse
            if self.pulse_phase > 2 * math.pi:
                self.pulse_phase -= 2 * math.pi
        else:
            # Fade out pulse
            if self.pulse_phase > 0:
                self.pulse_phase = max(0, self.pulse_phase - 0.08)

        self.drawing_area.queue_draw()
        return True  # Keep animating

    def draw_bubble(self, area, cr, width, height):
        """Draw the bubble with Cairo - CYBERPUNK STYLE."""
        import cairo
        cx, cy = width / 2, height / 2
        radius = 25  # Core bubble size

        # Clear background
        cr.set_operator(0)  # CAIRO_OPERATOR_CLEAR
        cr.paint()
        cr.set_operator(1)  # CAIRO_OPERATOR_OVER

        if self.is_active or self.pulse_phase > 0:
            # ACTIVE: Full cyberpunk neon blast
            pulse = (math.sin(self.pulse_phase) + 1) / 2
            pulse2 = (math.sin(self.pulse_phase * 2) + 1) / 2

            # Outer glow layer 1 - magenta haze (smaller)
            glow_r = radius + 15 + pulse * 5
            pattern = cairo.RadialGradient(cx, cy, radius, cx, cy, glow_r)
            pattern.add_color_stop_rgba(0, *NEON_MAGENTA, 0.6 * pulse + 0.2)
            pattern.add_color_stop_rgba(0.5, *NEON_PINK, 0.3 * pulse)
            pattern.add_color_stop_rgba(1, *NEON_MAGENTA, 0)
            cr.set_source(pattern)
            cr.arc(cx, cy, glow_r, 0, 2 * math.pi)
            cr.fill()

            # Outer glow layer 2 - cyan ring (smaller)
            glow_r2 = radius + 10 + pulse2 * 4
            pattern = cairo.RadialGradient(cx, cy, radius * 0.8, cx, cy, glow_r2)
            pattern.add_color_stop_rgba(0, *NEON_CYAN, 0.7 * pulse + 0.3)
            pattern.add_color_stop_rgba(0.6, *ELECTRIC_BLUE, 0.4 * pulse)
            pattern.add_color_stop_rgba(1, *NEON_CYAN, 0)
            cr.set_source(pattern)
            cr.arc(cx, cy, glow_r2, 0, 2 * math.pi)
            cr.fill()

            # Solid base for core
            cr.set_source_rgba(*DARK_PURPLE, 1.0)
            cr.arc(cx, cy, radius, 0, 2 * math.pi)
            cr.fill()

            # Core bubble - hot gradient (solid, blue-tinted center)
            pattern = cairo.RadialGradient(cx - radius * 0.3, cy - radius * 0.3, 0, cx, cy, radius)
            pattern.add_color_stop_rgba(0, 0.7, 0.9, 1.0, 1.0)  # Light cyan center
            pattern.add_color_stop_rgba(0.3, *NEON_CYAN, 1.0)
            pattern.add_color_stop_rgba(0.7, *NEON_MAGENTA, 1.0)
            pattern.add_color_stop_rgba(1, *DARK_PURPLE, 1.0)
            cr.set_source(pattern)
            cr.arc(cx, cy, radius, 0, 2 * math.pi)
            cr.fill()

            # Inner shine (blue tinted)
            cr.set_source_rgba(0.8, 0.95, 1.0, 0.5 + pulse * 0.3)
            cr.arc(cx - radius * 0.25, cy - radius * 0.25, radius * 0.2, 0, 2 * math.pi)
            cr.fill()

        else:
            # INACTIVE: Solid dark cyberpunk orb
            # Subtle outer glow
            pattern = cairo.RadialGradient(cx, cy, radius, cx, cy, radius + 12)
            pattern.add_color_stop_rgba(0, *NEON_MAGENTA, 0.3)
            pattern.add_color_stop_rgba(1, *DARK_PURPLE, 0)
            cr.set_source(pattern)
            cr.arc(cx, cy, radius + 12, 0, 2 * math.pi)
            cr.fill()

            # Solid base circle
            cr.set_source_rgba(*DARK_PURPLE, 1.0)
            cr.arc(cx, cy, radius, 0, 2 * math.pi)
            cr.fill()

            # Core gradient on top
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


def main():
    app = JarvisBubble()
    app.run()


if __name__ == '__main__':
    main()
