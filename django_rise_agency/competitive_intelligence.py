"""Competitive observations with traceable evidence and per-client permissions."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .client_center import _client_access
from .models import RiseCompetitorObservation


class CompetitorObservationForm(forms.ModelForm):
    class Meta:
        model = RiseCompetitorObservation
        fields = ["competitor_name", "platform", "source_url", "observed_on", "observation", "opportunity"]
        widgets = {
            "observed_on": forms.DateInput(attrs={"type": "date"}),
            "observation": forms.Textarea(attrs={"rows": 4}),
            "opportunity": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "competitor_name": "Concorrente",
            "platform": "Canal",
            "source_url": "Fonte pública (URL)",
            "observed_on": "Data da observação",
            "observation": "O que foi observado",
            "opportunity": "Oportunidade para a marca",
        }

    def clean_observed_on(self):
        value = self.cleaned_data["observed_on"]
        if value > timezone.localdate():
            raise forms.ValidationError("A data da observação não pode ser futura.")
        return value


@login_required
@require_http_methods(["GET", "POST"])
def competitor_observations(request, client_id):
    workspace, membership, manager, editable = _client_access(request, client_id)
    if not editable:
        raise Http404("Sem acesso")
    if request.method == "POST":
        form = CompetitorObservationForm(request.POST)
        if form.is_valid():
            observation = form.save(commit=False)
            observation.workspace = workspace
            observation.created_by = request.user
            observation.save()
            messages.success(request, "Observação guardada com fonte e data.")
            return redirect(reverse("rise_agency:competitors", kwargs={"client_id": workspace.pk}))
    else:
        form = CompetitorObservationForm(initial={"observed_on": timezone.localdate()})

    observations = RiseCompetitorObservation.objects.filter(workspace=workspace).select_related("created_by")[:100]
    return render(
        request,
        "django_rise_agency/competitive_intelligence.html",
        {
            "workspace": workspace,
            "form": form,
            "observations": observations,
            "can_edit": editable,
        },
        status=400 if request.method == "POST" and form.errors else 200,
    )
