from django.urls import path
from . import views

urlpatterns = [
    # Main views
    path('', views.product_list, name="product_list"),
    path('transactions/', views.transaction_list, name="transaction_list"),
    path('inventory/', views.inventory_view, name="inventory_view"),
    path('transaction/<int:transaction_id>/', views.transaction_detail, name="transaction_detail"),
    
    # API endpoints
    path('api/inventory/', views.api_inventory, name="api_inventory"),
    path('api/stock/<int:product_id>/', views.api_check_stock, name="api_check_stock"),
]