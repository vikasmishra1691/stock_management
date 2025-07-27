from django import forms
from django.core.exceptions import ValidationError
from .models import ProdMast, StockTrans, StockDetail
from collections import defaultdict

class ProductForm(forms.ModelForm):
    class Meta:
        model = ProdMast
        fields = ['prod_name', 'prod_desc', 'is_active']
        widgets = {
            'prod_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product name',
                'maxlength': 100
            }),
            'prod_desc': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional product description'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'prod_name': 'Product Name',
            'prod_desc': 'Description',
            'is_active': 'Active'
        }

    def clean_prod_name(self):
        name = self.cleaned_data.get('prod_name')
        if name:
            name = name.strip().title()
            if len(name) < 2:
                raise ValidationError("Product name must be at least 2 characters long")
            
            # Check for uniqueness (excluding current instance if editing)
            existing = ProdMast.objects.filter(prod_name__iexact=name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError("A product with this name already exists")
        
        return name

class StockTransForm(forms.ModelForm):
    class Meta:
        model = StockTrans
        fields = ['transaction_type', 'notes', 'created_by']
        widgets = {
            'transaction_type': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional transaction notes'
            }),
            'created_by': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your name or ID'
            })
        }
        labels = {
            'transaction_type': 'Transaction Type',
            'notes': 'Notes',
            'created_by': 'Created By'
        }

class StockDetailForm(forms.ModelForm):
    class Meta:
        model = StockDetail
        fields = ['product', 'quantity', 'unit_price', 'notes']
        widgets = {
            'product': forms.Select(attrs={
                'class': 'form-select'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Enter quantity'
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Optional unit price'
            }),
            'notes': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional notes'
            })
        }
        labels = {
            'product': 'Product',
            'quantity': 'Quantity',
            'unit_price': 'Unit Price',
            'notes': 'Notes'
        }

    def __init__(self, *args, **kwargs):
        self.transaction_type = kwargs.pop('transaction_type', None)
        super().__init__(*args, **kwargs)
        
        # Only show active products
        self.fields['product'].queryset = ProdMast.objects.filter(is_active=True)

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity is not None and quantity <= 0:
            raise ValidationError("Quantity must be greater than 0")
        return quantity

    def clean_unit_price(self):
        price = self.cleaned_data.get('unit_price')
        if price is not None and price < 0:
            raise ValidationError("Price cannot be negative")
        return price

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        
        if product and quantity and self.transaction_type == 'OUT':
            # Check stock availability for OUT transactions
            current_stock = self._get_current_stock(product)
            if current_stock < quantity:
                raise ValidationError(
                    f"Insufficient stock for {product.prod_name}. "
                    f"Available: {current_stock}, Requested: {quantity}"
                )
        
        return cleaned_data

    def _get_current_stock(self, product):
        """Calculate current stock for a product"""
        inventory = defaultdict(int)
        details = StockDetail.objects.filter(
            product=product
        ).select_related('transaction')

        for detail in details:
            qty = detail.quantity
            if detail.transaction.transaction_type == 'OUT':
                qty = -qty
            inventory[product] += qty

        return inventory[product]

# Custom formset for better validation
StockDetailFormSet = forms.formset_factory(
    StockDetailForm,
    extra=3,
    min_num=1,
    validate_min=True,
    can_delete=True
)