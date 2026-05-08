import asyncio
import json
import logging
import re
from html import unescape

from app.collector.base_connector import BaseConnector, CollectionResult, RawItem

logger = logging.getLogger(__name__)

# Tous les domaines disponibles sur les-aides.fr
DOMAINS = [883, 790, 793, 798, 802, 805, 862, 807, 810, 813, 816, 820, 818]

# Secteurs NAF de premier niveau (A à U) — on les parcourt tous pour couvrir toutes les activités
APE_SECTORS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U"]

# Mapping moyen d'intervention → device_type Kafundo
MOYEN_TO_TYPE = {
    822: "investissement",   # Intervention en fonds propres
    827: "pret",             # Avance - Prets - Garanties
    833: "subvention",       # Subvention
    837: "accompagnement",   # Prise en charge des couts
    840: "exoneration",      # Allegement des charges sociales
    845: "exoneration",      # Allegement des charges fiscales
}

# Mapping implantation → geographic_scope
IMPLANTATION_TO_SCOPE = {
    "E": "european",
    "N": "national",
    "T": "regional",
}


def _strip_html(html: str) -> str:
    """Retire les balises HTML et decode les entites."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    return " ".join(text.split()).strip()


def _build_editorial_text(payload: dict) -> str:
    """Assemble un texte source plus riche que le simple resume."""
    candidate_keys = (
        "resume",
        "description",
        "objet",
        "objectif",
        "conditions",
        "beneficiaires",
        "publics",
        "operations",
        "depenses",
        "demarches",
        "modalites",
        "montant",
        "aide",
        "avantage",
    )
    parts: list[str] = []
    seen: set[str] = set()

    for key in candidate_keys:
        value = payload.get(key)
        if not value:
            continue
        text = _strip_html(str(value))
        if not text or text in seen:
            continue
        seen.add(text)
        parts.append(text)

    return "\n\n".join(parts).strip()


def _normalize_domains(value) -> list[int]:
    if not value:
        return list(DOMAINS)
    if isinstance(value, (int, str)):
        value = [value]

    domains: list[int] = []
    for item in value:
        try:
            domains.append(int(item))
        except (TypeError, ValueError):
            continue
    return domains or list(DOMAINS)


def _normalize_ape_sectors(value) -> list[str]:
    if not value:
        return list(APE_SECTORS)
    if isinstance(value, str):
        value = [value]

    sectors: list[str] = []
    for item in value:
        text = str(item or "").strip().upper()
        if re.fullmatch(r"[A-U]", text):
            sectors.append(text)
    return sectors or list(APE_SECTORS)


class LesAidesConnector(BaseConnector):
    """
    Collecte depuis l'API les-aides.fr (CCI France).

    Itère sur tous les domaines x secteurs APE, agrège les dispositifs uniques
    (dedoublonnage par numero), puis conserve un maximum de champs metadata
    pour permettre un backfill plus fin dans le normalizer.

    Config source attendue :
        api_key_value : IDC (identifiant de connexion à l'API)
    """

    async def collect(self) -> CollectionResult:
        idc = self.config.get("api_key_value", "")
        if not idc:
            return CollectionResult(
                source_id=self.source_id,
                items=[],
                success=False,
                error="IDC manquant dans la config (api_key_value)",
            )

        headers = {"IDC": idc}
        base_url = "https://api.les-aides.fr"
        domains = _normalize_domains(self.config.get("domains"))
        ape_sectors = _normalize_ape_sectors(self.config.get("ape_sectors"))
        max_items = int(self.config.get("max_items") or 0)

        seen_numeros: set[int] = set()
        all_items: list[RawItem] = []
        api_errors = 0

        for domaine in domains:
            for ape in ape_sectors:
                url = f"{base_url}/aides/?ape={ape}&domaine={domaine}"
                try:
                    response = await self._get(url, extra_headers=headers)
                    data = response.json()

                    # depassement=true → resultats tronques, la liste est vide
                    if data.get("depassement"):
                        logger.debug("[LesAides] ape=%s domaine=%s: trop de resultats, ignore", ape, domaine)
                        continue

                    dispositifs = data.get("dispositifs") or []
                    for dispositif in dispositifs:
                        numero = dispositif.get("numero")
                        if not numero or numero in seen_numeros:
                            continue
                        seen_numeros.add(numero)

                        title = (dispositif.get("nom") or "").strip()
                        if not title:
                            continue

                        description = _build_editorial_text(dispositif) or _strip_html(dispositif.get("resume") or "")
                        uri = self._build_absolute_url(str(dispositif.get("uri") or base_url), base_url)
                        sigle = dispositif.get("sigle") or ""
                        implantation = dispositif.get("implantation") or "N"
                        moyens = dispositif.get("moyens") or []
                        domaines = dispositif.get("domaines") or []
                        validation = dispositif.get("validation") or ""
                        generation = dispositif.get("generation") or ""

                        device_type = None
                        for moyen in moyens:
                            device_type = MOYEN_TO_TYPE.get(moyen)
                            if device_type:
                                break

                        geographic_scope = IMPLANTATION_TO_SCOPE.get(implantation, "national")
                        country = "France" if implantation in ("N", "T") else "Europe"

                        metadata = dict(dispositif)
                        metadata.update(
                            {
                                "numero": numero,
                                "sigle": sigle,
                                "organism": sigle,
                                "implantation": implantation,
                                "geographic_scope": geographic_scope,
                                "country": country,
                                "device_type": device_type,
                                "validation": validation,
                                "generation": generation,
                                "domaines": domaines,
                                "moyens": moyens,
                                "raw_json": json.dumps(dispositif, ensure_ascii=False, default=str)[:12000],
                            }
                        )

                        all_items.append(
                            RawItem(
                                title=title,
                                url=uri,
                                raw_content=description,
                                source_id=self.source_id,
                                metadata=metadata,
                            )
                        )

                        if max_items and len(all_items) >= max_items:
                            logger.info(
                                "[LesAides][%s] arret anticipe apres %s fiches (max_items)",
                                self.source_id,
                                len(all_items),
                            )
                            return CollectionResult(
                                source_id=self.source_id,
                                items=all_items,
                                success=True,
                                error=f"{api_errors} erreurs API" if api_errors else None,
                            )

                except Exception as exc:
                    api_errors += 1
                    logger.warning("[LesAides] Erreur ape=%s domaine=%s: %s", ape, domaine, exc)
                    await asyncio.sleep(1)
                    continue

        logger.info(
            "[LesAides][%s] %s dispositifs collectes (%s erreurs API)",
            self.source_id,
            len(all_items),
            api_errors,
        )

        success = api_errors < (len(domains) * len(ape_sectors)) // 2
        return CollectionResult(
            source_id=self.source_id,
            items=all_items,
            success=success,
            error=f"{api_errors} erreurs API" if api_errors else None,
        )
