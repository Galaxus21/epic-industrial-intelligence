"""Display labels for sensor keys: "vibration_de" becomes "Vibration DE".

The frontend formats keys the same way (formatSensorLabel in frontend/src/lib/sensorDisplay.ts);
keep the two acronym lists identical.
"""

sensorAcronyms = frozenset({"DE", "NDE", "DP", "RPM", "HP", "LP", "CW", "MW", "PH"})


def sensorLabel(key: str) -> str:
    words = key.split("_")
    return " ".join(word.upper() if word.upper() in sensorAcronyms else word.capitalize() for word in words)
