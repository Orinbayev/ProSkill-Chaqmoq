import re

def normalize_phone(phone: str) -> str:
    """
    Normalizes phone numbers to +998XXXXXXXXX format.
    Duplicate of backend logic.
    """
    if not phone:
        return ""
    
    # Remove all non-digit characters
    digits = re.sub(r"\D", "", str(phone))
    
    if len(digits) == 9:
        return f"+998{digits}"
    elif len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    elif len(digits) > 12 and digits.startswith("00") and digits[2:5] == "998":
        return f"+{digits[2:]}"
        
    if len(digits) == 12:
        return f"+{digits}"
        
    return f"+{digits}" if digits else ""
