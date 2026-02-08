from django.urls import path
from . import views

app_name = 'store'

urlpatterns = [
    path('', views.products, name='products'),
    path('mahsulot/<int:pk>/', views.product_detail, name='product_detail'),
    path('mahsulot/<int:pk>/comment/', views.add_comment, name='add_comment'),
    path('comment/<int:cid>/reply/', views.reply_comment, name='reply_comment'),
    path('mahsulot/<int:pk>/sorov/', views.create_request, name='create_request'),
    path('mahsulotlar/', views.product_list, name='product_list'),
    path("so'rovlar/", views.request_list, name='requests'),
    path("so'rovlar/<int:pk>/tasdiqlash/", views.request_approve, name='request_approve'),
    path("so'rovlar/<int:pk>/tasdiqlash/", views.request_approve, name="request_approve"),
    path("so'rovlar/<int:pk>/rad_etish/", views.request_reject, name="request_reject"),

    # CRUD (director/manager)
    path('product/create/', views.product_create, name='product_create'),
    path('product/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('product/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path("so'rovlar/<int:pk>/rad/", views.request_reject, name='request_reject'),
    path('leads/', views.lead_list, name='lead_list'),
    path('leads/new/', views.lead_create, name='lead_create'),
    path('leads/<int:pk>/edit/', views.lead_edit, name='lead_edit'),
    path('leads/<int:pk>/delete/', views.lead_delete, name='lead_delete'),
    path("leads/<int:pk>/convert/", views.lead_convert, name="lead_convert"),
    
    # Lead Settings
    path('leads/settings/', views.lead_settings, name='lead_settings'),
    path('leads/settings/add/', views.lead_config_add, name='lead_config_add'),
    path('leads/settings/<str:type_code>/<int:pk>/delete/', views.lead_config_delete, name='lead_config_delete'),
    
    # Expenses (Test)
    path('expenses/', views.expenses, name='expenses'),
    path('expenses/create/', views.expense_create, name='expense_create'),
    path('expenses/category/create/', views.expense_category_create, name='expense_category_create'),
    path('expenses/<int:pk>/edit/', views.expense_edit, name='expense_edit'),
    path('expenses/<int:pk>/delete/', views.expense_delete, name='expense_delete'),
    path('expenses/<int:pk>/comment/', views.expense_comment, name='expense_comment'),
]
