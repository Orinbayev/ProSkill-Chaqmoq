def format_phone(phone: str) -> str:
    if not phone:
        return "Noma'lum"
    return f"<b>{phone}</b>"

def format_date(date_str: str) -> str:
    # Just a simple wrapper for now
    return f"<i>{date_str}</i>"
