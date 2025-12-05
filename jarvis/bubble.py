#!/usr/bin/env python3
"""Jarvis floating bubble overlay using GTK4 + layer-shell."""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')

from gi.repository import Gtk, Gdk, GLib, Gtk4LayerShell as LayerShell
from pathlib import Path
import math

# Bubble settings
BUBBLE_SIZE = 60
MARGIN_TOP = 20
MARGIN_RIGHT = 20


class JarvisBubble(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.jarvis.bubble')
        self.window = None
        self.drawing_area = None
        self.pulse_phase = 0.0
        self.is_active = False
        self.animation_id = None

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

        # Poll for CapsLock state
        GLib.timeout_add(50, self.check_capslock)

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

    def check_capslock(self):
        """Check CapsLock LED state via sysfs."""
        try:
            # Find CapsLock LED
            leds = Path('/sys/class/leds')
            for led in leds.iterdir():
                if 'capslock' in led.name.lower():
                    brightness = int((led / 'brightness').read_text().strip())
                    self.is_active = brightness > 0
                    break
        except Exception:
            pass
        return True  # Keep polling

    def animate(self):
        """Update animation phase."""
        if self.is_active:
            self.pulse_phase += 0.15
            if self.pulse_phase > 2 * math.pi:
                self.pulse_phase -= 2 * math.pi
        else:
            # Fade out pulse
            if self.pulse_phase > 0:
                self.pulse_phase = max(0, self.pulse_phase - 0.1)

        self.drawing_area.queue_draw()
        return True  # Keep animating

    def draw_bubble(self, area, cr, width, height):
        """Draw the bubble with Cairo."""
        cx, cy = width / 2, height / 2
        radius = min(width, height) / 2 - 4

        # Clear background
        cr.set_operator(0)  # CAIRO_OPERATOR_CLEAR
        cr.paint()
        cr.set_operator(1)  # CAIRO_OPERATOR_OVER

        # Glow effect when active
        if self.is_active or self.pulse_phase > 0:
            glow_intensity = (math.sin(self.pulse_phase) + 1) / 2 * 0.5 + 0.3
            glow_radius = radius + 8 + math.sin(self.pulse_phase) * 4

            # Radial gradient for glow
            import cairo
            pattern = cairo.RadialGradient(cx, cy, radius * 0.5, cx, cy, glow_radius)
            pattern.add_color_stop_rgba(0, 0.4, 0.8, 1.0, glow_intensity)
            pattern.add_color_stop_rgba(0.6, 0.2, 0.5, 0.9, glow_intensity * 0.5)
            pattern.add_color_stop_rgba(1, 0.1, 0.3, 0.8, 0)
            cr.set_source(pattern)
            cr.arc(cx, cy, glow_radius, 0, 2 * math.pi)
            cr.fill()

        # Main bubble - gradient fill
        import cairo
        pattern = cairo.RadialGradient(cx - radius * 0.3, cy - radius * 0.3, 0, cx, cy, radius)
        if self.is_active:
            # Active: bright cyan/blue
            pattern.add_color_stop_rgba(0, 0.5, 0.9, 1.0, 0.95)
            pattern.add_color_stop_rgba(1, 0.2, 0.5, 0.8, 0.9)
        else:
            # Inactive: muted blue-gray
            pattern.add_color_stop_rgba(0, 0.4, 0.5, 0.6, 0.85)
            pattern.add_color_stop_rgba(1, 0.2, 0.3, 0.4, 0.8)

        cr.set_source(pattern)
        cr.arc(cx, cy, radius, 0, 2 * math.pi)
        cr.fill()

        # Subtle highlight
        cr.set_source_rgba(1, 1, 1, 0.3)
        cr.arc(cx - radius * 0.2, cy - radius * 0.2, radius * 0.3, 0, 2 * math.pi)
        cr.fill()


def main():
    app = JarvisBubble()
    app.run()


if __name__ == '__main__':
    main()
