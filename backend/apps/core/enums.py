from django.db import models


class AudienceGroup(models.TextChoices):
    GENERAL = "GENERAL", "General Public"
    ELDERLY = "ELDERLY", "Seniors & family"  # UI display label per D4
    TEENAGER = "TEENAGER", "Teenagers & Students"
    NON_TECH = "NON_TECH", "Non-Technical Users"
