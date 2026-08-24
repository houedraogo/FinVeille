import asyncio
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
    827: "pret",             # Avance − Prêts − Garanties
    833: "subvention",       # Subvention
    837: "accompagnement",   # Prise en charge des coûts
    840: "exoneration",      # Allègement des charges sociales
    845: "exoneration",      # Allègement des charges fiscales
}

# Mapping implantation → geographic_scope
IMPLANTATION_TO_SCOPE = {
    "E": "european",
    "N": "national",
    "T": "regional",
}


def _strip_html(html: str) -> str:
    """Retire les balises HTML et décode les entités."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    return " ".join(text.split()).strip()


class LesAidesConnector(BaseConnector):
    """
    Collecte depuis l'API les-aides.fr (CCI France).

    Itère sur tous les domaines × secteurs APE, agrège les dispositifs uniques
    (dédoublonnage par numéro), puis utilise le champ 'resume' comme description.

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

        seen_numeros: set[int] = set()
        all_items: list[RawItem] = []
        api_errors = 0

        for domaine in DOMAINS:
            for ape in APE_SECTORS:
                url = f"{base_url}/aides/?ape={ape}&domaine={domaine}"
                try:
                    response = await self._get(url, extra_headers=headers)
                    data = response.json()

                    # depassement=true → résultats tronqués, la liste est vide
                    if data.get("depassement"):
                        logger.debug(f"[LesAides] ape={ape} domaine={domaine}: trop de résultats, ignoré")
                        continue

                    dispositifs = data.get("dispositifs") or []
                    for d in dispositifs:
                        numero = d.get("numero")
                        if not numero or numero in seen_numeros:
                            continue
                        seen_numeros.add(numero)

                        title = (d.get("nom") or "").strip()
                        if not title:
                            continue

                        description = _strip_html(d.get("resume") or "")
                        uri = d.get("uri") or base_url
                        sigle = d.get("sigle") or ""
                        implantation = d.get("implantation") or "N"
                        moyens = d.get("moyens") or []
                        domaines = d.get("domaines") or []
                        validation = d.get("validation") or ""
                        generation = d.get("generation") or ""

                        # Détermine le device_type prioritaire depuis les moyens
                        device_type = None
                        for m in moyens:
                            device_type = MOYEN_TO_TYPE.get(m)
                            if device_type:
                                break

                        geographic_scope = IMPLANTATION_TO_SCOPE.get(implantation, "national")
                        country = "France" if implantation in ("N", "T") else "Europe"

                        all_items.append(
                            RawItem(
                                title=title,
                                url=uri,
                                raw_content=description,
                                source_id=self.source_id,
                                metadata={
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
                                },
                            )
                        )

                except Exception as exc:
                    api_errors += 1
                    logger.warning(f"[LesAides] Erreur ape={ape} domaine={domaine}: {exc}")
                    await asyncio.sleep(1)
                    continue

        logger.info(
            f"[LesAides][{self.source_id}] {len(all_items)} dispositifs collectés "
            f"({api_errors} erreurs API)"
        )

        success = api_errors < (len(DOMAINS) * len(APE_SECTORS)) // 2
        return CollectionResult(
            source_id=self.source_id,
            items=all_items,
            success=success,
            error=f"{api_errors} erreurs API" if api_errors else None,
        )
