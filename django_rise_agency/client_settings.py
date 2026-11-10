"""Configuração RISE por marca: avenças, voz e política de aprovação.

Só Owner/Admin da mesma organização podem alterar estes campos.
"""
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.members.models import OrgMembership
from apps.workspaces.models import Workspace

from .models import RiseBrandProfile, RiseRetainer


class RiseClientSettingsForm(forms.Form):
    period = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={"type": "month"}),
        label="Período",
    )
    posts_included = forms.IntegerField(min_value=0, max_value=10000, label="Posts contratados")
    stories_included = forms.IntegerField(min_value=0, max_value=10000, label="Stories contratadas")
    notes = forms.CharField(required=False, max_length=4000, widget=forms.Textarea, label="Observações da avença")
    voice_guidelines = forms.CharField(
        required=False,
        max_length=10000,
        widget=forms.Textarea,
        label="Orientações de comunicação da marca",
    )
    enforce_dual_approval = forms.BooleanField(required=False, label="Exigir aprovação de texto e visual")

    def clean_period(self):
        period = self.cleaned_data["period"]
        try:
            parsed = datetime.strptime(period, "%Y-%m")
        except ValueError as exc:
            raise forms.ValidationError("Indica um mês válido no formato AAAA-MM.") from exc
        canonical = parsed.strftime("%Y-%m")
        if period != canonical:
            raise forms.ValidationError("Indica um mês válido no formato AAAA-MM.")
        return canonical


def _current_period(org):
    try:
        local_now = timezone.now().astimezone(ZoneInfo(org.default_timezone or "UTC"))
    except ZoneInfoNotFoundError:
        local_now = timezone.now()
    return local_now.strftime("%Y-%m")


@login_required
@require_http_methods(["GET", "POST"])
def client_settings(request, client_id):
    org = getattr(request, "org", None)
    membership = getattr(request, "org_membership", None)
    if (
        org is None
        or membership is None
        or membership.user_id != request.user.pk
        or membership.organization_id != org.pk
        or membership.org_role not in (OrgMembership.OrgRole.OWNER, OrgMembership.OrgRole.ADMIN)
    ):
        raise Http404("Marca não disponível")
    workspace = get_object_or_404(Workspace, pk=client_id, organization_id=org.pk, is_archived=False)

    if request.method == "POST":
        form = RiseClientSettingsForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            RiseRetainer.objects.update_or_create(
                workspace=workspace,
                period=data["period"],
                defaults={
                    "posts_included": data["posts_included"],
                    "stories_included": data["stories_included"],
                    "notes": data["notes"],
                },
            )
            RiseBrandProfile.objects.update_or_create(
                workspace=workspace,
                defaults={
                    "voice_guidelines": data["voice_guidelines"],
                    "enforce_dual_approval": data["enforce_dual_approval"],
                },
            )
            messages.success(request, "Definições RISE guardadas para esta marca.")
            url = f"/rise/clientes/{workspace.pk}/avenca/?{urlencode({'period': data['period']})}"
            return redirect(url)
        selected_period = request.POST.get("period", _current_period(org))
    else:
        selected_period = request.GET.get("period", _current_period(org))
        period_form = RiseClientSettingsForm({"period": selected_period, "posts_included": 0, "stories_included": 0})
        if not period_form.is_valid():
            selected_period = _current_period(org)
        retainer = RiseRetainer.objects.filter(workspace=workspace, period=selected_period).first()
        profile = RiseBrandProfile.objects.filter(workspace=workspace).first()
        form = RiseClientSettingsForm(
            initial={
                "period": selected_period,
                "posts_included": retainer.posts_included if retainer else 0,
                "stories_included": retainer.stories_included if retainer else 0,
                "notes": retainer.notes if retainer else "",
                "voice_guidelines": profile.voice_guidelines if profile else "",
                "enforce_dual_approval": profile.enforce_dual_approval if profile else False,
            }
        )
    return render(
        request,
        "django_rise_agency/client_settings.html",
        {"workspace": workspace, "form": form, "period": selected_period},
    )
