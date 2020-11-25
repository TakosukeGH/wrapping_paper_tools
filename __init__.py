bl_info= {
    "name": "Wrapping Paper Tools",
    "author": "Takosuke",
    "version": (0, 0, 1),
    "blender": (2, 80, 0),
    "location": "View3D > Tools Panel",
    "description": "Wrapping Paper Tools.",
    "support": "COMMUNITY",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": 'Import-Export'}

if "bpy" in locals():
    import importlib
    if "properties" in locals():
        importlib.reload(properties)
    if "exporter" in locals():
        importlib.reload(exporter)

import bpy
import logging
  
from . import (
    properties,
    exporter,
)

logger = logging.getLogger("wrapping_paper_tools")

if not logger.handlers:
    hdlr = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)-7s %(asctime)s %(message)s (%(module)s %(funcName)s)", datefmt="%H:%M:%S")
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.DEBUG) # DEBUG, INFO, WARNING, ERROR, CRITICAL

logger.debug("init logger") # debug, info, warning, error, critical

def register():
    properties.register()
    exporter.register()

def unregister():
    properties.unregister()
    exporter.unregister()

if __name__ == "__main__":
    register()
