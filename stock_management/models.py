from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError

class ProdMast(models.Model):
    prod_name = models.CharField(max_length=100, unique=True, help_text="Product name must be unique")
    prod_desc = models.TextField(blank=True, help_text="Optional product description")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="Set to false to deactivate product")

    class Meta:
        verbose_name = "Product Master"
        verbose_name_plural = "Product Masters"
        ordering = ['prod_name']

    def __str__(self):
        return self.prod_name

    def clean(self):
        if self.prod_name:
            self.prod_name = self.prod_name.strip().title()
        if len(self.prod_name.strip()) < 2:
            raise ValidationError("Product name must be at least 2 characters long")

class StockTrans(models.Model):
    TRANSACTION_TYPES = [
        ("IN", "Stock In"),
        ("OUT", "Stock Out")
    ]
    
    transaction_type = models.CharField(
        max_length=3, 
        choices=TRANSACTION_TYPES,
        help_text="Select transaction type"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text="Optional transaction notes")
    created_by = models.CharField(max_length=100, blank=True, help_text="Who created this transaction")

    class Meta:
        verbose_name = "Stock Transaction"
        verbose_name_plural = "Stock Transactions"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    def get_total_items(self):
        return self.stockdetail_set.count()

    def get_total_quantity(self):
        return sum(detail.quantity for detail in self.stockdetail_set.all())

class StockDetail(models.Model):
    product = models.ForeignKey(ProdMast, on_delete=models.CASCADE)
    transaction = models.ForeignKey(StockTrans, on_delete=models.CASCADE)
    quantity = models.IntegerField(
        validators=[MinValueValidator(1, message="Quantity must be at least 1")]
    )
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0, message="Price cannot be negative")]
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Stock Detail"
        verbose_name_plural = "Stock Details"
        unique_together = ['product', 'transaction']  # Prevent duplicate product in same transaction

    def __str__(self):
        return f"{self.product.prod_name} - {self.quantity} units"

    def clean(self):
    # Validate quantity
        if self.quantity is None:
            raise ValidationError("Quantity is required")
        if self.quantity <= 0:
            raise ValidationError("Quantity must be greater than 0")
    
    # Skip stock validation during initial form validation
    # Stock validation will be handled in the view after transaction creation

    def validate_stock_availability(self, transaction_type):
        """Separate method to validate stock availability"""
        if transaction_type == 'OUT':
            current_stock = self.get_current_stock()
            if current_stock < self.quantity:
                raise ValidationError(
                    f"Insufficient stock for {self.product.prod_name}. Available: {current_stock}, Requested: {self.quantity}"
                )

    def get_current_stock(self):
        """Calculate current stock for this product"""
        from collections import defaultdict
        inventory = defaultdict(int)
        details = StockDetail.objects.filter(
            product=self.product
        ).select_related('transaction')
        
        for detail in details:
            if detail == self:  # Skip the current record being validated
                continue
            qty = detail.quantity
            if detail.transaction.transaction_type == 'OUT':
                qty = -qty
            inventory[detail.product] += qty
        
        return inventory[self.product]

    def get_total_value(self):
        if self.unit_price:
            return self.quantity * self.unit_price
        return 0