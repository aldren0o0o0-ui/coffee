from decimal import Decimal
from app.core.exceptions import ValidationError
from app.modules.sales.models import Sale, SaleStatus


def validate_sale_can_be_refunded(sale: Sale, refund_amount=None):
    if sale.status == SaleStatus.VOIDED:
        raise ValidationError("Voided sales cannot be refunded.")
    if sale.status == SaleStatus.REFUNDED:
        raise ValidationError("This order has already been fully refunded.")

    if refund_amount is not None:
        try:
            amt = Decimal(str(refund_amount))
        except (ValueError, TypeError):
            raise ValidationError("Invalid refund amount format.")

        if amt <= Decimal("0.00"):
            raise ValidationError("Refund amount must be greater than zero.")

        current_refunded = Decimal(str(sale.refund_amount or "0.00"))
        remaining = Decimal(str(sale.total_amount)) - current_refunded
        if amt > remaining:
            raise ValidationError(
                f"Refund amount (${amt:.2f}) cannot exceed remaining balance (${remaining:.2f})."
            )
    return True


def validate_sale_can_be_voided(sale: Sale):
    if sale.status == SaleStatus.VOIDED:
        raise ValidationError("This order is already voided.")
    if sale.status in (SaleStatus.REFUNDED, SaleStatus.PARTIALLY_REFUNDED):
        raise ValidationError("Cannot void an order that has been refunded.")
    if sale.status != SaleStatus.COMPLETED:
        raise ValidationError("Only completed orders can be voided.")
    return True
