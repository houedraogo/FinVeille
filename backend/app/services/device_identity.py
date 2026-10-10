"""Identité d'une fiche : clés canoniques et comparaison de deux fiches.

Pourquoi ce module (nettoyage du catalogue, octobre 2026)
---------------------------------------------------------
L'audit de la production a montré que le dédoublonnage historique (titre
normalisé + pays, organisme ignoré) pouvait aussi bien rater de vrais
doublons (variantes typographiques, préfixe « Subvention - », même fiche
importée par deux portails) que fusionner à tort des aides territoriales
distinctes qui partagent un intitulé générique (« Aide à l'immobilier
d'entreprise » existe en 71 exemplaires, un par collectivité, chacun avec
son propre règlement). Ce module sépare donc explicitement quatre cas :

* CERTAIN  : même page source discriminante ET même intitulé (à la
  typographie et au préfixe de type près), organismes compatibles, mêmes
  années d'édition. Fusion automatique possible.
* PROBABLE : fort indice mais pas de preuve (même intitulé sans page
  commune, intitulé quasi identique sur la même page…). JAMAIS fusionné
  automatiquement : placé en file de revue.
* HOMONYME : même intitulé mais organisme générique et pages sources
  différentes -> aides territoriales distinctes. Ne jamais fusionner.
* NONE     : rien en commun d'exploitable (dont éditions d'années
  différentes d'un même appel, et pages « liste » partagées par des
  titres différents).

Le module est volontairement pur (aucun accès base) pour être testé sur
des cas réels et réutilisé par l'import, le pipeline et le nettoyage.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Optional
from urllib.parse import parse_qsl, urlsplit

from unidecode import unidecode


class DuplicateTier(str, Enum):
    CERTAIN = "certain"
    PROBABLE = "probable"
    HOMONYM = "homonym"
    NONE = "none"


@dataclass(frozen=True)
class Assessment:
    tier: DuplicateTier
    reasons: tuple[str, ...] = ()

    @property
    def mergeable(self) -> bool:
        """Seul le palier CERTAIN autorise une fusion sans revue humaine."""
        return self.tier is DuplicateTier.CERTAIN


# Organismes qui désignent le portail / l'agrégateur et non le financeur réel :
# deux fiches partageant cet organisme ne sont PAS identifiées par lui.
GENERIC_ORGANISMS = frozenset({
    "",
    "dge",
    "aides entreprises fr",
    "aides territoires",
    "les aides fr",
    "import manuel",
})

# Suffixe de portail ajouté par certains collecteurs au vrai financeur
# (« CCI Hauts-de-France / les-aides.fr ») : retiré pour comparer les financeurs.
_PORTAL_SUFFIX_RE = re.compile(r"\s+(?:les aides fr|aides entreprises fr)$")

# Un lien partagé par au moins ce nombre de titres DIFFÉRENTS est une page
# « liste » (jeu de données, annuaire, PDF de synthèse…), pas une fiche.
LISTING_URL_MIN_DISTINCT_TITLES = 3

_QUOTES = str.maketrans({
    "’": "'", "‘": "'", "ʼ": "'", "`": "'", "´": "'",
    "“": '"', "”": '"', "«": '"', "»": '"',
})
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
# Préfixes de typage ajoutés par certains collecteurs (« Subvention - … »).
_TYPE_PREFIX_RE = re.compile(
    r"^(?:subvention|concours|investissement|opportunite|opportunities|pret|bourse|"
    r"appel a projets?|appel a candidatures?)\s+(?=\S)"
)
_LOOSE_STOP = frozenset({
    "a", "au", "aux", "de", "des", "du", "d", "l", "la", "le", "les", "et", "en", "pour",
    "un", "une", "sur", "the", "of", "for", "and", "to", "in",
})
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source",
})
_INDEX_FILES = ("index.html", "index.htm", "index.php", "default.aspx")


def normalize_text(value: Optional[str]) -> str:
    """Minuscules, sans accents, apostrophes/guillemets unifiés, espaces compactés."""
    if not value:
        return ""
    text = unidecode(str(value).translate(_QUOTES)).lower()
    text = _NON_ALNUM_RE.sub(" ", text)
    return " ".join(text.split())


def years_in(title: Optional[str]) -> frozenset[str]:
    return frozenset(_YEAR_RE.findall(unidecode(str(title or ""))))


def title_key(title: Optional[str]) -> str:
    """Clé stricte : typographie unifiée, années CONSERVÉES (2025 ≠ 2026)."""
    return normalize_text(title)


def title_key_loose(title: Optional[str]) -> str:
    """Clé souple : sans années, sans préfixe de typage (« Subvention - … »)."""
    text = normalize_text(title)
    text = _TYPE_PREFIX_RE.sub("", text)
    text = _YEAR_RE.sub(" ", text)
    return " ".join(text.split())


def _loose_tokens(title: Optional[str]) -> frozenset[str]:
    return frozenset(
        word for word in title_key_loose(title).split()
        if word not in _LOOSE_STOP and len(word) > 1
    )


def token_similarity(left: Optional[str], right: Optional[str]) -> float:
    a, b = _loose_tokens(left), _loose_tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def organism_key(organism: Optional[str]) -> str:
    key = normalize_text(organism)
    stripped = _PORTAL_SUFFIX_RE.sub("", key)
    return stripped or key


def is_generic_organism(organism: Optional[str]) -> bool:
    return organism_key(organism) in GENERIC_ORGANISMS


def canonical_url(url: Optional[str]) -> Optional[str]:
    """Forme canonique d'une URL source, ou None si elle n'identifie aucune fiche.

    Ignore schéma, « www. », fragment, slash final, fichiers d'index et
    paramètres de suivi. Une page d'accueil (aucun chemin, aucun paramètre)
    n'est pas discriminante -> None.
    """
    if not url:
        return None
    raw = str(url).strip()
    if not raw or raw.startswith(("/", "#")):
        return None
    if "://" not in raw:
        raw = "http://" + raw
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    host = (parts.netloc or "").lower()
    if "@" in host:
        host = host.rsplit("@", 1)[1]
    if host.startswith("www."):
        host = host[4:]
    if not host or "." not in host:
        return None
    path = parts.path or ""
    for index_file in _INDEX_FILES:
        if path.lower().endswith("/" + index_file):
            path = path[: -len(index_file)]
    path = path.rstrip("/")
    query = sorted(
        (key, value) for key, value in parse_qsl(parts.query, keep_blank_values=False)
        if key.lower() not in _TRACKING_PARAMS
    )
    if not path and not query:
        return None
    suffix = "?" + "&".join(f"{k}={v}" for k, v in query) if query else ""
    return f"{host}{path}{suffix}"


def url_variants(url: Optional[str]) -> list[str]:
    """Variantes littérales à tester en base pour retrouver une même page."""
    canonical = canonical_url(url)
    if canonical is None:
        return []
    base = canonical
    variants = []
    for scheme in ("https://", "http://"):
        for www in ("", "www."):
            variants.append(f"{scheme}{www}{base}")
            variants.append(f"{scheme}{www}{base}/")
    return variants


UrlTitleCounter = Callable[[str], int]


def _compatible_organisms(a: Optional[str], b: Optional[str]) -> str:
    """'same' | 'unknown' (au moins un côté générique/absent) | 'different'."""
    ka, kb = organism_key(a), organism_key(b)
    if ka and ka == kb and not is_generic_organism(a):
        return "same"
    if is_generic_organism(a) or is_generic_organism(b):
        return "unknown"
    if token_similarity(a, b) >= 0.6:
        return "same"
    return "different"


def assess_pair(
    left: Mapping[str, object],
    right: Mapping[str, object],
    *,
    distinct_titles_for_url: Optional[UrlTitleCounter] = None,
) -> Assessment:
    """Compare deux fiches (clés : title, organism, country, source_url)."""
    if normalize_text(str(left.get("country") or "")) != normalize_text(str(right.get("country") or "")):
        return Assessment(DuplicateTier.NONE, ("country_differs",))

    title_a, title_b = str(left.get("title") or ""), str(right.get("title") or "")
    strict_equal = bool(title_key(title_a)) and title_key(title_a) == title_key(title_b)
    loose_equal = bool(title_key_loose(title_a)) and title_key_loose(title_a) == title_key_loose(title_b)
    year_conflict = bool(years_in(title_a) and years_in(title_b) and years_in(title_a) != years_in(title_b))

    url_a, url_b = canonical_url(left.get("source_url")), canonical_url(right.get("source_url"))  # type: ignore[arg-type]
    same_url = url_a is not None and url_a == url_b
    if same_url and distinct_titles_for_url is not None:
        if distinct_titles_for_url(url_a) >= LISTING_URL_MIN_DISTINCT_TITLES:  # type: ignore[arg-type]
            same_url = False  # page « liste » partagée : ne prouve rien

    organisms = _compatible_organisms(left.get("organism"), right.get("organism"))  # type: ignore[arg-type]
    reasons: list[str] = []

    if year_conflict:
        return Assessment(DuplicateTier.NONE, ("different_edition_years",))

    if same_url and (strict_equal or loose_equal):
        reasons.append("same_page_and_title" if strict_equal else "same_page_and_title_variant")
        if organisms == "different":
            return Assessment(DuplicateTier.PROBABLE, tuple(reasons + ["organisms_differ"]))
        return Assessment(DuplicateTier.CERTAIN, tuple(reasons + [f"organisms_{organisms}"]))

    if strict_equal or loose_equal:
        both_urls = url_a is not None and url_b is not None
        if organisms == "different":
            return Assessment(DuplicateTier.NONE, ("same_title_other_organism",))
        if organisms == "unknown" and both_urls and url_a != url_b and is_generic_organism(left.get("organism")) and is_generic_organism(right.get("organism")):  # type: ignore[arg-type]
            return Assessment(DuplicateTier.HOMONYM, ("same_title_generic_organism_distinct_pages",))
        reasons.append("same_title" if strict_equal else "same_title_variant")
        reasons.append("page_differs" if both_urls else "page_unknown")
        return Assessment(DuplicateTier.PROBABLE, tuple(reasons + [f"organisms_{organisms}"]))

    if same_url and token_similarity(title_a, title_b) >= 0.9:
        return Assessment(DuplicateTier.PROBABLE, ("same_page_near_identical_title",))

    return Assessment(DuplicateTier.NONE, ())


class DuplicateIndex:
    """Index en mémoire d'un lot de fiches pour comparer sans N×N.

    Chaque fiche : dict avec au moins id, title, organism, country, source_url.
    """

    def __init__(self, devices: list[Mapping[str, object]]):
        self._devices = list(devices)
        self._by_url: dict[str, list[int]] = {}
        self._by_title: dict[str, list[int]] = {}
        titles_per_url: dict[str, set[str]] = {}
        for position, device in enumerate(self._devices):
            url = canonical_url(device.get("source_url"))  # type: ignore[arg-type]
            if url:
                self._by_url.setdefault(url, []).append(position)
                titles_per_url.setdefault(url, set()).add(title_key_loose(str(device.get("title") or "")))
            key = title_key_loose(str(device.get("title") or ""))
            if key:
                self._by_title.setdefault(key, []).append(position)
        self._distinct_titles = {url: len(titles) for url, titles in titles_per_url.items()}

    def distinct_titles_for_url(self, url: str) -> int:
        return self._distinct_titles.get(url, 0)

    def candidates(self, device: Mapping[str, object]) -> list[Mapping[str, object]]:
        seen: set[int] = set()
        found: list[Mapping[str, object]] = []
        url = canonical_url(device.get("source_url"))  # type: ignore[arg-type]
        keys = []
        if url:
            keys.extend(self._by_url.get(url, []))
        key = title_key_loose(str(device.get("title") or ""))
        if key:
            keys.extend(self._by_title.get(key, []))
        for position in keys:
            if position in seen:
                continue
            seen.add(position)
            other = self._devices[position]
            if other.get("id") is not None and other.get("id") == device.get("id"):
                continue
            found.append(other)
        return found

    def assess(self, device: Mapping[str, object]) -> list[tuple[Mapping[str, object], Assessment]]:
        results = []
        for other in self.candidates(device):
            assessment = assess_pair(device, other, distinct_titles_for_url=self.distinct_titles_for_url)
            if assessment.tier is not DuplicateTier.NONE:
                results.append((other, assessment))
        return results
