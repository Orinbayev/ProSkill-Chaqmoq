from django.urls import path

from . import views_superadmin as views

app_name = "marketing"

urlpatterns = [
    path("", views.marketing_dashboard, name="dashboard"),
    path("settings/", views.site_settings_update, name="site_settings"),
    path("settings/hero-image/", views.site_hero_image_update, name="site_hero_image"),

    path("partner-logos/", views.partner_logo_list, name="partner_logo_list"),
    path("partner-logos/create/", views.partner_logo_create, name="partner_logo_create"),
    path("partner-logos/<int:pk>/edit/", views.partner_logo_edit, name="partner_logo_edit"),
    path("partner-logos/<int:pk>/delete/", views.partner_logo_delete, name="partner_logo_delete"),
    path("partner-logos/<int:pk>/toggle-active/", views.partner_logo_toggle_active, name="partner_logo_toggle_active"),
    path("partner-logos/<int:pk>/move-up/", views.partner_logo_move_up, name="partner_logo_move_up"),
    path("partner-logos/<int:pk>/move-down/", views.partner_logo_move_down, name="partner_logo_move_down"),

    path("feature-blocks/", views.feature_block_list, name="feature_block_list"),
    path("feature-blocks/create/", views.feature_block_create, name="feature_block_create"),
    path("feature-blocks/<int:pk>/edit/", views.feature_block_edit, name="feature_block_edit"),
    path("feature-blocks/<int:pk>/delete/", views.feature_block_delete, name="feature_block_delete"),
    path("feature-blocks/<int:pk>/toggle-active/", views.feature_block_toggle_active, name="feature_block_toggle_active"),
    path("feature-blocks/<int:pk>/move-up/", views.feature_block_move_up, name="feature_block_move_up"),
    path("feature-blocks/<int:pk>/move-down/", views.feature_block_move_down, name="feature_block_move_down"),

    path("screenshot-sections/", views.screenshot_section_list, name="screenshot_section_list"),
    path("screenshot-sections/create/", views.screenshot_section_create, name="screenshot_section_create"),
    path("screenshot-sections/<int:pk>/edit/", views.screenshot_section_edit, name="screenshot_section_edit"),
    path("screenshot-sections/<int:pk>/delete/", views.screenshot_section_delete, name="screenshot_section_delete"),
    path("screenshot-sections/<int:pk>/toggle-active/", views.screenshot_section_toggle_active, name="screenshot_section_toggle_active"),
    path("screenshot-sections/<int:pk>/move-up/", views.screenshot_section_move_up, name="screenshot_section_move_up"),
    path("screenshot-sections/<int:pk>/move-down/", views.screenshot_section_move_down, name="screenshot_section_move_down"),

    path("pricing-plans/", views.pricing_plan_list, name="pricing_plan_list"),
    path("pricing-plans/import/", views.pricing_plan_import, name="pricing_plan_import"),
    path("pricing-plans/export/", views.pricing_plan_export, name="pricing_plan_export"),
    path("pricing-plans/template/excel/", views.pricing_plan_template_excel, name="pricing_plan_template_excel"),
    path("pricing-plans/template/json/", views.pricing_plan_template_json, name="pricing_plan_template_json"),
    path("pricing-plans/create/", views.pricing_plan_create, name="pricing_plan_create"),
    path("pricing-plans/<int:pk>/edit/", views.pricing_plan_edit, name="pricing_plan_edit"),
    path("pricing-plans/<int:pk>/delete/", views.pricing_plan_delete, name="pricing_plan_delete"),
    path("pricing-plans/<int:pk>/toggle-active/", views.pricing_plan_toggle_active, name="pricing_plan_toggle_active"),
    path("pricing-plans/<int:pk>/move-up/", views.pricing_plan_move_up, name="pricing_plan_move_up"),
    path("pricing-plans/<int:pk>/move-down/", views.pricing_plan_move_down, name="pricing_plan_move_down"),

    path("pricing-features/", views.pricing_feature_list, name="pricing_feature_list"),
    path("pricing-features/create/", views.pricing_feature_create, name="pricing_feature_create"),
    path("pricing-features/<int:pk>/edit/", views.pricing_feature_edit, name="pricing_feature_edit"),
    path("pricing-features/<int:pk>/delete/", views.pricing_feature_delete, name="pricing_feature_delete"),
    path("pricing-features/<int:pk>/move-up/", views.pricing_feature_move_up, name="pricing_feature_move_up"),
    path("pricing-features/<int:pk>/move-down/", views.pricing_feature_move_down, name="pricing_feature_move_down"),

    path("testimonials/", views.testimonial_list, name="testimonial_list"),
    path("testimonials/create/", views.testimonial_create, name="testimonial_create"),
    path("testimonials/<int:pk>/edit/", views.testimonial_edit, name="testimonial_edit"),
    path("testimonials/<int:pk>/delete/", views.testimonial_delete, name="testimonial_delete"),
    path("testimonials/<int:pk>/toggle-active/", views.testimonial_toggle_active, name="testimonial_toggle_active"),
    path("testimonials/<int:pk>/move-up/", views.testimonial_move_up, name="testimonial_move_up"),
    path("testimonials/<int:pk>/move-down/", views.testimonial_move_down, name="testimonial_move_down"),

    path("faqs/", views.faq_list, name="faq_list"),
    path("faqs/create/", views.faq_create, name="faq_create"),
    path("faqs/<int:pk>/edit/", views.faq_edit, name="faq_edit"),
    path("faqs/<int:pk>/delete/", views.faq_delete, name="faq_delete"),
    path("faqs/<int:pk>/toggle-active/", views.faq_toggle_active, name="faq_toggle_active"),
    path("faqs/<int:pk>/move-up/", views.faq_move_up, name="faq_move_up"),
    path("faqs/<int:pk>/move-down/", views.faq_move_down, name="faq_move_down"),

    path("support-cards/", views.support_card_list, name="support_card_list"),
    path("support-cards/create/", views.support_card_create, name="support_card_create"),
    path("support-cards/<int:pk>/edit/", views.support_card_edit, name="support_card_edit"),
    path("support-cards/<int:pk>/delete/", views.support_card_delete, name="support_card_delete"),
    path("support-cards/<int:pk>/toggle-active/", views.support_card_toggle_active, name="support_card_toggle_active"),
    path("support-cards/<int:pk>/move-up/", views.support_card_move_up, name="support_card_move_up"),
    path("support-cards/<int:pk>/move-down/", views.support_card_move_down, name="support_card_move_down"),

    path("vacancies/", views.vacancy_list, name="vacancy_list"),
    path("vacancies/create/", views.vacancy_create, name="vacancy_create"),
    path("vacancies/<int:pk>/edit/", views.vacancy_edit, name="vacancy_edit"),
    path("vacancies/<int:pk>/delete/", views.vacancy_delete, name="vacancy_delete"),
    path("vacancies/<int:pk>/toggle-active/", views.vacancy_toggle_active, name="vacancy_toggle_active"),
    path("vacancies/<int:pk>/move-up/", views.vacancy_move_up, name="vacancy_move_up"),
    path("vacancies/<int:pk>/move-down/", views.vacancy_move_down, name="vacancy_move_down"),

    path("static-pages/", views.static_page_list, name="static_page_list"),
    path("static-pages/create/", views.static_page_create, name="static_page_create"),
    path("static-pages/<int:pk>/edit/", views.static_page_edit, name="static_page_edit"),
    path("static-pages/<int:pk>/delete/", views.static_page_delete, name="static_page_delete"),
    path("static-pages/<int:pk>/toggle-active/", views.static_page_toggle_active, name="static_page_toggle_active"),

    # === Tarif v2 — Bosqich 4: PlanFeature CRUD ===
    path("features/", views.feature_list, name="feature_list"),
    path("features/create/", views.feature_create, name="feature_create"),
    path("features/<int:pk>/edit/", views.feature_edit, name="feature_edit"),
    path("features/<int:pk>/delete/", views.feature_delete, name="feature_delete"),
    path("features/<int:pk>/toggle-active/", views.feature_toggle_active, name="feature_toggle_active"),

    # === Tarif v2 — Bosqich 4: Markaz feature override ===
    path("centers/", views.center_list_for_features, name="center_list_for_features"),
    path("centers/<int:pk>/features/", views.center_feature_overrides, name="center_feature_overrides"),
    path("centers/<int:pk>/features/toggle/", views.center_feature_toggle, name="center_feature_toggle"),

    path("demo-leads/", views.demo_lead_list, name="demo_lead_list"),
    path("demo-leads/<int:pk>/", views.demo_lead_detail, name="demo_lead_detail"),
    path("demo-leads/<int:pk>/delete/", views.demo_lead_delete, name="demo_lead_delete"),
    path("demo-leads/<int:pk>/toggle-contacted/", views.demo_lead_toggle_contacted, name="demo_lead_toggle_contacted"),
]
