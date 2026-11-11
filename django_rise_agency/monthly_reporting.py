"""RISE: monthly KPIs and real, downloadable, branded PDF reports."""

from html import escape
from io import BytesIO

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .client_center import _client_access, _period_window
from .models import RiseEditorialAssignment, RiseMonthlyReport, RiseRetainer

KPI_FIELDS = (
    ("followers", "Seguidores"),
    ("reach", "Alcance"),
    ("impressions", "Impressões"),
    ("interactions", "Interações"),
    ("link_clicks", "Cliques em links"),
    ("leads", "Leads"),
    ("conversions", "Conversões"),
    ("ad_spend", "Investimento em anúncios (€)"),
)


class RiseMonthlyReportForm(forms.ModelForm):
    class Meta:
        model = RiseMonthlyReport
        fields = [
            "followers",
            "reach",
            "impressions",
            "interactions",
            "link_clicks",
            "leads",
            "conversions",
            "ad_spend",
            "data_source",
            "summary",
            "conclusions",
            "next_steps",
        ]
        widgets = {
            "data_source": forms.TextInput(attrs={"placeholder": "Ex.: Relatório Meta Business Suite, 01 a 30/11"}),
            "summary": forms.Textarea(attrs={"rows": 4}),
            "conclusions": forms.Textarea(attrs={"rows": 5}),
            "next_steps": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        values = super().clean()
        if (
            any(values.get(key) is not None for key, _label in KPI_FIELDS)
            and not (values.get("data_source") or "").strip()
        ):
            self.add_error("data_source", "Indica a fonte dos indicadores preenchidos.")
        return values


def _report_context(workspace, period, report):
    retainer = RiseRetainer.objects.filter(workspace_id=workspace.id, period=period).first()
    previous = (
        RiseMonthlyReport.objects.filter(workspace_id=workspace.id, period__lt=period)
        .order_by("-period")
        .first()
    )
    comparison = []
    for field, label in KPI_FIELDS:
        current_value = getattr(report, field) if report else None
        previous_value = getattr(previous, field) if previous else None
        delta = current_value - previous_value if current_value is not None and previous_value is not None else None
        comparison.append({
            "label": label,
            "current": current_value,
            "previous": previous_value,
            "delta": delta,
        })
    classified = RiseEditorialAssignment.objects.filter(post__workspace_id=workspace.pk, period=period)
    counts = classified.aggregate(
        posts=Count("pk", filter=Q(format="post"), distinct=True),
        stories=Count("pk", filter=Q(format="story"), distinct=True),
        posts_published=Count("pk", filter=Q(format="post", post__platform_posts__status="published"), distinct=True),
        stories_published=Count(
            "pk", filter=Q(format="story", post__platform_posts__status="published"), distinct=True
        ),
    )
    return {
        "workspace": workspace,
        "period": period,
        "report": report,
        "previous_report": previous,
        "comparison": comparison,
        "retainer": retainer,
        "counts": counts,
        "kpis": [
            {"label": label, "value": getattr(report, field) if report is not None else None}
            for field, label in KPI_FIELDS
        ],
    }


@login_required
@require_GET
def report_detail(request, client_id):
    workspace, membership, manager, editable = _client_access(request, client_id)
    try:
        period, _start, _end = _period_window(workspace, request.GET.get("period", ""))
    except ValueError:
        return HttpResponseBadRequest("Mês inválido.")
    report = RiseMonthlyReport.objects.filter(workspace_id=workspace.pk, period=period).first()
    form = RiseMonthlyReportForm(instance=report)
    context = _report_context(workspace, period, report)
    context.update({"form": form, "can_edit": editable, "is_manager": manager})
    return render(request, "django_rise_agency/monthly_report.html", context)


@login_required
@require_POST
def report_save(request, client_id):
    workspace, _membership, _manager, editable = _client_access(request, client_id)
    if not editable:
        raise Http404("Sem acesso ao relatório.")
    try:
        period, _start, _end = _period_window(workspace, request.POST.get("period", ""))
        if not request.POST.get("period"):
            raise ValueError("Falta o mês")
    except ValueError:
        return HttpResponseBadRequest("Mês inválido.")
    report = RiseMonthlyReport.objects.filter(workspace_id=workspace.pk, period=period).first()
    form = RiseMonthlyReportForm(request.POST, instance=report)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.workspace = workspace
        obj.period = period
        obj.updated_by = request.user
        obj.save()
        messages.success(request, "KPIs e relatório guardados para este mês.")
        from urllib.parse import urlencode

        return redirect(
            reverse("rise_agency:report_detail", kwargs={"client_id": workspace.pk})
            + "?"
            + urlencode({"period": period})
        )
    context = _report_context(workspace, period, report)
    context.update({"form": form, "can_edit": editable})
    return render(request, "django_rise_agency/monthly_report.html", context, status=400)


def _pdf_paragraph(text, style):
    from reportlab.platypus import Paragraph

    return Paragraph(escape(str(text or "")).replace("\n", "<br/>"), style)


@login_required
@require_GET
def report_pdf(request, client_id):
    workspace, _membership, _manager, _editable = _client_access(request, client_id)
    try:
        period, _start, _end = _period_window(workspace, request.GET.get("period", ""))
    except ValueError:
        return HttpResponseBadRequest("Mês inválido.")
    report = RiseMonthlyReport.objects.filter(workspace_id=workspace.pk, period=period).first()
    if report is None:
        raise Http404("Guarda um relatório antes de exportar o PDF.")
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import HRFlowable, KeepTogether, SimpleDocTemplate, Spacer, Table, TableStyle

    background = colors.HexColor("#050006")
    lime = colors.HexColor("#BECC43")
    ink = colors.HexColor("#26282B")
    muted = colors.HexColor("#69706A")
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "rise_title",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=background,
        alignment=TA_LEFT,
        spaceAfter=12,
    )
    heading = ParagraphStyle(
        "rise_section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=background,
        spaceBefore=17,
        spaceAfter=8,
    )
    text_style = ParagraphStyle(
        "rise_body", parent=styles["BodyText"], fontSize=9.5, leading=15, textColor=ink, spaceAfter=8
    )
    small = ParagraphStyle(
        "rise_small", parent=styles["BodyText"], fontSize=8, leading=12, textColor=muted, spaceAfter=8
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=19 * mm,
        leftMargin=19 * mm,
        topMargin=24 * mm,
        bottomMargin=22 * mm,
        title=f"RISE | {workspace.name} | {period}",
        author="RISE Content Hub",
    )
    ctx = _report_context(workspace, period, report)
    story = [
        _pdf_paragraph("RISE  /  CONTENT HUB", heading),
        HRFlowable(width="100%", thickness=3, color=lime),
        Spacer(1, 10),
        _pdf_paragraph(f"Relatório mensal — {workspace.name}", title),
        _pdf_paragraph(f"Período: {period}  |  Origem dos indicadores: {report.data_source or 'Não indicada'}", small),
        _pdf_paragraph("Indicadores de desempenho", heading),
    ]
    rows = [[_pdf_paragraph("INDICADOR", small), _pdf_paragraph("VALOR", small)]]
    for kpi in ctx["kpis"]:
        raw = kpi["value"]
        formatted = (
            "Não disponível"
            if raw is None
            else (f"{raw:,.2f} €" if kpi["label"].startswith("Investimento") else f"{raw:,}")
        )
        rows.append([_pdf_paragraph(kpi["label"], text_style), _pdf_paragraph(formatted, text_style)])
    tbl = Table(rows, colWidths=[112 * mm, 56 * mm], hAlign="LEFT", repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F5DF")),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#E3E8DE")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([tbl, _pdf_paragraph("Produção editorial", heading)])
    contract = ctx["retainer"]
    counts = ctx["counts"]
    contract_text = (
        f"Posts classificados: {counts['posts']} / {contract.posts_included}. "
        f"Stories classificadas: {counts['stories']} / {contract.stories_included}."
        if contract
        else f"Posts classificados: {counts['posts']}. Stories classificadas: {counts['stories']}. "
        "Sem avença contratada para este mês."
    )
    story.append(_pdf_paragraph(contract_text, text_style))
    story.append(
        _pdf_paragraph(
            f"Com pelo menos um canal publicado: {counts['posts_published']} posts e {counts['stories_published']} stories.",
            text_style,
        )
    )
    for label, value in (
        ("Enquadramento e resultados", report.summary),
        ("Conclusões", report.conclusions),
        ("Próximas ações", report.next_steps),
    ):
        story.append(
            KeepTogether([_pdf_paragraph(label, heading), _pdf_paragraph(value or "Não preenchido.", text_style)])
        )
    story.append(Spacer(1, 12))
    story.append(
        _pdf_paragraph(
            "Os KPIs são declarados manualmente pela equipa e dependem da fonte identificada. "
            "Conteúdos por publicar ou não classificados não são inferidos nem duplicados por canal.",
            small,
        )
    )

    def footer(canvas, pdf_doc):
        canvas.saveState()
        canvas.setStrokeColor(lime)
        canvas.setLineWidth(2)
        canvas.line(19 * mm, 17 * mm, 191 * mm, 17 * mm)
        canvas.setFillColor(muted)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(19 * mm, 12 * mm, "RISE CONTENT HUB  ·  Direção para cada marca.")
        canvas.drawRightString(191 * mm, 12 * mm, str(pdf_doc.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    result = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    result["Content-Disposition"] = f'attachment; filename="RISE-Relatorio-{workspace.pk}-{period}.pdf"'
    result["Cache-Control"] = "private, no-store"
    return result
