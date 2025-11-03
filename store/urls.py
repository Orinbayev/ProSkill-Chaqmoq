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

]
