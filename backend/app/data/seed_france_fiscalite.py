"""
Fiches de référence pour les dispositifs fiscaux France permanents.
CIR, CII, JEI, C3IV, IP Box, etc.
Usage: docker exec kafundo-backend python -m app.data.seed_france_fiscalite
"""
import asyncio
from uuid import uuid4

from sqlalchemy import text

from app.database import AsyncSessionLocal

DEVICES = [
    {
        "slug": "fr-cir-credit-impot-recherche",
        "title": "Crédit d'Impôt Recherche (CIR)",
        "organism": "Ministère de l'Enseignement supérieur et de la Recherche",
        "device_type": "credit_impot",
        "sectors": ["industrie", "numerique", "sante", "environnement", "transversal"],
        "beneficiaries": ["pme", "eti", "grande_entreprise", "startup"],
        "short_description": "Le CIR est un crédit d'impôt de 30% des dépenses de R&D (jusqu'à 100 M€), puis 5% au-delà. Il s'applique aux activités de recherche fondamentale, appliquée et de développement expérimental. C'est le dispositif fiscal le plus important pour l'innovation en France.",
        "full_description": """## Présentation
Le Crédit d'Impôt Recherche (CIR) est le principal dispositif fiscal de soutien à la R&D en France. Il permet aux entreprises de déduire de leur impôt 30% de leurs dépenses de recherche et développement.

## Taux et plafonds
- **30%** des dépenses de R&D jusqu'à 100 millions d'euros
- **5%** au-delà de 100 millions d'euros
- Remboursement immédiat pour les PME, JEI et entreprises nouvelles

## Dépenses éligibles
- Salaires et charges des chercheurs et techniciens de recherche
- Dotations aux amortissements des équipements de recherche
- Dépenses de fonctionnement (forfait de 43% des salaires)
- Sous-traitance auprès d'organismes agréés (publics ou privés)
- Dépenses de brevet (dépôt, maintenance, défense)
- Dépenses de veille technologique (plafond 60 000 €)

## Conditions
L'entreprise doit mener des activités de R&D au sens du Manuel de Frascati : recherche fondamentale, recherche appliquée ou développement expérimental. Les travaux doivent viser à lever une incertitude scientifique ou technique.""",
        "eligibility_criteria": "Toute entreprise soumise à l'IR ou l'IS, quels que soient sa taille, son secteur et sa forme juridique. Les activités doivent relever de la R&D (recherche fondamentale, appliquée ou développement expérimental).",
        "funding_details": "30% des dépenses de R&D jusqu'à 100 M€, puis 5% au-delà. Remboursement immédiat pour les PME. Report possible sur 3 ans.",
        "source_url": "https://www.enseignementsup-recherche.gouv.fr/fr/le-credit-d-impot-recherche-cir-69726",
        "status": "recurring",
        "is_recurring": True,
    },
    {
        "slug": "fr-cii-credit-impot-innovation",
        "title": "Crédit d'Impôt Innovation (CII)",
        "organism": "Ministère de l'Enseignement supérieur et de la Recherche",
        "device_type": "credit_impot",
        "sectors": ["industrie", "numerique", "transversal"],
        "beneficiaries": ["pme", "startup", "tpe"],
        "short_description": "Le CII accorde aux PME un crédit d'impôt de 30% des dépenses d'innovation (plafond 400 000 €/an), soit un avantage maximal de 120 000 €. Il concerne la conception de prototypes ou installations pilotes de produits nouveaux.",
        "full_description": """## Présentation
Le Crédit d'Impôt Innovation (CII) est réservé aux PME. Il couvre les dépenses liées à la conception de prototypes ou installations pilotes de produits nouveaux, en aval de la R&D.

## Taux et plafonds
- **30%** des dépenses d'innovation
- Plafond de **400 000 €** de dépenses par an
- Avantage fiscal maximal : **120 000 €** par an
- Remboursement immédiat pour les PME

## Dépenses éligibles
- Salaires des personnels affectés aux opérations d'innovation
- Dotations aux amortissements
- Sous-traitance (plafond)
- Dépenses de fonctionnement (forfait)
- Frais de brevet liés aux innovations

## Différence avec le CIR
Le CIR couvre la R&D (incertitude scientifique/technique), le CII couvre l'innovation (produit nouveau sur le marché, supérieur en performances, éco-conception, ergonomie, fonctionnalités).""",
        "eligibility_criteria": "Réservé aux PME au sens communautaire (< 250 salariés, CA < 50 M€ ou bilan < 43 M€). Les dépenses doivent concerner des opérations de conception de prototypes ou installations pilotes de produits nouveaux.",
        "funding_details": "30% des dépenses d'innovation, plafonné à 400 000 € de dépenses par an (soit 120 000 € de crédit d'impôt max).",
        "source_url": "https://www.enseignementsup-recherche.gouv.fr/fr/le-credit-d-impot-innovation-cii-69738",
        "status": "recurring",
        "is_recurring": True,
    },
    {
        "slug": "fr-jei-jeune-entreprise-innovante",
        "title": "Statut Jeune Entreprise Innovante (JEI)",
        "organism": "Ministère de l'Économie / DGFiP",
        "device_type": "exoneration",
        "sectors": ["numerique", "industrie", "sante", "transversal"],
        "beneficiaries": ["startup", "pme", "tpe"],
        "short_description": "Le statut JEI offre des exonérations fiscales et sociales aux jeunes entreprises innovantes de moins de 11 ans qui consacrent au moins 15% de leurs charges à la R&D. Exonération d'impôt sur les bénéfices et de cotisations patronales sur les salaires des chercheurs.",
        "full_description": """## Présentation
Le statut de Jeune Entreprise Innovante (JEI) permet aux startups et PME innovantes de bénéficier d'exonérations fiscales et sociales significatives pendant leurs premières années.

## Avantages fiscaux
- **Exonération d'impôt sur les bénéfices** : 100% la 1ère année bénéficiaire, 50% la 2e
- **Exonération de CFE et taxe foncière** pendant 7 ans (sur délibération des collectivités)
- **Exonération de cotisations patronales** sur les salaires des chercheurs, techniciens, gestionnaires de projet R&D, juristes PI et personnels de tests

## Conditions d'éligibilité
- Entreprise de moins de 11 ans
- Moins de 250 salariés
- CA < 50 M€ ou bilan < 43 M€
- Au moins **15% des charges** consacrées à la R&D
- Être indépendante (pas détenue à 50%+ par un groupe)
- Être réellement nouvelle (pas issue d'une restructuration)

## Cumul
Le JEI est cumulable avec le CIR et le CII.""",
        "eligibility_criteria": "PME de moins de 11 ans, moins de 250 salariés, CA < 50 M€, consacrant au moins 15% de ses charges à la R&D, et indépendante.",
        "funding_details": "Exonération totale d'IS la 1ère année bénéficiaire, 50% la 2e. Exonération de cotisations patronales sur les salaires R&D. Exonération de CFE et taxe foncière sur 7 ans.",
        "source_url": "https://www.economie.gouv.fr/entreprises/jeune-entreprise-innovante-jei",
        "status": "recurring",
        "is_recurring": True,
    },
    {
        "slug": "fr-c3iv-credit-impot-industrie-verte",
        "title": "Crédit d'Impôt Investissement Industries Vertes (C3IV)",
        "organism": "Ministère de l'Économie / DGFiP",
        "device_type": "credit_impot",
        "sectors": ["industrie", "energie", "environnement"],
        "beneficiaries": ["pme", "eti", "grande_entreprise"],
        "short_description": "Le C3IV soutient les investissements industriels dans 4 filières stratégiques de la transition énergétique : batteries, éolien, pompes à chaleur et panneaux solaires. Crédit d'impôt de 20% à 60% selon la taille de l'entreprise et la zone d'implantation.",
        "full_description": """## Présentation
Le Crédit d'Impôt au titre des Investissements dans l'Industrie Verte (C3IV) est un nouveau dispositif créé par la loi Industrie Verte (2023) pour soutenir la réindustrialisation verte de la France.

## Filières éligibles
- **Batteries** (cellules, modules, packs)
- **Panneaux solaires** (cellules, modules, composants)
- **Éoliennes** (composants critiques)
- **Pompes à chaleur** (composants et assemblage)

## Taux
- **20%** pour les grandes entreprises
- **40%** pour les ETI
- **60%** pour les PME
- Majorations possibles pour les zones AFR (aide à finalité régionale)

## Dépenses éligibles
- Investissements corporels : terrains, bâtiments, équipements, machines
- Investissements incorporels : brevets, licences, savoir-faire
- Plafond : 150 M€ de dépenses (200 M€ en zone AFR)""",
        "eligibility_criteria": "Entreprises industrielles investissant dans la production de batteries, panneaux solaires, éoliennes ou pompes à chaleur en France. Agrément préalable obligatoire auprès de la DGFiP.",
        "funding_details": "20% (grandes entreprises), 40% (ETI), 60% (PME) des investissements éligibles. Plafond de 150 M€ de dépenses (200 M€ en zone AFR).",
        "source_url": "https://www.economie.gouv.fr/industrie-verte/c3iv",
        "status": "recurring",
        "is_recurring": True,
    },
    {
        "slug": "fr-ip-box-regime-fiscal-pi",
        "title": "IP Box — Régime fiscal de la propriété intellectuelle",
        "organism": "DGFiP",
        "device_type": "exoneration",
        "sectors": ["numerique", "industrie", "sante", "transversal"],
        "beneficiaries": ["pme", "eti", "grande_entreprise", "startup"],
        "short_description": "L'IP Box permet de bénéficier d'un taux réduit d'imposition de 10% sur les revenus tirés de la propriété intellectuelle (brevets, logiciels, certificats d'obtention végétale). Il vise à encourager la localisation de la R&D en France.",
        "full_description": """## Présentation
Le régime IP Box (Patent Box) permet d'appliquer un taux d'imposition réduit de 10% (au lieu de 25%) sur les revenus tirés de certains actifs de propriété intellectuelle développés en France.

## Actifs éligibles
- Brevets et certificats d'utilité
- Certificats d'obtention végétale
- Logiciels protégés par le droit d'auteur
- Procédés de fabrication industriels associés à un brevet

## Revenus concernés
- Redevances de licences
- Plus-values de cession
- Résultat net tiré de l'exploitation directe

## Calcul
Le bénéfice éligible est calculé selon le ratio nexus (lien entre les dépenses de R&D réalisées en propre et le revenu de PI). Plus la R&D est réalisée en France par l'entreprise, plus le bénéfice éligible au taux réduit est important.""",
        "eligibility_criteria": "Toute entreprise soumise à l'IS qui détient des actifs de PI éligibles et a réalisé les dépenses de R&D correspondantes.",
        "funding_details": "Taux d'imposition réduit à 10% (au lieu de 25%) sur les revenus de PI éligibles.",
        "source_url": "https://bofip.impots.gouv.fr/bofip/11955-PGP.html",
        "status": "recurring",
        "is_recurring": True,
    },
    {
        "slug": "fr-suramortissement-industriel",
        "title": "Suramortissement industriel — Déduction exceptionnelle",
        "organism": "DGFiP",
        "device_type": "exoneration",
        "sectors": ["industrie"],
        "beneficiaries": ["pme", "eti"],
        "short_description": "Les PME et ETI industrielles peuvent déduire de leur résultat imposable 40% du prix de revient de certains équipements de production (robots, imprimantes 3D, logiciels de pilotage, machines de fabrication additive).",
        "full_description": """## Présentation
Le suramortissement industriel permet aux PME et ETI de déduire de leur résultat imposable 40% de la valeur d'origine de certains biens d'équipement utilisés dans la production industrielle.

## Équipements éligibles
- Robots industriels et cobots
- Machines de fabrication additive (impression 3D)
- Logiciels de conception, fabrication et pilotage (CAO, FAO, MES, ERP industriel)
- Capteurs connectés et équipements IoT industriels
- Machines-outils à commande numérique

## Avantage
- Déduction extra-comptable de **40%** du prix de revient
- S'ajoute à l'amortissement classique
- Étalée sur la durée d'amortissement du bien""",
        "eligibility_criteria": "PME et ETI industrielles (secteurs manufacturiers). Biens neufs acquis ou fabriqués entre le 1er janvier 2019 et le 31 décembre 2025.",
        "funding_details": "Déduction fiscale de 40% du prix de revient des équipements éligibles, en plus de l'amortissement normal.",
        "source_url": "https://www.economie.gouv.fr/entreprises/suramortissement-investissement-industriel",
        "status": "recurring",
        "is_recurring": True,
    },
    {
        "slug": "fr-jec-jeune-entreprise-croissance",
        "title": "Jeune Entreprise de Croissance (JEC)",
        "organism": "Ministère de l'Économie / DGFiP",
        "device_type": "exoneration",
        "sectors": ["numerique", "industrie", "transversal"],
        "beneficiaries": ["startup", "pme"],
        "short_description": "La JEC est une extension du JEI pour les entreprises de moins de 11 ans en forte croissance. L'entreprise doit justifier d'au moins 5% de dépenses de R&D et d'une croissance significative de son CA. Mêmes avantages fiscaux que le JEI.",
        "full_description": """## Présentation
Le statut Jeune Entreprise de Croissance (JEC), créé par la loi de finances 2024, élargit le dispositif JEI aux entreprises innovantes en forte croissance même si elles ne consacrent pas 15% de leurs charges à la R&D.

## Conditions
- Entreprise de moins de 11 ans
- PME (< 250 salariés, CA < 50 M€)
- Au moins **5% des charges** en R&D (contre 15% pour le JEI)
- **Croissance significative** du CA (10%+ par an ou doublement sur 3 ans)

## Avantages
Identiques au JEI : exonérations d'IS, cotisations patronales, CFE et taxe foncière.""",
        "eligibility_criteria": "PME de moins de 11 ans, au moins 5% de charges de R&D, et croissance significative du CA (10%+ annuel ou doublement sur 3 ans).",
        "funding_details": "Exonérations fiscales et sociales identiques au JEI (IS, cotisations patronales, CFE).",
        "source_url": "https://www.economie.gouv.fr/entreprises/jeune-entreprise-innovante-jei",
        "status": "recurring",
        "is_recurring": True,
    },
]


async def main():
    async with AsyncSessionLocal() as db:
        for d in DEVICES:
            existing = await db.execute(
                text("SELECT id FROM devices WHERE slug = :slug"),
                {"slug": d["slug"]}
            )
            if existing.scalar_one_or_none():
                print(f"  SKIP (existe déjà): {d['slug']}")
                continue

            await db.execute(text("""
                INSERT INTO devices (
                    id, slug, title, title_normalized, organism, country,
                    device_type, sectors, beneficiaries,
                    short_description, full_description, eligibility_criteria,
                    funding_details, source_url, status, is_recurring,
                    language, confidence_score, completeness_score,
                    validation_status, created_at, updated_at
                ) VALUES (
                    :id, :slug, :title, :title_norm, :organism, 'France',
                    :dtype, :sectors, :bens,
                    :short, :full, :elig,
                    :funding, :url, :status, :recurring,
                    'fr', 95, 95,
                    'auto_published', NOW(), NOW()
                )
            """), {
                "id": str(uuid4()),
                "slug": d["slug"],
                "title": d["title"],
                "title_norm": d["title"].lower(),
                "organism": d["organism"],
                "dtype": d["device_type"],
                "sectors": d["sectors"],
                "bens": d["beneficiaries"],
                "short": d["short_description"],
                "full": d["full_description"],
                "elig": d["eligibility_criteria"],
                "funding": d["funding_details"],
                "url": d["source_url"],
                "status": d["status"],
                "recurring": d["is_recurring"],
            })
            print(f"  OK: {d['title']}")

        await db.commit()
        print(f"\n{len(DEVICES)} fiches fiscales traitées.")


if __name__ == "__main__":
    asyncio.run(main())
