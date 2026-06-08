import secrets


def generate_invite_code() -> str:
    return secrets.token_urlsafe(6)[:8].upper()
