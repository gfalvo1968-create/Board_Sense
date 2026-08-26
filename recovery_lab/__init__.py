"""Board Sense Recovery Lab.

Routes recognized scrap/components into recovery families and combines safe
recovery guidance, labor/time value, and Scrap Radar market intelligence.
"""

from recovery_lab.registry import RECOVERY_LABS, get_lab

__all__ = ["RECOVERY_LABS", "get_lab"]
