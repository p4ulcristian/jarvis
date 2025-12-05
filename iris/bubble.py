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
BUBBLE_SIZE = 100  # Bigger for more glow room
MARGIN_TOP = 20
MARGIN_RIGHT = 20

# Cyberpunk neon colors (RGB 0-1)
NEON_CYAN = (0.0, 1.0, 1.0)
NEON_MAGENTA = (1.0, 0.0, 0.8)
NEON_PINK = (1.0, 0.2, 0.6)
ELECTRIC_BLUE = (0.1, 0.5, 1.0)
DARK_PURPLE = (0.15, 0.05, 0.2)

# X button settings
X_SIZE = 12  # Size of the X
X_MARGIN = 8  # Margin from top-right corner
X_HIT_RADIUS = 15  # Click detection radius


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
        self.is_active = False
        self.animation_id = None
        self.evdev_thread = None
        # Mouse tracking for X button
        self.mouse_x = -1
        self.mouse_y = -1
        self.x_hovered = False

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

        # Add mouse motion tracking for hover detection
        motion_controller = Gtk.EventControllerMotion()
        motion_controller.connect('motion', self.on_mouse_motion)
        motion_controller.connect('leave', self.on_mouse_leave)
        self.drawing_area.add_controller(motion_controller)

        # Add click handler
        click_controller = Gtk.GestureClick()
        click_controller.connect('pressed', self.on_click)
        self.drawing_area.add_controller(click_controller)

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

    def get_x_center(self):
        """Get the center coordinates of the X button."""
        return (BUBBLE_SIZE - X_MARGIN - X_SIZE // 2, X_MARGIN + X_SIZE // 2)

    def on_mouse_motion(self, controller, x, y):
        """Track mouse position for hover effects."""
        self.mouse_x = x
        self.mouse_y = y
        # Check if hovering over X button
        x_cx, x_cy = self.get_x_center()
        dist = math.sqrt((x - x_cx) ** 2 + (y - x_cy) ** 2)
        self.x_hovered = dist <= X_HIT_RADIUS

    def on_mouse_leave(self, controller):
        """Reset hover state when mouse leaves."""
        self.mouse_x = -1
        self.mouse_y = -1
        self.x_hovered = False

    def on_click(self, gesture, n_press, x, y):
        """Handle clicks - check if X button was clicked."""
        x_cx, x_cy = self.get_x_center()
        dist = math.sqrt((x - x_cx) ** 2 + (y - x_cy) ** 2)
        if dist <= X_HIT_RADIUS:
            # X button clicked - send SIGTERM to parent (Iris server)
            print("X clicked - shutting down Iris", flush=True)
            os.kill(os.getppid(), signal.SIGTERM)

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

        # Draw "Iris" label below bubble
        label_text = "Iris"
        label_y = cy + radius + 18  # Position below bubble

        # Set font
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13)

        # Get text dimensions for centering
        extents = cr.text_extents(label_text)
        text_x = cx - extents.width / 2 - extents.x_bearing
        text_y = label_y

        # Draw glow effect (multiple layers)
        for offset, alpha in [(3, 0.15), (2, 0.25), (1, 0.4)]:
            cr.set_source_rgba(*NEON_CYAN, alpha)
            cr.move_to(text_x, text_y)
            cr.show_text(label_text)

        # Draw main text
        cr.set_source_rgba(*NEON_CYAN, 0.95)
        cr.move_to(text_x, text_y)
        cr.show_text(label_text)

        # Draw X button in top-right corner
        x_cx, x_cy = self.get_x_center()
        half = X_SIZE // 2

        # X opacity: subtle normally, bright when hovered
        x_alpha = 0.9 if self.x_hovered else 0.4

        # Draw X with glow when hovered
        if self.x_hovered:
            # Glow behind X
            cr.set_source_rgba(*NEON_MAGENTA, 0.4)
            cr.arc(x_cx, x_cy, X_HIT_RADIUS, 0, 2 * math.pi)
            cr.fill()

        # Draw the X lines
        cr.set_line_width(2.5 if self.x_hovered else 2.0)
        cr.set_line_cap(1)  # CAIRO_LINE_CAP_ROUND
        cr.set_source_rgba(1, 1, 1, x_alpha)

        # First line of X (top-left to bottom-right)
        cr.move_to(x_cx - half, x_cy - half)
        cr.line_to(x_cx + half, x_cy + half)
        cr.stroke()

        # Second line of X (top-right to bottom-left)
        cr.move_to(x_cx + half, x_cy - half)
        cr.line_to(x_cx - half, x_cy + half)
        cr.stroke()


def main():
    app = IrisBubble()
    app.run()


if __name__ == '__main__':
    main()
