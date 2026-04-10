import hashlib


def compute_content_hash(content: str) -> str:
    """Calcule un SHA-256 d'un contenu pour détecter les changements."""
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


def compute_fingerprint(title: str, organism: str, country: str) -> str:
    """Empreinte unique pour la déduplication."""
    from unidecode import unidecode
    normalized = unidecode(f"{title}{organism}{country}".lower())
    normalized = "".join(c for c in normalized if c.isalnum())
    return hashlib.md5(normalized.encode()).hexdigest()
