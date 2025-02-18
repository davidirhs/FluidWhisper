import os
import tkinter as tk
from recorder import AudioRecorder
from config_manager import load_config
import logging

def setup_logging(log_level):
    level = getattr(logging, log_level.upper(), logging.WARNING)
    logger = logging.getLogger()
    logger.setLevel(level)
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

 

def main():
    config = load_config()
    setup_logging(config.get('log_level', 'WARNING'))
    root = tk.Tk()
    
    # Compute absolute paths to the icon files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_png_path = os.path.join(script_dir, "assets", "FluidWhisper.png")
    icon_ico_path = os.path.join(script_dir, "assets", "FluidWhisper.ico")
    
    try:
        icon_png = tk.PhotoImage(file=icon_png_path)
        root.iconphoto(False, icon_png)    # Sets the titlebar icon
        root._icon = icon_png              # Prevents garbage collection
        root.iconbitmap(icon_ico_path)     # Sets the taskbar icon (Windows)
    except Exception as e:
        print("Error setting window icon:", e)
    
    root.withdraw()  # Hide the main window if not needed
    app = AudioRecorder(root, config)
    root.mainloop()

if __name__ == "__main__":
    main()
