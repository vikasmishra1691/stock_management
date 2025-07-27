from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from collections import defaultdict
from .models import ProdMast, StockTrans, StockDetail
from .forms import ProductForm, StockTransForm, StockDetailForm, StockDetailFormSet

def product_list(request):
    """Display and handle product creation"""
    products = ProdMast.objects.all().order_by('prod_name')
    
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            try:
                product = form.save()
                messages.success(request, f'Product "{product.prod_name}" added successfully!')
                return redirect('product_list')
            except Exception as e:
                messages.error(request, f'Error saving product: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ProductForm()
    
    return render(request, "stock_management/products.html", {
        "form": form,
        "products": products
    })


def transaction_list(request):
    """Display and handle stock transactions"""
    if request.method == "POST":
        transaction_form = StockTransForm(request.POST)
        detail_formset = StockDetailFormSet(request.POST)
        
        if transaction_form.is_valid() and detail_formset.is_valid():
            try:
                with transaction.atomic():  # Ensure data consistency
                    # Save the transaction first
                    stock_transaction = transaction_form.save()
                    
                    # Track products to prevent duplicates in same transaction
                    products_in_transaction = set()
                    
                    # Validate stock for OUT transactions before saving details
                    if stock_transaction.transaction_type == 'OUT':
                        for detail_form in detail_formset:
                            if detail_form.cleaned_data and not detail_form.cleaned_data.get('DELETE', False):
                                product = detail_form.cleaned_data['product']
                                quantity = detail_form.cleaned_data['quantity']
                                
                                # Check for duplicate products in same transaction
                                if product in products_in_transaction:
                                    messages.error(request, f'Duplicate product "{product.prod_name}" in transaction.')
                                    raise ValidationError("Duplicate products not allowed")
                                
                                products_in_transaction.add(product)
                                
                                # Create temporary detail instance for stock validation
                                detail = detail_form.save(commit=False)
                                detail.transaction = stock_transaction
                                
                                # Validate stock availability using the separate method
                                detail.validate_stock_availability(stock_transaction.transaction_type)
                    else:
                        # For IN transactions, just check for duplicates
                        for detail_form in detail_formset:
                            if detail_form.cleaned_data and not detail_form.cleaned_data.get('DELETE', False):
                                product = detail_form.cleaned_data['product']
                                
                                # Check for duplicate products in same transaction
                                if product in products_in_transaction:
                                    messages.error(request, f'Duplicate product "{product.prod_name}" in transaction.')
                                    raise ValidationError("Duplicate products not allowed")
                                
                                products_in_transaction.add(product)
                    
                    # If validation passes, save all details
                    for detail_form in detail_formset:
                        if detail_form.cleaned_data and not detail_form.cleaned_data.get('DELETE', False):
                            detail = detail_form.save(commit=False)
                            detail.transaction = stock_transaction
                            detail.save()
                    
                    if not products_in_transaction:
                        messages.error(request, 'Transaction must contain at least one product.')
                        raise ValidationError("Empty transaction")
                    
                    messages.success(
                        request, 
                        f'{stock_transaction.get_transaction_type_display()} transaction created successfully with {len(products_in_transaction)} items!'
                    )
                    return redirect('transaction_list')
                    
            except ValidationError as e:
                messages.error(request, f'Validation error: {str(e)}')
            except Exception as e:
                messages.error(request, f'Error creating transaction: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors in the form.')
    else:
        transaction_form = StockTransForm()
        detail_formset = StockDetailFormSet()

    transactions = StockTrans.objects.all().prefetch_related('stockdetail_set__product').order_by('-created_at')
    
    return render(request, 'stock_management/transactions.html', {
        'transaction_form': transaction_form,
        'detail_forms': detail_formset,
        'transactions': transactions
    })


def inventory_view(request):
    """Display current inventory with stock levels"""
    inventory = defaultdict(int)
    details = StockDetail.objects.select_related('transaction', 'product')

    for detail in details:
        qty = detail.quantity
        if detail.transaction.transaction_type == 'OUT':
            qty = -qty
        inventory[detail.product] += qty

    # Convert to list for easier template handling and add stock status
    inventory_list = []
    for product, quantity in inventory.items():
        status = 'good'
        if quantity <= 0:
            status = 'out_of_stock'
        elif quantity <= 10:  # Low stock threshold
            status = 'low_stock'
        
        inventory_list.append({
            'product': product,
            'quantity': quantity,
            'status': status
        })
    
    # Sort by product name
    inventory_list.sort(key=lambda x: x['product'].prod_name)
    
    return render(request, 'stock_management/inventory.html', {
        'inventory_list': inventory_list
    })

# API endpoints for future integrations
@require_http_methods(["GET"])
def api_inventory(request):
    """API endpoint to get current inventory as JSON"""
    inventory = defaultdict(int)
    details = StockDetail.objects.select_related('transaction', 'product')

    for detail in details:
        qty = detail.quantity
        if detail.transaction.transaction_type == 'OUT':
            qty = -qty
        inventory[detail.product] += qty

    # Convert to JSON-serializable format
    inventory_data = []
    for product, quantity in inventory.items():
        inventory_data.append({
            'product_id': product.id,
            'product_name': product.prod_name,
            'quantity': quantity,
            'status': 'out_of_stock' if quantity <= 0 else 'low_stock' if quantity <= 10 else 'good'
        })

    return JsonResponse({
        'status': 'success',
        'data': inventory_data,
        'total_products': len(inventory_data)
    })

@require_http_methods(["GET"])
def api_check_stock(request, product_id):
    """API endpoint to check stock for a specific product"""
    try:
        product = get_object_or_404(ProdMast, id=product_id)
        
        inventory = defaultdict(int)
        details = StockDetail.objects.filter(product=product).select_related('transaction')

        for detail in details:
            qty = detail.quantity
            if detail.transaction.transaction_type == 'OUT':
                qty = -qty
            inventory[product] += qty

        current_stock = inventory[product]
        
        return JsonResponse({
            'status': 'success',
            'product_id': product.id,
            'product_name': product.prod_name,
            'current_stock': current_stock,
            'stock_status': 'out_of_stock' if current_stock <= 0 else 'low_stock' if current_stock <= 10 else 'good'
        })
    
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

def transaction_detail(request, transaction_id):
    """View details of a specific transaction"""
    transaction_obj = get_object_or_404(StockTrans, id=transaction_id)
    details = StockDetail.objects.filter(transaction=transaction_obj).select_related('product')
    
    return render(request, 'stock_management/transaction_detail.html', {
        'transaction': transaction_obj,
        'details': details
    })