"""RISE integrations: safe setup, actual provider health and on-demand AI draft generation.

Never log or render credentials, never automatically send Mailchimp campaigns,
and never claim Meta/LinkedIn OAuth works before a real provider authorization.
"""

import os
import re

import httpx
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.composer.models import Post
from apps.credentials.models import PlatformCredential, derive_is_configured
from apps.members.models import OrgMembership, WorkspaceMembership
from apps.social_accounts.models import SocialAccount

from .client_center import _client_access
from .models import RiseBrandProfile, RiseServiceCredential

NETWORKS = (
    ("facebook", "Facebook"),
    ("instagram", "Instagram via Facebook"),
    ("instagram_login", "Instagram direto"),
    ("linkedin_personal", "LinkedIn pessoal"),
    ("linkedin_company", "LinkedIn empresarial"),
)


def _agency_admin(request):
    org = getattr(request, "org", None)
    membership = getattr(request, "org_membership", None)
    if (
        org is None
        or membership is None
        or membership.user_id != request.user.pk
        or membership.organization_id != org.pk
        or membership.org_role not in (OrgMembership.OrgRole.OWNER, OrgMembership.OrgRole.ADMIN)
    ):
        raise Http404("Área restrita à administração RISE")
    return org


def _secret(org, provider):
    env_name = "RISE_OPENAI_API_KEY" if provider == "openai" else "RISE_MAILCHIMP_API_KEY"
    from_env = os.environ.get(env_name, "").strip()
    if from_env:
        return from_env
    saved = RiseServiceCredential.objects.filter(organization=org, provider=provider).first()
    return (saved.secret or "").strip() if saved else ""


def _mailchimp_dc(key, configured=""):
    if configured and re.fullmatch(r"[a-z]{2}[0-9]{1,3}", configured):
        return configured
    match = re.search(r"-([a-z]{2}[0-9]{1,3})$", key)
    return match.group(1) if match else ""


class IntegrationSecretForm(forms.Form):
    provider = forms.ChoiceField(choices=RiseServiceCredential.Provider.choices)
    secret = forms.CharField(
        max_length=512,
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
    )
    data_center = forms.CharField(max_length=12, required=False)

    def clean_data_center(self):
        value = (self.cleaned_data.get("data_center") or "").strip().lower()
        if value and not re.fullmatch(r"[a-z]{2}[0-9]{1,3}", value):
            raise forms.ValidationError("Centro de dados inválido (ex.: us21).")
        return value


class AiContentForm(forms.Form):
    topic = forms.CharField(max_length=400, label="Tema", widget=forms.TextInput)
    objective = forms.CharField(
        max_length=550,
        label="Objetivo e contexto",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    network = forms.ChoiceField(
        choices=[("linkedin", "LinkedIn"), ("facebook", "Facebook"), ("instagram", "Instagram")],
        label="Rede social",
    )


@login_required
@require_GET
def integrations(request):
    org = _agency_admin(request)
    credentials = {x.platform: x for x in PlatformCredential.objects.filter(organization=org)}
    from_env = getattr(settings, "PLATFORM_CREDENTIALS_FROM_ENV", {})
    networks = []
    for platform, label in NETWORKS:
        cred = credentials.get(platform)
        configured = bool((cred and cred.is_configured) or derive_is_configured(platform, from_env.get(platform, {})))
        networks.append(
            {
                "platform": platform,
                "label": label,
                "configured": configured,
                "connected": SocialAccount.objects.filter(
                    workspace__organization=org,
                    platform=platform,
                    connection_status=SocialAccount.ConnectionStatus.CONNECTED,
                ).count(),
                "callback_url": request.build_absolute_uri(
                    reverse("social_accounts:oauth_callback", kwargs={"platform": platform})
                ),
            }
        )
    # Show only workspaces where the signed-in user can actually manage the
    # social connection; org admin status alone does not grant workspace actions.
    account_workspaces = []
    memberships = (
        WorkspaceMembership.objects.filter(user=request.user, workspace__organization=org, workspace__is_archived=False)
        .select_related("workspace", "custom_role")
        .order_by("workspace__name")
    )
    for member in memberships:
        if member.effective_permissions.get("manage_social_accounts", False):
            account_workspaces.append(member.workspace)
    mailchimp_key = _secret(org, "mailchimp")
    openai_key = _secret(org, "openai")
    configured_dc = (
        RiseServiceCredential.objects.filter(organization=org, provider="mailchimp")
        .values_list("data_center", flat=True)
        .first()
        or ""
    )
    return render(
        request,
        "django_rise_agency/integrations.html",
        {
            "networks": networks,
            "account_workspaces": account_workspaces,
            "mailchimp_ready": bool(mailchimp_key and _mailchimp_dc(mailchimp_key, configured_dc)),
            "openai_ready": bool(openai_key),
            "has_any_workspace": org.workspaces.filter(is_archived=False).exists(),
            "mailchimp_dc": configured_dc,
            "integration_form": IntegrationSecretForm(),
        },
    )


@login_required
@require_POST
def save_integration(request):
    org = _agency_admin(request)
    form = IntegrationSecretForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Revê a configuração da integração.")
        return redirect("rise_agency:integrations")
    provider = form.cleaned_data["provider"]
    supplied = form.cleaned_data["secret"].strip()
    dc = form.cleaned_data["data_center"]
    existing = RiseServiceCredential.objects.filter(organization=org, provider=provider).first()
    if not supplied and not existing:
        messages.error(request, "Introduz uma chave de API para estabelecer a ligação.")
        return redirect("rise_agency:integrations")
    if provider == "mailchimp":
        effective = supplied or (existing.secret if existing else "")
        dc = _mailchimp_dc(effective, dc or (existing.data_center if existing else ""))
        if not dc:
            messages.error(request, "É necessário indicar o centro de dados do Mailchimp (ex.: us21).")
            return redirect("rise_agency:integrations")
    else:
        dc = ""
    if existing:
        if supplied:
            existing.secret = supplied
        existing.data_center = dc
        existing.save()
    else:
        RiseServiceCredential.objects.create(organization=org, provider=provider, secret=supplied, data_center=dc)
    messages.success(request, "Credencial guardada de forma cifrada. Testa a ligação antes de a utilizar.")
    return redirect("rise_agency:integrations")


@login_required
@require_POST
def disconnect_service(request):
    org = _agency_admin(request)
    provider = request.POST.get("provider", "")
    if provider not in RiseServiceCredential.Provider.values:
        return HttpResponseBadRequest("Integração inválida.")
    RiseServiceCredential.objects.filter(organization=org, provider=provider).delete()
    messages.success(
        request, "Credencial guardada na aplicação eliminada. Uma variável do Railway, se existir, continua ativa."
    )
    return redirect("rise_agency:integrations")


@login_required
@require_GET
def mailchimp_read(request):
    org = _agency_admin(request)
    key = _secret(org, "mailchimp")
    dc = (
        RiseServiceCredential.objects.filter(organization=org, provider="mailchimp")
        .values_list("data_center", flat=True)
        .first()
        or ""
    )
    dc = _mailchimp_dc(key, dc)
    if not key or not dc:
        messages.error(request, "Configura primeiro a API Mailchimp e o respetivo centro de dados.")
        return redirect("rise_agency:integrations")
    try:
        with httpx.Client(timeout=12) as client:
            response = client.get(
                f"https://{dc}.api.mailchimp.com/3.0/lists",
                auth=("rise-content-hub", key),
                params={"count": 25, "fields": "lists.id,lists.name,total_items"},
            )
            response.raise_for_status()
            payload = response.json()
            audiences = [
                {"id": x.get("id", ""), "name": x.get("name", "Sem nome")}
                for x in payload.get("lists", [])
                if isinstance(x, dict)
            ]
    except (httpx.HTTPError, ValueError, KeyError):
        messages.error(
            request, "O Mailchimp não autorizou a consulta. Verifica a chave, os acessos e o centro de dados."
        )
        return redirect("rise_agency:integrations")
    return render(request, "django_rise_agency/mailchimp_audiences.html", {"audiences": audiences})


@login_required
@require_GET
def ai_editor(request, client_id):
    workspace, _membership, _manager, _can_edit = _client_access(request, client_id)
    configured = bool(_secret(workspace.organization, "openai"))
    return render(
        request,
        "django_rise_agency/ai_editor.html",
        {"workspace": workspace, "configured": configured, "form": AiContentForm()},
    )


@login_required
@require_POST
def ai_generate(request, client_id):
    workspace, _membership, _manager, can_edit = _client_access(request, client_id)
    if not can_edit:
        raise Http404("Sem permissão")
    form = AiContentForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "django_rise_agency/ai_editor.html",
            {"workspace": workspace, "form": form, "configured": True},
            status=400,
        )
    key = _secret(workspace.organization, "openai")
    if not key:
        messages.error(request, "A chave de API OpenAI ainda não está configurada.")
        return redirect("rise_agency:ai_editor", client_id=client_id)
    brand = RiseBrandProfile.objects.filter(workspace=workspace).first()
    guidance = brand.voice_guidelines[:4000] if brand else ""
    topic = form.cleaned_data["topic"]
    objective = form.cleaned_data["objective"]
    network = form.cleaned_data["network"]
    # A chamada só acontece após a ação explícita do utilizador. Nunca publica automaticamente.
    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": getattr(settings, "RISE_AI_MODEL", "gpt-4o-mini"),
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "És um especialista em comunicação de marcas. Escreve em português de Portugal. "
                            "Devolve apenas a proposta de copy, sem markdown, nem introdução. "
                            "Não inventes factos, resultados ou testemunhos. "
                            f"Orientações desta marca: {guidance or 'Tom profissional e claro.'}"
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Rede: {network}. Tema: {topic}. Objetivo e contexto: {objective}. "
                        "Cria uma publicação original com CTA adequado, pronta para revisão editorial.",
                    },
                ],
                "max_tokens": 650,
            },
            timeout=25,
        )
        response.raise_for_status()
        payload = response.json()
        text_result = payload["choices"][0]["message"]["content"].strip()
        if not text_result:
            raise ValueError("Resposta vazia")
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        messages.error(request, "Não foi possível gerar o conteúdo. Verifica a configuração OpenAI e tenta novamente.")
        return redirect("rise_agency:ai_editor", client_id=client_id)
    post = Post.objects.create(
        workspace=workspace,
        author=request.user,
        title=f"IA · {topic}"[:255],
        caption=text_result[:10000],
        internal_notes=f"Rascunho assistido por IA para {network}. Validar factos, imagem e identidade antes da aprovação.",
    )
    messages.success(request, "Rascunho de texto criado. Revê-o e acrescenta o visual antes de agendar.")
    return redirect("composer:compose_edit", workspace_id=workspace.pk, post_id=post.pk)
