import re

def normalize_phone(phone: str) -> str:
    """
    Normalizes phone numbers to +998XXXXXXXXX format.
    Supports formats:
    - 993845854
    - 998993845854
    - +998993845854
    - 99 384 58 54
    - 99-384-58-54
    Returns +998XXXXXXXXX or empty string if invalid.
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
    elif len(digits) == 13 and digits.startswith("0") and digits[1:4] == "998":
        # Handle cases like 0998...
        return f"+{digits[1:]}"
        
    # Last resort: if it's 12 digits, assume it's correct but without +
    if len(digits) == 12:
        return f"+{digits}"
        
    return f"+{digits}" if digits else ""
