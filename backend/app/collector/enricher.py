from datetime import date
from typing import Dict, Any

REQUIRED_FIELDS  = ["title", "organism", "country", "device_type", "short_description"]
IMPORTANT_FIELDS = ["close_date", "amount_max", "eligibility_criteria", "sectors", "source_url"]
OPTIONAL_FIELDS  = ["full_description", "beneficiaries", "funding_rate", "open_date"]

# Score de base par niveau de source (1 = meilleur)
SOURCE_LEVEL_BASE = {1: 72, 2: 55, 3: 38}

TYPE_LABELS = {
    "subvention":          "propose une subvention",
    "pret":                "propose un prêt public",
    "avance_remboursable": "propose une avance remboursable",
    "garantie":            "propose une garantie publique",
    "credit_impot":        "permet de bénéficier d'un crédit d'impôt",
    "exoneration":         "prévoit des exonérations fiscales",
    "aap":                 "lance un appel à projets",
    "ami":                 "lance un appel à manifestation d'intérêt",
    "accompagnement":      "propose un programme d'accompagnement",
    "concours":            "organise un concours",
    "autre":               "propose un dispositif de financement",
}


class Enricher:
    """Calcule les scores et génère le résumé automatique (extractif)."""

    def enrich(self, device: Dict[str, Any], source_level: int = 2) -> Dict[str, Any]:
        device["completeness_score"] = self._completeness(device)
        device["confidence_score"]   = self._confidence(device, source_level)
        device["relevance_score"]    = self._relevance(device)
        device["auto_summary"]       = self._summary(device)
        return device

    def _completeness(self, d: dict) -> int:
        score = 0
        score += sum(14 for f in REQUIRED_FIELDS  if d.get(f))   # max 70
        score += sum(4  for f in IMPORTANT_FIELDS if d.get(f))   # max 20
        score += sum(2  for f in OPTIONAL_FIELDS  if d.get(f))   # max  8
        score += 2 if d.get("keywords") else 0                   # max  2
        return min(score, 100)

    def _confidence(self, d: dict, source_level: int) -> int:
        base = SOURCE_LEVEL_BASE.get(source_level, 40)
        completeness_bonus = self._completeness(d) * 0.28
        return int(min(base + completeness_bonus, 100))

    def _relevance(self, d: dict) -> int:
        score = self._completeness(d)
        # Bonus si dispositif actif avec date future
        if d.get("close_date"):
            try:
                cd = d["close_date"] if isinstance(d["close_date"], date) else date.fromisoformat(str(d["close_date"]))
                if cd >= date.today():
                    score = min(score + 12, 100)
            except (ValueError, TypeError):
                pass
        if d.get("is_recurring"):
            score = min(score + 8, 100)
        # Malus si expiré/fermé
        if d.get("status") in ("closed", "expired"):
            score = max(score - 25, 0)
        return score

    def _summary(self, d: dict) -> str:
        parts = []

        organism = d.get("organism", "")
        if organism:
            parts.append(organism)

        action = TYPE_LABELS.get(d.get("device_type", "autre"), "propose un financement public")
        parts.append(action)

        sectors = d.get("sectors") or []
        if sectors and sectors != ["transversal"]:
            parts.append(f"dans le secteur {', '.join(sectors[:2])}")

        amount_max = d.get("amount_max")
        if amount_max:
            currency = d.get("currency", "EUR")
            try:
                parts.append(f"jusqu'à {float(amount_max):,.0f} {currency}".replace(",", " "))
            except (ValueError, TypeError):
                pass

        close_date = d.get("close_date")
        if close_date:
            try:
                cd = close_date if isinstance(close_date, date) else date.fromisoformat(str(close_date))
                parts.append(f"— clôture le {cd.strftime('%d/%m/%Y')}")
            except (ValueError, TypeError):
                pass
        elif d.get("is_recurring"):
            parts.append("— dispositif récurrent")

        if not parts:
            return ""

        summary = " ".join(parts)
        return summary[0].upper() + summary[1:] + "."
