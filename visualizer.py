import tkinter as tk

class WaveformFrame(tk.Frame):
    def __init__(self, master, width=300, height=80, wave_color="white", config=None):
        super().__init__(master, width=width, height=height, bg="black")
        self.width = width
        self.height = height
        self.wave_color = wave_color
        self.config_obj = config

        # Set up the canvas with a black background.
        self.canvas = tk.Canvas(self, width=self.width, height=self.height, bg="black", highlightthickness=0)
        self.canvas.pack()

        # List to store amplitude history for waveform drawing
        self.amplitudes = [0] * self.width

        self._running = True
        self.fading_out = False  # Flag for fade-out effect

        # Start the update loop (roughly 20 fps)
        self.after_id = self.after(50, self._draw_waveform)

    def push_amplitude(self, amplitude):
        """Append a new amplitude value and maintain history length equal to the widget width."""
        self.amplitudes.append(amplitude)
        if len(self.amplitudes) > self.width:
            self.amplitudes.pop(0)

    def _draw_waveform(self):
        if not self._running:
            return
        try:
            mid_y = self.height // 2
            points = []
            # Use amplitude history to create waveform points
            for x, amp in enumerate(self.amplitudes[-self.width:]):
                scaled_amp = min(amp / 0.3, 1.0)  # Normalize amplitude (0.3 as near-max value)
                y = mid_y - scaled_amp * (self.height / 2)
                points.append((x, y))
            if len(points) > 1:
                flat_points = [coord for point in points for coord in point]
                self.canvas.delete("wave")
                self.canvas.create_line(*flat_points, fill=self.wave_color, width=2, tag="wave")
            # Fade-out effect handling
            if self.fading_out:
                self.amplitudes = [amp * 0.9 for amp in self.amplitudes]
                if max(self.amplitudes) < 0.01:
                    self._running = False
                    self.destroy()
                    return
            self.after_id = self.after(50, self._draw_waveform)
        except tk.TclError:
            # If the widget has been destroyed, ignore further updates.
            return

    def stop(self):
        """Trigger fade-out effect and cancel pending callbacks."""
        self.fading_out = True
        if self.after_id is not None:
            try:
                self.after_cancel(self.after_id)
            except Exception as e:
                print("after_cancel error:", e)
            self.after_id = None 