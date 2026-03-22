from dataclasses import dataclass
from typing import Iterable

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import (
    DemoLeadUpdateForm,
    FAQForm,
    FeatureBlockForm,
    PartnerLogoForm,
    PricingFeatureForm,
    PricingPlanForm,
    ScreenshotSectionForm,
    SiteSettingForm,
    SiteSettingHeroImageForm,
    StaticPageForm,
    SupportCardForm,
    TestimonialForm,
    VacancyForm,
)
from accounts.views import is_superadmin

from .models import (
    DemoLead,
    FAQ,
    FeatureBlock,
    PartnerLogo,
    PricingFeature,
    PricingPlan,
    ScreenshotSection,
    SiteSetting,
    StaticPage,
    SupportCard,
    Testimonial,
    Vacancy,
)


def _apply_search(queryset, query: str, search_fields: Iterable[str]):
    if not query:
        return queryset

    condition = Q()
    for field in search_fields:
        condition |= Q(**{f"{field}__icontains": query})
    return queryset.filter(condition)


def _apply_active_filter(queryset, active_raw: str):
    if active_raw == "1":
        return queryset.filter(is_active=True)
    if active_raw == "0":
        return queryset.filter(is_active=False)
    return queryset


def _paginate(request: HttpRequest, queryset, per_page: int = 15):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page"))


def _render_form_page(
    request: HttpRequest,
    *,
    template_name: str,
    form,
    page_title: str,
    section_title: str,
    cancel_url_name: str,
    object_for_preview=None,
    extra_context: dict | None = None,
) -> HttpResponse:
    context = {
        "form": form,
        "page_title": page_title,
        "section_title": section_title,
        "cancel_url": reverse(cancel_url_name),
        "object_for_preview": object_for_preview,
    }
    if extra_context:
        context.update(extra_context)
    return render(request, template_name, context)


def _render_delete_page(
    request: HttpRequest,
    *,
    template_name: str,
    object_to_delete,
    page_title: str,
    cancel_url_name: str,
):
    return render(
        request,
        template_name,
        {
            "object_to_delete": object_to_delete,
            "page_title": page_title,
            "cancel_url": reverse(cancel_url_name),
        },
    )


@dataclass
class RecentUpdate:
    title: str
    model_label: str
    updated_at: object
    url: str


@login_required
@user_passes_test(is_superadmin)
def marketing_dashboard(request: HttpRequest) -> HttpResponse:
    site_setting = SiteSetting.objects.order_by("-updated_at", "-id").first()
    counts = {
        "partner_logos": PartnerLogo.objects.count(),
        "feature_blocks": FeatureBlock.objects.count(),
        "pricing_plans": PricingPlan.objects.count(),
        "pricing_features": PricingFeature.objects.count(),
        "faqs": FAQ.objects.count(),
        "testimonials": Testimonial.objects.count(),
        "demo_leads": DemoLead.objects.count(),
        "vacancies": Vacancy.objects.count(),
        "support_cards": SupportCard.objects.count(),
        "screenshots": ScreenshotSection.objects.count(),
        "static_pages": StaticPage.objects.count(),
    }

    recent_demo_leads = DemoLead.objects.select_related("selected_plan").order_by("-created_at")[:8]

    recent_updates: list[RecentUpdate] = []
    recent_models = [
        (PartnerLogo, "Hamkor logosi", "platform_global:marketing:partner_logo_list", "name"),
        (FeatureBlock, "Imkoniyat bloki", "platform_global:marketing:feature_block_list", "title"),
        (PricingPlan, "Tarif rejasi", "platform_global:marketing:pricing_plan_list", "name"),
        (FAQ, "Ko'p so'raladigan savol", "platform_global:marketing:faq_list", "question"),
        (Testimonial, "Mijoz fikri", "platform_global:marketing:testimonial_list", "full_name"),
        (SupportCard, "Yordam kartasi", "platform_global:marketing:support_card_list", "title"),
        (Vacancy, "Vakansiya", "platform_global:marketing:vacancy_list", "title"),
        (StaticPage, "Statik sahifa", "platform_global:marketing:static_page_list", "title"),
    ]

    for model, label, list_url_name, title_attr in recent_models:
        obj = model.objects.order_by("-updated_at", "-id").first()
        if not obj:
            continue
        recent_updates.append(
            RecentUpdate(
                title=getattr(obj, title_attr, str(obj)),
                model_label=label,
                updated_at=obj.updated_at,
                url=reverse(list_url_name),
            )
        )

    recent_updates = sorted(recent_updates, key=lambda x: x.updated_at, reverse=True)[:8]

    return render(
        request,
        "marketing/superadmin/dashboard.html",
        {
            "counts": counts,
            "recent_demo_leads": recent_demo_leads,
            "recent_updates": recent_updates,
            "site_setting": site_setting,
        },
    )


@login_required
@user_passes_test(is_superadmin)
def site_settings_update(request: HttpRequest) -> HttpResponse:
    instance = SiteSetting.objects.order_by("-updated_at", "-id").first()
    if instance is None:
        instance = SiteSetting.objects.create(site_name="ChaqmoqApp", is_active=True)

    form = SiteSettingForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Sayt sozlamalari muvaffaqiyatli yangilandi.")
        return redirect("platform_global:marketing:site_settings")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/site_settings_form.html",
        form=form,
        page_title="Sayt sozlamalari",
        section_title="Marketing / Sayt sozlamalari",
        cancel_url_name="platform_global:marketing:dashboard",
        object_for_preview=instance,
    )


@login_required
@user_passes_test(is_superadmin)
def site_hero_image_update(request: HttpRequest) -> HttpResponse:
    instance = SiteSetting.objects.order_by("-updated_at", "-id").first()
    if instance is None:
        instance = SiteSetting.objects.create(site_name="ChaqmoqApp", is_active=True)

    form = SiteSettingHeroImageForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Hero rasm muvaffaqiyatli yangilandi.")
        return redirect("platform_global:marketing:site_hero_image")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/site_hero_image_form.html",
        form=form,
        page_title="Hero rasmni boshqarish",
        section_title="Marketing / Sayt sozlamalari / Hero rasm",
        cancel_url_name="platform_global:marketing:site_settings",
        object_for_preview=instance,
    )


@login_required
@user_passes_test(is_superadmin)
def partner_logo_list(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    active = request.GET.get("active", "")

    queryset = PartnerLogo.objects.all().order_by("order", "id")
    queryset = _apply_search(queryset, q, ["name"])
    queryset = _apply_active_filter(queryset, active)
    page_obj = _paginate(request, queryset)

    return render(
        request,
        "marketing/superadmin/partner_logo_list.html",
        {
            "page_obj": page_obj,
            "objects": page_obj.object_list,
            "q": q,
            "active": active,
        },
    )


@login_required
@user_passes_test(is_superadmin)
def partner_logo_create(request: HttpRequest) -> HttpResponse:
    form = PartnerLogoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Hamkor logosi qo'shildi.")
        return redirect("platform_global:marketing:partner_logo_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/partner_logo_form.html",
        form=form,
        page_title="Hamkor logosi qo'shish",
        section_title="Marketing / Hamkor logolari",
        cancel_url_name="platform_global:marketing:partner_logo_list",
    )


@login_required
@user_passes_test(is_superadmin)
def partner_logo_edit(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(PartnerLogo, pk=pk)
    form = PartnerLogoForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Hamkor logosi yangilandi.")
        return redirect("platform_global:marketing:partner_logo_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/partner_logo_form.html",
        form=form,
        page_title="Hamkor logosi tahrirlash",
        section_title="Marketing / Hamkor logolari",
        cancel_url_name="platform_global:marketing:partner_logo_list",
        object_for_preview=instance,
    )


@login_required
@user_passes_test(is_superadmin)
def partner_logo_delete(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(PartnerLogo, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "Hamkor logosi o'chirildi.")
        return redirect("platform_global:marketing:partner_logo_list")

    return _render_delete_page(
        request,
        template_name="marketing/superadmin/partner_logo_confirm_delete.html",
        object_to_delete=instance,
        page_title="Hamkor logosi o'chirish",
        cancel_url_name="platform_global:marketing:partner_logo_list",
    )


@login_required
@user_passes_test(is_superadmin)
def feature_block_list(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    active = request.GET.get("active", "")
    section = request.GET.get("section", "")

    queryset = FeatureBlock.objects.all().order_by("section", "order", "id")
    queryset = _apply_search(
        queryset,
        q,
        [
            "title",
            "title_uz",
            "title_ru",
            "title_en",
            "subtitle",
            "subtitle_uz",
            "subtitle_ru",
            "subtitle_en",
            "description",
            "description_uz",
            "description_ru",
            "description_en",
        ],
    )
    queryset = _apply_active_filter(queryset, active)
    if section:
        queryset = queryset.filter(section=section)

    page_obj = _paginate(request, queryset)
    return render(
        request,
        "marketing/superadmin/feature_block_list.html",
        {
            "page_obj": page_obj,
            "objects": page_obj.object_list,
            "q": q,
            "active": active,
            "section": section,
            "section_choices": FeatureBlock.Section.choices,
        },
    )


@login_required
@user_passes_test(is_superadmin)
def feature_block_create(request: HttpRequest) -> HttpResponse:
    form = FeatureBlockForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Imkoniyat bloki qo'shildi.")
        return redirect("platform_global:marketing:feature_block_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/feature_block_form.html",
        form=form,
        page_title="Imkoniyat bloki qo'shish",
        section_title="Marketing / Imkoniyat bloklari",
        cancel_url_name="platform_global:marketing:feature_block_list",
    )


@login_required
@user_passes_test(is_superadmin)
def feature_block_edit(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(FeatureBlock, pk=pk)
    form = FeatureBlockForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Imkoniyat bloki yangilandi.")
        return redirect("platform_global:marketing:feature_block_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/feature_block_form.html",
        form=form,
        page_title="Imkoniyat bloki tahrirlash",
        section_title="Marketing / Imkoniyat bloklari",
        cancel_url_name="platform_global:marketing:feature_block_list",
        object_for_preview=instance,
    )


@login_required
@user_passes_test(is_superadmin)
def feature_block_delete(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(FeatureBlock, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "Imkoniyat bloki o'chirildi.")
        return redirect("platform_global:marketing:feature_block_list")

    return _render_delete_page(
        request,
        template_name="marketing/superadmin/feature_block_confirm_delete.html",
        object_to_delete=instance,
        page_title="Imkoniyat bloki o'chirish",
        cancel_url_name="platform_global:marketing:feature_block_list",
    )


@login_required
@user_passes_test(is_superadmin)
def screenshot_section_list(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    active = request.GET.get("active", "")

    queryset = ScreenshotSection.objects.all().order_by("order", "id")
    queryset = _apply_search(
        queryset,
        q,
        [
            "title",
            "title_uz",
            "title_ru",
            "title_en",
            "description",
            "description_uz",
            "description_ru",
            "description_en",
        ],
    )
    queryset = _apply_active_filter(queryset, active)

    page_obj = _paginate(request, queryset)
    return render(
        request,
        "marketing/superadmin/screenshot_section_list.html",
        {
            "page_obj": page_obj,
            "objects": page_obj.object_list,
            "q": q,
            "active": active,
        },
    )


@login_required
@user_passes_test(is_superadmin)
def screenshot_section_create(request: HttpRequest) -> HttpResponse:
    form = ScreenshotSectionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Ekran ko'rinishi qo'shildi.")
        return redirect("platform_global:marketing:screenshot_section_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/screenshot_section_form.html",
        form=form,
        page_title="Ekran ko'rinishi qo'shish",
        section_title="Marketing / Ekran ko'rinishlari",
        cancel_url_name="platform_global:marketing:screenshot_section_list",
    )


@login_required
@user_passes_test(is_superadmin)
def screenshot_section_edit(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(ScreenshotSection, pk=pk)
    form = ScreenshotSectionForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Ekran ko'rinishi yangilandi.")
        return redirect("platform_global:marketing:screenshot_section_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/screenshot_section_form.html",
        form=form,
        page_title="Ekran ko'rinishi tahrirlash",
        section_title="Marketing / Ekran ko'rinishlari",
        cancel_url_name="platform_global:marketing:screenshot_section_list",
        object_for_preview=instance,
    )


@login_required
@user_passes_test(is_superadmin)
def screenshot_section_delete(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(ScreenshotSection, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "Ekran ko'rinishi o'chirildi.")
        return redirect("platform_global:marketing:screenshot_section_list")

    return _render_delete_page(
        request,
        template_name="marketing/superadmin/screenshot_section_confirm_delete.html",
        object_to_delete=instance,
        page_title="Ekran ko'rinishi o'chirish",
        cancel_url_name="platform_global:marketing:screenshot_section_list",
    )


@login_required
@user_passes_test(is_superadmin)
def pricing_plan_list(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    active = request.GET.get("active", "")
    duration = request.GET.get("duration", "")
    recommended = request.GET.get("recommended", "")

    queryset = PricingPlan.objects.prefetch_related("features").all().order_by("duration_months", "order", "id")
    queryset = _apply_search(
        queryset,
        q,
        [
            "name",
            "name_uz",
            "name_ru",
            "name_en",
            "student_range",
            "student_range_uz",
            "student_range_ru",
            "student_range_en",
            "discount_label",
            "discount_label_uz",
            "discount_label_ru",
            "discount_label_en",
            "badge_text",
            "badge_text_uz",
            "badge_text_ru",
            "badge_text_en",
        ],
    )
    queryset = _apply_active_filter(queryset, active)

    if duration:
        queryset = queryset.filter(duration_months=duration)
    if recommended == "1":
        queryset = queryset.filter(is_recommended=True)

    page_obj = _paginate(request, queryset)
    duration_values = (
        PricingPlan.objects.order_by("duration_months")
        .values_list("duration_months", flat=True)
        .distinct()
    )

    return render(
        request,
        "marketing/superadmin/pricing_plan_list.html",
        {
            "page_obj": page_obj,
            "objects": page_obj.object_list,
            "q": q,
            "active": active,
            "duration": duration,
            "recommended": recommended,
            "duration_values": duration_values,
        },
    )


@login_required
@user_passes_test(is_superadmin)
def pricing_plan_create(request: HttpRequest) -> HttpResponse:
    form = PricingPlanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tarif rejasi qo'shildi.")
        return redirect("platform_global:marketing:pricing_plan_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/pricing_plan_form.html",
        form=form,
        page_title="Tarif rejasi qo'shish",
        section_title="Marketing / Tarif rejalari",
        cancel_url_name="platform_global:marketing:pricing_plan_list",
    )


@login_required
@user_passes_test(is_superadmin)
def pricing_plan_edit(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(PricingPlan, pk=pk)
    form = PricingPlanForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tarif rejasi yangilandi.")
        return redirect("platform_global:marketing:pricing_plan_list")

    plan_features = instance.features.all().order_by("order", "id")
    return _render_form_page(
        request,
        template_name="marketing/superadmin/pricing_plan_form.html",
        form=form,
        page_title="Tarif rejasi tahrirlash",
        section_title="Marketing / Tarif rejalari",
        cancel_url_name="platform_global:marketing:pricing_plan_list",
        object_for_preview=instance,
        extra_context={"plan_features": plan_features},
    )


@login_required
@user_passes_test(is_superadmin)
def pricing_plan_delete(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(PricingPlan, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "Tarif rejasi o'chirildi.")
        return redirect("platform_global:marketing:pricing_plan_list")

    return _render_delete_page(
        request,
        template_name="marketing/superadmin/pricing_plan_confirm_delete.html",
        object_to_delete=instance,
        page_title="Tarif rejasi o'chirish",
        cancel_url_name="platform_global:marketing:pricing_plan_list",
    )


@login_required
@user_passes_test(is_superadmin)
def pricing_feature_list(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    plan_id = request.GET.get("plan", "")

    queryset = PricingFeature.objects.select_related("pricing_plan").all().order_by(
        "pricing_plan__duration_months", "pricing_plan__order", "order", "id"
    )
    queryset = _apply_search(
        queryset,
        q,
        [
            "text",
            "text_uz",
            "text_ru",
            "text_en",
            "pricing_plan__name",
            "pricing_plan__name_uz",
            "pricing_plan__name_ru",
            "pricing_plan__name_en",
            "pricing_plan__student_range",
            "pricing_plan__student_range_uz",
            "pricing_plan__student_range_ru",
            "pricing_plan__student_range_en",
        ],
    )

    if plan_id:
        queryset = queryset.filter(pricing_plan_id=plan_id)

    page_obj = _paginate(request, queryset)

    return render(
        request,
        "marketing/superadmin/pricing_feature_list.html",
        {
            "page_obj": page_obj,
            "objects": page_obj.object_list,
            "q": q,
            "plan_id": plan_id,
            "plans": PricingPlan.objects.filter(is_active=True).order_by("duration_months", "order", "id"),
        },
    )


@login_required
@user_passes_test(is_superadmin)
def pricing_feature_create(request: HttpRequest) -> HttpResponse:
    initial = {}
    plan_id = request.GET.get("plan", "")
    if plan_id:
        initial["pricing_plan"] = plan_id

    form = PricingFeatureForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tarif afzalligi qo'shildi.")
        return redirect("platform_global:marketing:pricing_feature_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/pricing_feature_form.html",
        form=form,
        page_title="Tarif afzalligi qo'shish",
        section_title="Marketing / Tarif afzalliklari",
        cancel_url_name="platform_global:marketing:pricing_feature_list",
    )


@login_required
@user_passes_test(is_superadmin)
def pricing_feature_edit(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(PricingFeature, pk=pk)
    form = PricingFeatureForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tarif afzalligi yangilandi.")
        return redirect("platform_global:marketing:pricing_feature_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/pricing_feature_form.html",
        form=form,
        page_title="Tarif afzalligi tahrirlash",
        section_title="Marketing / Tarif afzalliklari",
        cancel_url_name="platform_global:marketing:pricing_feature_list",
        object_for_preview=instance,
    )


@login_required
@user_passes_test(is_superadmin)
def pricing_feature_delete(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(PricingFeature, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "Tarif afzalligi o'chirildi.")
        return redirect("platform_global:marketing:pricing_feature_list")

    return _render_delete_page(
        request,
        template_name="marketing/superadmin/pricing_feature_confirm_delete.html",
        object_to_delete=instance,
        page_title="Tarif afzalligi o'chirish",
        cancel_url_name="platform_global:marketing:pricing_feature_list",
    )


@login_required
@user_passes_test(is_superadmin)
def testimonial_list(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    active = request.GET.get("active", "")

    queryset = Testimonial.objects.all().order_by("order", "id")
    queryset = _apply_search(
        queryset,
        q,
        [
            "full_name",
            "center_name",
            "role",
            "role_uz",
            "role_ru",
            "role_en",
            "text",
            "text_uz",
            "text_ru",
            "text_en",
        ],
    )
    queryset = _apply_active_filter(queryset, active)

    page_obj = _paginate(request, queryset)
    return render(
        request,
        "marketing/superadmin/testimonial_list.html",
        {
            "page_obj": page_obj,
            "objects": page_obj.object_list,
            "q": q,
            "active": active,
        },
    )


@login_required
@user_passes_test(is_superadmin)
def testimonial_create(request: HttpRequest) -> HttpResponse:
    form = TestimonialForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Mijoz fikri qo'shildi.")
        return redirect("platform_global:marketing:testimonial_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/testimonial_form.html",
        form=form,
        page_title="Mijoz fikri qo'shish",
        section_title="Marketing / Mijozlar fikri",
        cancel_url_name="platform_global:marketing:testimonial_list",
    )


@login_required
@user_passes_test(is_superadmin)
def testimonial_edit(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(Testimonial, pk=pk)
    form = TestimonialForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Mijoz fikri yangilandi.")
        return redirect("platform_global:marketing:testimonial_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/testimonial_form.html",
        form=form,
        page_title="Mijoz fikri tahrirlash",
        section_title="Marketing / Mijozlar fikri",
        cancel_url_name="platform_global:marketing:testimonial_list",
        object_for_preview=instance,
    )


@login_required
@user_passes_test(is_superadmin)
def testimonial_delete(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(Testimonial, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "Mijoz fikri o'chirildi.")
        return redirect("platform_global:marketing:testimonial_list")

    return _render_delete_page(
        request,
        template_name="marketing/superadmin/testimonial_confirm_delete.html",
        object_to_delete=instance,
        page_title="Mijoz fikri o'chirish",
        cancel_url_name="platform_global:marketing:testimonial_list",
    )


@login_required
@user_passes_test(is_superadmin)
def faq_list(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    active = request.GET.get("active", "")

    queryset = FAQ.objects.all().order_by("order", "id")
    queryset = _apply_search(
        queryset,
        q,
        [
            "question",
            "question_uz",
            "question_ru",
            "question_en",
            "answer",
            "answer_uz",
            "answer_ru",
            "answer_en",
        ],
    )
    queryset = _apply_active_filter(queryset, active)

    page_obj = _paginate(request, queryset)
    return render(
        request,
        "marketing/superadmin/faq_list.html",
        {
            "page_obj": page_obj,
            "objects": page_obj.object_list,
            "q": q,
            "active": active,
        },
    )


@login_required
@user_passes_test(is_superadmin)
def faq_create(request: HttpRequest) -> HttpResponse:
    form = FAQForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Savol-javob qo'shildi.")
        return redirect("platform_global:marketing:faq_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/faq_form.html",
        form=form,
        page_title="Savol-javob qo'shish",
        section_title="Marketing / Savol-javoblar",
        cancel_url_name="platform_global:marketing:faq_list",
    )


@login_required
@user_passes_test(is_superadmin)
def faq_edit(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(FAQ, pk=pk)
    form = FAQForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Savol-javob yangilandi.")
        return redirect("platform_global:marketing:faq_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/faq_form.html",
        form=form,
        page_title="Savol-javob tahrirlash",
        section_title="Marketing / Savol-javoblar",
        cancel_url_name="platform_global:marketing:faq_list",
        object_for_preview=instance,
    )


@login_required
@user_passes_test(is_superadmin)
def faq_delete(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(FAQ, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "Savol-javob o'chirildi.")
        return redirect("platform_global:marketing:faq_list")

    return _render_delete_page(
        request,
        template_name="marketing/superadmin/faq_confirm_delete.html",
        object_to_delete=instance,
        page_title="Savol-javobni o'chirish",
        cancel_url_name="platform_global:marketing:faq_list",
    )


@login_required
@user_passes_test(is_superadmin)
def support_card_list(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    active = request.GET.get("active", "")

    queryset = SupportCard.objects.all().order_by("order", "id")
    queryset = _apply_search(
        queryset,
        q,
        [
            "title",
            "title_uz",
            "title_ru",
            "title_en",
            "description",
            "description_uz",
            "description_ru",
            "description_en",
            "button_text",
            "button_text_uz",
            "button_text_ru",
            "button_text_en",
            "button_url",
        ],
    )
    queryset = _apply_active_filter(queryset, active)

    page_obj = _paginate(request, queryset)
    return render(
        request,
        "marketing/superadmin/support_card_list.html",
        {
            "page_obj": page_obj,
            "objects": page_obj.object_list,
            "q": q,
            "active": active,
        },
    )


@login_required
@user_passes_test(is_superadmin)
def support_card_create(request: HttpRequest) -> HttpResponse:
    form = SupportCardForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Yordam kartasi qo'shildi.")
        return redirect("platform_global:marketing:support_card_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/support_card_form.html",
        form=form,
        page_title="Yordam kartasi qo'shish",
        section_title="Marketing / Yordam kartalari",
        cancel_url_name="platform_global:marketing:support_card_list",
    )


@login_required
@user_passes_test(is_superadmin)
def support_card_edit(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(SupportCard, pk=pk)
    form = SupportCardForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Yordam kartasi yangilandi.")
        return redirect("platform_global:marketing:support_card_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/support_card_form.html",
        form=form,
        page_title="Yordam kartasi tahrirlash",
        section_title="Marketing / Yordam kartalari",
        cancel_url_name="platform_global:marketing:support_card_list",
        object_for_preview=instance,
    )


@login_required
@user_passes_test(is_superadmin)
def support_card_delete(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(SupportCard, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "Yordam kartasi o'chirildi.")
        return redirect("platform_global:marketing:support_card_list")

    return _render_delete_page(
        request,
        template_name="marketing/superadmin/support_card_confirm_delete.html",
        object_to_delete=instance,
        page_title="Yordam kartasi o'chirish",
        cancel_url_name="platform_global:marketing:support_card_list",
    )


@login_required
@user_passes_test(is_superadmin)
def vacancy_list(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    active = request.GET.get("active", "")
    employment = request.GET.get("employment", "")

    queryset = Vacancy.objects.all().order_by("order", "id")
    queryset = _apply_search(
        queryset,
        q,
        [
            "title",
            "title_uz",
            "title_ru",
            "title_en",
            "city",
            "department",
            "department_uz",
            "department_ru",
            "department_en",
            "description",
            "description_uz",
            "description_ru",
            "description_en",
            "requirements",
            "requirements_uz",
            "requirements_ru",
            "requirements_en",
            "responsibilities",
            "responsibilities_uz",
            "responsibilities_ru",
            "responsibilities_en",
        ],
    )
    queryset = _apply_active_filter(queryset, active)
    if employment:
        queryset = queryset.filter(employment_type=employment)

    page_obj = _paginate(request, queryset)
    return render(
        request,
        "marketing/superadmin/vacancy_list.html",
        {
            "page_obj": page_obj,
            "objects": page_obj.object_list,
            "q": q,
            "active": active,
            "employment": employment,
            "employment_choices": Vacancy.EmploymentType.choices,
        },
    )


@login_required
@user_passes_test(is_superadmin)
def vacancy_create(request: HttpRequest) -> HttpResponse:
    form = VacancyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Vakansiya qo'shildi.")
        return redirect("platform_global:marketing:vacancy_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/vacancy_form.html",
        form=form,
        page_title="Vakansiya qo'shish",
        section_title="Marketing / Vakansiyalar",
        cancel_url_name="platform_global:marketing:vacancy_list",
    )


@login_required
@user_passes_test(is_superadmin)
def vacancy_edit(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(Vacancy, pk=pk)
    form = VacancyForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Vakansiya yangilandi.")
        return redirect("platform_global:marketing:vacancy_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/vacancy_form.html",
        form=form,
        page_title="Vakansiya tahrirlash",
        section_title="Marketing / Vakansiyalar",
        cancel_url_name="platform_global:marketing:vacancy_list",
        object_for_preview=instance,
    )


@login_required
@user_passes_test(is_superadmin)
def vacancy_delete(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(Vacancy, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "Vakansiya o'chirildi.")
        return redirect("platform_global:marketing:vacancy_list")

    return _render_delete_page(
        request,
        template_name="marketing/superadmin/vacancy_confirm_delete.html",
        object_to_delete=instance,
        page_title="Vakansiya o'chirish",
        cancel_url_name="platform_global:marketing:vacancy_list",
    )


@login_required
@user_passes_test(is_superadmin)
def static_page_list(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    active = request.GET.get("active", "")

    queryset = StaticPage.objects.all().order_by("key", "id")
    queryset = _apply_search(
        queryset,
        q,
        [
            "key",
            "title",
            "title_uz",
            "title_ru",
            "title_en",
            "content",
            "content_uz",
            "content_ru",
            "content_en",
        ],
    )
    queryset = _apply_active_filter(queryset, active)

    page_obj = _paginate(request, queryset)
    return render(
        request,
        "marketing/superadmin/static_page_list.html",
        {
            "page_obj": page_obj,
            "objects": page_obj.object_list,
            "q": q,
            "active": active,
        },
    )


@login_required
@user_passes_test(is_superadmin)
def static_page_create(request: HttpRequest) -> HttpResponse:
    form = StaticPageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Statik sahifa qo'shildi.")
        return redirect("platform_global:marketing:static_page_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/static_page_form.html",
        form=form,
        page_title="Statik sahifa qo'shish",
        section_title="Marketing / Statik sahifalar",
        cancel_url_name="platform_global:marketing:static_page_list",
    )


@login_required
@user_passes_test(is_superadmin)
def static_page_edit(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(StaticPage, pk=pk)
    form = StaticPageForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Statik sahifa yangilandi.")
        return redirect("platform_global:marketing:static_page_list")

    return _render_form_page(
        request,
        template_name="marketing/superadmin/static_page_form.html",
        form=form,
        page_title="Statik sahifa tahrirlash",
        section_title="Marketing / Statik sahifalar",
        cancel_url_name="platform_global:marketing:static_page_list",
        object_for_preview=instance,
    )


@login_required
@user_passes_test(is_superadmin)
def static_page_delete(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(StaticPage, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "Statik sahifa o'chirildi.")
        return redirect("platform_global:marketing:static_page_list")

    return _render_delete_page(
        request,
        template_name="marketing/superadmin/static_page_confirm_delete.html",
        object_to_delete=instance,
        page_title="Statik sahifa o'chirish",
        cancel_url_name="platform_global:marketing:static_page_list",
    )


@login_required
@user_passes_test(is_superadmin)
def demo_lead_list(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    contacted = request.GET.get("contacted", "")
    plan_id = request.GET.get("plan", "")

    queryset = DemoLead.objects.select_related("selected_plan").all().order_by("-created_at")
    queryset = _apply_search(queryset, q, ["full_name", "center_name", "phone", "note"])

    if contacted == "1":
        queryset = queryset.filter(is_contacted=True)
    elif contacted == "0":
        queryset = queryset.filter(is_contacted=False)

    if plan_id:
        queryset = queryset.filter(selected_plan_id=plan_id)

    page_obj = _paginate(request, queryset)

    return render(
        request,
        "marketing/superadmin/demo_lead_list.html",
        {
            "page_obj": page_obj,
            "objects": page_obj.object_list,
            "q": q,
            "contacted": contacted,
            "plan_id": plan_id,
            "plans": PricingPlan.objects.filter(is_active=True).order_by("duration_months", "order"),
        },
    )


@login_required
@user_passes_test(is_superadmin)
def demo_lead_detail(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(DemoLead.objects.select_related("selected_plan"), pk=pk)
    form = DemoLeadUpdateForm(request.POST or None, instance=instance)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Demo so'rovi ma'lumotlari yangilandi.")
        return redirect("platform_global:marketing:demo_lead_detail", pk=instance.pk)

    return render(
        request,
        "marketing/superadmin/demo_lead_detail.html",
        {
            "lead": instance,
            "form": form,
            "page_title": f"Demo so'rovi: {instance.full_name}",
            "back_url": reverse("platform_global:marketing:demo_lead_list"),
        },
    )


@login_required
@user_passes_test(is_superadmin)
def demo_lead_delete(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(DemoLead, pk=pk)
    if request.method == "POST":
        instance.delete()
        messages.success(request, "Demo so'rovi o'chirildi.")
        return redirect("platform_global:marketing:demo_lead_list")

    return _render_delete_page(
        request,
        template_name="marketing/superadmin/demo_lead_confirm_delete.html",
        object_to_delete=instance,
        page_title="Demo so'rovini o'chirish",
        cancel_url_name="platform_global:marketing:demo_lead_list",
    )


def _toggle_active_object(request: HttpRequest, model, pk: int, redirect_name: str):
    instance = get_object_or_404(model, pk=pk)
    instance.is_active = not instance.is_active
    instance.save(update_fields=["is_active"])
    messages.success(request, "Holat yangilandi.")
    next_url = request.POST.get("next") or reverse(redirect_name)
    return redirect(next_url)


def _move_order_object(request: HttpRequest, model, pk: int, direction: str, redirect_name: str, group_field: str | None = None):
    instance = get_object_or_404(model, pk=pk)
    current_order = getattr(instance, "order", None)
    if current_order is None:
        messages.error(request, "Bu modelda order maydoni topilmadi.")
        next_url = request.POST.get("next") or reverse(redirect_name)
        return redirect(next_url)

    filters = {}
    if group_field:
        filters[group_field] = getattr(instance, group_field)

    if direction == "up":
        target = model.objects.filter(order__lt=current_order, **filters).order_by("-order", "-id").first()
    else:
        target = model.objects.filter(order__gt=current_order, **filters).order_by("order", "id").first()

    if target:
        target_order = target.order
        target.order = current_order
        target.save(update_fields=["order"])

        instance.order = target_order
        instance.save(update_fields=["order"])
        messages.success(request, "Tartib yangilandi.")

    next_url = request.POST.get("next") or reverse(redirect_name)
    return redirect(next_url)


@login_required
@user_passes_test(is_superadmin)
@require_POST
def partner_logo_toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    return _toggle_active_object(request, PartnerLogo, pk, "platform_global:marketing:partner_logo_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def partner_logo_move_up(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, PartnerLogo, pk, "up", "platform_global:marketing:partner_logo_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def partner_logo_move_down(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, PartnerLogo, pk, "down", "platform_global:marketing:partner_logo_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def feature_block_toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    return _toggle_active_object(request, FeatureBlock, pk, "platform_global:marketing:feature_block_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def feature_block_move_up(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, FeatureBlock, pk, "up", "platform_global:marketing:feature_block_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def feature_block_move_down(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, FeatureBlock, pk, "down", "platform_global:marketing:feature_block_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def screenshot_section_toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    return _toggle_active_object(request, ScreenshotSection, pk, "platform_global:marketing:screenshot_section_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def screenshot_section_move_up(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, ScreenshotSection, pk, "up", "platform_global:marketing:screenshot_section_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def screenshot_section_move_down(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, ScreenshotSection, pk, "down", "platform_global:marketing:screenshot_section_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def pricing_plan_toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    return _toggle_active_object(request, PricingPlan, pk, "platform_global:marketing:pricing_plan_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def pricing_plan_move_up(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, PricingPlan, pk, "up", "platform_global:marketing:pricing_plan_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def pricing_plan_move_down(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, PricingPlan, pk, "down", "platform_global:marketing:pricing_plan_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def pricing_feature_move_up(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(
        request,
        PricingFeature,
        pk,
        "up",
        "platform_global:marketing:pricing_feature_list",
        group_field="pricing_plan",
    )


@login_required
@user_passes_test(is_superadmin)
@require_POST
def pricing_feature_move_down(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(
        request,
        PricingFeature,
        pk,
        "down",
        "platform_global:marketing:pricing_feature_list",
        group_field="pricing_plan",
    )


@login_required
@user_passes_test(is_superadmin)
@require_POST
def testimonial_toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    return _toggle_active_object(request, Testimonial, pk, "platform_global:marketing:testimonial_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def testimonial_move_up(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, Testimonial, pk, "up", "platform_global:marketing:testimonial_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def testimonial_move_down(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, Testimonial, pk, "down", "platform_global:marketing:testimonial_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def faq_toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    return _toggle_active_object(request, FAQ, pk, "platform_global:marketing:faq_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def faq_move_up(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, FAQ, pk, "up", "platform_global:marketing:faq_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def faq_move_down(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, FAQ, pk, "down", "platform_global:marketing:faq_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def support_card_toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    return _toggle_active_object(request, SupportCard, pk, "platform_global:marketing:support_card_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def support_card_move_up(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, SupportCard, pk, "up", "platform_global:marketing:support_card_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def support_card_move_down(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, SupportCard, pk, "down", "platform_global:marketing:support_card_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def vacancy_toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    return _toggle_active_object(request, Vacancy, pk, "platform_global:marketing:vacancy_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def vacancy_move_up(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, Vacancy, pk, "up", "platform_global:marketing:vacancy_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def vacancy_move_down(request: HttpRequest, pk: int) -> HttpResponse:
    return _move_order_object(request, Vacancy, pk, "down", "platform_global:marketing:vacancy_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def static_page_toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    return _toggle_active_object(request, StaticPage, pk, "platform_global:marketing:static_page_list")


@login_required
@user_passes_test(is_superadmin)
@require_POST
def demo_lead_toggle_contacted(request: HttpRequest, pk: int) -> HttpResponse:
    instance = get_object_or_404(DemoLead, pk=pk)
    instance.is_contacted = not instance.is_contacted
    instance.save(update_fields=["is_contacted"])
    messages.success(request, "Demo so'rovi bog'lanish holati yangilandi.")

    next_url = request.POST.get("next") or reverse("platform_global:marketing:demo_lead_list")
    return redirect(next_url)
