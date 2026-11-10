from app.core.exceptions import ValidationError, ShiftClosedError
from app.modules.pos.models import POSRegisterShift


def validate_active_shift_exists(user_id):
    """Ensure user or terminal has an open register shift."""
    active_shift = POSRegisterShift.query.filter_by(user_id=user_id, is_active=True).first()
    if not active_shift:
        raise ShiftClosedError("No active register shift found. Please open a shift before taking orders.")
    return active_shift


def validate_no_active_shift(user_id):
    active_shift = POSRegisterShift.query.filter_by(user_id=user_id, is_active=True).first()
    if active_shift:
        raise ValidationError("You already have an active register shift open.")
    return True
