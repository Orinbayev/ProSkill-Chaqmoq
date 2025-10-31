from django.urls import path
from . import views

app_name = 'store'

urlpatterns = [
    path('', views.products, name='products'),
    path('mahsulot/<int:pk>/', views.product_detail, name='product_detail'),
    path('mahsulot/<int:pk>/sorov/', views.create_request, name='create_request'),
    path('mahsulotlar/', views.product_list, name='product_list'),
    path("so'rovlar/", views.request_list, name='requests'),
    path("so'rovlar/<int:pk>/tasdiqlash/", views.request_approve, name='request_approve'),

    # CRUD (director/manager)
    path('product/create/', views.product_create, name='product_create'),
    path('product/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('product/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path("so'rovlar/<int:pk>/rad/", views.request_reject, name='request_reject'),

]
