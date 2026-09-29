"""Registro delle piattaforme supportate."""
from . import bsmart, digibook24, sanoma, zanichelli, hub, mylim

PLATFORMS = [
    {"key": "bsmart", "label": "bSmart", "mod": bsmart, "site": "bsmart"},
    {"key": "digibook24", "label": "digibook24 (EdiErmes)", "mod": digibook24, "site": "digibook24"},
    {"key": "sanoma", "label": "Sanoma", "mod": sanoma, "site": None},
    {"key": "zanichelli", "label": "Zanichelli", "mod": zanichelli, "site": None},
    {"key": "hub", "label": "HUB Scuola (Young + Kids)", "mod": hub, "site": None},
    {"key": "mylim", "label": "MyLim (Loescher)", "mod": mylim, "site": None},
]

BY_KEY = {p["key"]: p for p in PLATFORMS}
