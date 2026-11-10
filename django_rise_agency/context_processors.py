"""Contexto da experiência visual RISE, configurável por ambiente."""
from django.conf import settings


def rise_experience(request):
    return {"RISE_BRANDED": getattr(settings, "RISE_BRANDED", False)}
