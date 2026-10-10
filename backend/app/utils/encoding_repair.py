"""Détection et réparation du mojibake (UTF-8 lu comme cp1252, ex. « â‚¬ » pour « € »)."""
import re

_MOJIBAKE_RE = re.compile(
    r"[ÂÃâ][\u0080-¿Œ-ŸŽžƒˆ˜–-›€™]{1,2}"
)


def looks_mojibake(text: str) -> bool:
    return bool(text) and _MOJIBAKE_RE.search(text) is not None


def _repair_sequence(match: "re.Match[str]") -> str:
    try:
        return match.group().encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return match.group()


def repair_mojibake(text: str) -> str:
    """Répare les séquences mojibake reconnues ; le reste du texte est inchangé."""
    return _MOJIBAKE_RE.sub(_repair_sequence, text or "")
