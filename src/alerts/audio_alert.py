"""Audio alert module for HIGH/CRITICAL collision threats."""

import platform
import subprocess


def play_alert(risk_level: str):
    """Play a beep sound based on risk level."""
    if risk_level not in ("HIGH", "CRITICAL"):
        return
    try:
        if platform.system() == "Windows":
            import winsound
            freq = 1000 if risk_level == "CRITICAL" else 800
            duration = 500 if risk_level == "CRITICAL" else 300
            winsound.Beep(freq, duration)
        elif platform.system() == "Darwin":
            subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"],
                         capture_output=True, timeout=2)
        else:
            subprocess.run(["paplay",
                          "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"],
                         capture_output=True, timeout=2)
    except Exception:
        pass  # Silent fail if audio not available
