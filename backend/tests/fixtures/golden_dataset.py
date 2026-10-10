"""
Golden Dataset — 40 cas représentatifs pour le Sprint Qualité 1.

Valeurs attendues établies depuis les sources primaires, pas depuis les données Kafundo.
Chaque cas est un dict avec :
  - id           : identifiant unique du cas
  - category     : A (VALID) | B (SUSPECT) | C (INVALID) | D (edge case)
  - source_name  : nom de la source
  - source_url   : URL source attendue (absolue)
  - raw_content  : extrait représentatif du contenu source brut
  - expected     : dict des valeurs attendues (voir champs ci-dessous)

Champs expected :
  title             : titre en français attendu
  content_nature    : "FINANCING_OPPORTUNITY" | "EVENT" | "NEWS" | etc.
  should_publish    : True / False
  organism          : organisme financeur réel (pas l'agrégateur)
  amount_min        : float ou None
  amount_max        : float ou None
  currency          : "EUR" | "XOF" | "USD" | etc.
  amount_type       : "beneficiary_amount" | "program_budget" | "rate_only" | "range" | "unknown"
  deadline          : "YYYY-MM-DD" ou None
  is_recurring      : bool
  country           : str
  source_language   : "fr" | "en"
  requires_translation : bool
  quality_state     : "VALID" | "SUSPECT" | "REVIEW_REQUIRED" | "INVALID"
"""

GOLDEN_DATASET = [

    # ══════════════════════════════════════════════
    # CATÉGORIE A — VALID (fiches exploitables telles quelles)
    # ══════════════════════════════════════════════

    {
        "id": "A01",
        "category": "A",
        "source_name": "Bpifrance",
        "source_url": "https://www.bpifrance.fr/nos-solutions/financement/prets/pret-croissance-industrie",
        "raw_content": (
            "Prêt Croissance Industrie — Bpifrance. "
            "Montant : 300 000 à 5 000 000 EUR. "
            "Durée : 5 à 7 ans. "
            "Objectif : soutenir les projets de modernisation et de transformation "
            "des PME et ETI industrielles. "
            "Bénéficiaires : PME et ETI du secteur industriel immatriculées en France. "
            "Date limite : dispositif ouvert en continu. "
            "Contact : Bpifrance régional."
        ),
        "expected": {
            "title": "Prêt Croissance Industrie — Bpifrance",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": True,
            "organism": "Bpifrance",
            "amount_min": 300_000,
            "amount_max": 5_000_000,
            "currency": "EUR",
            "amount_type": "range",
            "deadline": None,
            "is_recurring": True,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "VALID",
        },
    },

    {
        "id": "A02",
        "category": "A",
        "source_name": "FONSTI",
        "source_url": "https://www.fonsti.ci/appels-a-projets/innovation-2025",
        "raw_content": (
            "Appel à Projets Innovation 2025 — FONSTI (Côte d'Ivoire). "
            "Le FONSTI lance un appel à projets pour des projets d'innovation technologique. "
            "Montant maximum : 50 000 000 XOF par projet sélectionné. "
            "Date limite de dépôt : 30 septembre 2025. "
            "Critères : entreprise ivoirienne, projet innovant, business plan validé. "
            "Contact : fonsti@fonsti.ci"
        ),
        "expected": {
            "title": "Appel à Projets Innovation 2025 — FONSTI",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": True,
            "organism": "FONSTI",
            "amount_min": None,
            "amount_max": 50_000_000,
            "currency": "XOF",
            "amount_type": "beneficiary_amount",
            "deadline": "2025-09-30",
            "is_recurring": False,
            "country": "Côte d'Ivoire",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "VALID",
        },
    },

    {
        "id": "A03",
        "category": "A",
        "source_name": "Import manuel",
        "source_url": "https://eic.ec.europa.eu/eic-funding/eic-accelerator_fr",
        "raw_content": (
            "EIC Accelerator — Commission Européenne. "
            "Subvention jusqu'à 2 500 000 EUR + investissement equity jusqu'à 15 000 000 EUR. "
            "Pour les startups deeptech à fort potentiel de marché européen et mondial. "
            "Date limite prochaine session : 5 octobre 2025. "
            "Critères : innovation de rupture, PME ou startup immatriculée dans un État membre UE."
        ),
        "expected": {
            "title": "EIC Accelerator — Commission Européenne",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": True,
            "organism": "Commission Européenne / EIC",
            "amount_min": None,
            "amount_max": 2_500_000,
            "currency": "EUR",
            "amount_type": "beneficiary_amount",
            "deadline": "2025-10-05",
            "is_recurring": False,
            "country": "Europe",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "VALID",
        },
    },

    {
        "id": "A04",
        "category": "A",
        "source_name": "Global South Opportunities",
        "source_url": "https://globalsouthopportunities.com/agnes-intra-africa-grants/",
        "raw_content": (
            "AGNES Intra-Africa Mobility Grants for Junior Researchers 2026. "
            "Funding up to USD 7 500 per researcher for collaborative research visits. "
            "Eligible: junior researchers from African universities. "
            "Deadline: March 31, 2026. "
            "Funded by: African climate research network."
        ),
        "expected": {
            "title": "AGNES — Bourses de mobilité intra-africaine pour jeunes chercheurs 2026",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,  # requires translation before publish
            "organism": "AGNES / African climate research network",
            "amount_min": None,
            "amount_max": 7_500,
            "currency": "USD",
            "amount_type": "beneficiary_amount",
            "deadline": "2026-03-31",
            "is_recurring": False,
            "country": "International",
            "source_language": "en",
            "requires_translation": True,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "A05",
        "category": "A",
        "source_name": "Bpifrance",
        "source_url": "https://www.bpifrance.fr/nos-solutions/innovation/aides/bourse-french-tech-emergence",
        "raw_content": (
            "Bourse French Tech Émergence — Bpifrance. "
            "Subvention de 30 000 EUR accordée aux startups en phase de création. "
            "Dispositif ouvert en continu, dépôt mensuel. "
            "Bénéficiaires : startups de moins de 2 ans, 1 à 2 associés fondateurs, projet innovant. "
            "Taux de financement : 70 % des dépenses éligibles plafonnées à 30 000 EUR."
        ),
        "expected": {
            "title": "Bourse French Tech Émergence — Bpifrance",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": True,
            "organism": "Bpifrance",
            "amount_min": None,
            "amount_max": 30_000,
            "currency": "EUR",
            "amount_type": "beneficiary_amount",
            "deadline": None,
            "is_recurring": True,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "VALID",
        },
    },

    {
        "id": "A06",
        "category": "A",
        "source_name": "Import manuel",
        "source_url": "https://www.greenclimate.fund/readiness",
        "raw_content": (
            "Readiness and Preparatory Support Programme — Green Climate Fund. "
            "Up to USD 3 000 000 per country for readiness activities. "
            "Eligible: developing countries, national designated authorities, direct access entities. "
            "Ongoing, rolling submission dates. "
            "Grants for strengthening climate finance access."
        ),
        "expected": {
            "title": "GCF Readiness Programme — Fonds Vert pour le Climat",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,
            "organism": "Green Climate Fund",
            "amount_min": None,
            "amount_max": 3_000_000,
            "currency": "USD",
            "amount_type": "beneficiary_amount",
            "deadline": None,
            "is_recurring": True,
            "country": "International",
            "source_language": "en",
            "requires_translation": True,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "A07",
        "category": "A",
        "source_name": "Banque Mondiale",
        "source_url": "https://projects.worldbank.org/en/projects-operations/project-detail/P175765",
        "raw_content": (
            "Senegal Economic Inclusion and Social Protection Project. "
            "World Bank project approved. Grant component to support 50 000 households. "
            "Individual cash transfers of CFA 25 000/month. "
            "Direct application via Ministry of Social Development. "
            "Project closing date: December 31, 2028."
        ),
        "expected": {
            "title": "Projet inclusion économique et protection sociale — Sénégal",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,
            "organism": "Banque Mondiale / Ministère développement social Sénégal",
            "amount_min": None,
            "amount_max": 25_000,
            "currency": "XOF",
            "amount_type": "beneficiary_amount",
            "deadline": "2028-12-31",
            "is_recurring": True,
            "country": "Sénégal",
            "source_language": "en",
            "requires_translation": True,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "A08",
        "category": "A",
        "source_name": "FONSTI",
        "source_url": "https://www.fonsti.ci/bourses/doctorants-2025",
        "raw_content": (
            "Bourse de doctorat FONSTI 2025 — Côte d'Ivoire. "
            "Le FONSTI accorde des bourses aux doctorants ivoiriens en sciences et technologies. "
            "Montant : 300 000 XOF par mois pendant 3 ans. "
            "Dépôt des candidatures avant le 15 juillet 2025. "
            "Critères : nationalité ivoirienne, inscription en doctorat en Côte d'Ivoire, excellence académique."
        ),
        "expected": {
            "title": "Bourse de doctorat FONSTI 2025",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": True,
            "organism": "FONSTI",
            "amount_min": None,
            "amount_max": 300_000,
            "currency": "XOF",
            "amount_type": "beneficiary_amount",
            "deadline": "2025-07-15",
            "is_recurring": False,
            "country": "Côte d'Ivoire",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "VALID",
        },
    },

    {
        "id": "A09",
        "category": "A",
        "source_name": "Aides-entreprises.fr",
        "source_url": "https://www.economie.gouv.fr/entreprises/aide-numerique-tpe-pme",
        "raw_content": (
            "Chèque Numérique TPE/PME — Ministère de l'Économie. "
            "Aide de 500 EUR pour les TPE/PME souhaitant se numériser. "
            "Financement à 50 % des dépenses d'équipement numérique. "
            "Date limite : 31 décembre 2025. "
            "Bénéficiaires : TPE/PME de moins de 50 salariés, tous secteurs."
        ),
        "expected": {
            "title": "Chèque Numérique TPE/PME",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": True,
            "organism": "Ministère de l'Économie",
            "amount_min": None,
            "amount_max": 500,
            "currency": "EUR",
            "amount_type": "beneficiary_amount",
            "deadline": "2025-12-31",
            "is_recurring": False,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "VALID",
        },
    },

    {
        "id": "A10",
        "category": "A",
        "source_name": "Les-aides.fr",
        "source_url": "https://les-aides.fr/aide/aide-developpement-tourisme-vert",
        "raw_content": (
            "Aide au développement du tourisme vert — Région Nouvelle-Aquitaine. "
            "Subvention jusqu'à 80 000 EUR pour les projets d'hébergement écotouristique. "
            "Date limite : 30 juin 2026. "
            "Bénéficiaires : hébergeurs touristiques, gîtes, chambres d'hôtes. "
            "Taux : 40 % des dépenses éligibles."
        ),
        "expected": {
            "title": "Aide développement tourisme vert — Région Nouvelle-Aquitaine",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": True,
            "organism": "Région Nouvelle-Aquitaine",
            "amount_min": None,
            "amount_max": 80_000,
            "currency": "EUR",
            "amount_type": "beneficiary_amount",
            "deadline": "2026-06-30",
            "is_recurring": False,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "VALID",
        },
    },

    # ══════════════════════════════════════════════
    # CATÉGORIE B — SUSPECT (publiables mais incomplets)
    # ══════════════════════════════════════════════

    {
        "id": "B01",
        "category": "B",
        "source_name": "Aides-territoires ANCT",
        "source_url": "/aides/1209-aide-renovation-batiments-collectivites",  # URL relative
        "raw_content": (
            "Aide à la rénovation des bâtiments des collectivités — ANCT. "
            "Soutien aux collectivités pour la rénovation énergétique. "
            "Description complète disponible sur la page dédiée. "
            "Aucun montant communiqué. Aucune date limite communiquée."
        ),
        "expected": {
            "title": "Aide rénovation bâtiments collectivités — ANCT",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,  # URL relative → REVIEW_REQUIRED
            "organism": "ANCT",
            "amount_min": None,
            "amount_max": None,
            "currency": "EUR",
            "amount_type": "unknown",
            "deadline": None,
            "is_recurring": None,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "B02",
        "category": "B",
        "source_name": "Les-aides.fr",
        "source_url": "https://les-aides.fr/aide/accompagnement-commercialisation",
        "raw_content": (
            "Accompagnement à la commercialisation — CCI Hauts-de-France. "
            "Aide aux entreprises pour développer leur stratégie commerciale. "
            "Sans date limite communiquée. Organisme : CCI Hauts-de-France."
        ),
        "expected": {
            "title": "Accompagnement à la commercialisation",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": True,
            "organism": "CCI Hauts-de-France",  # agrégateur ici = aussi financeur
            "amount_min": None,
            "amount_max": None,
            "currency": "EUR",
            "amount_type": "unknown",
            "deadline": None,
            "is_recurring": None,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "SUSPECT",
        },
    },

    {
        "id": "B03",
        "category": "B",
        "source_name": "Aides-entreprises.fr",
        "source_url": "https://www.aides-entreprises.fr/aide/1234-export-pme",
        "raw_content": (
            "Aide au développement export PME — Bpifrance. "
            "Subvention pour les PME souhaitant se développer à l'export. "
            "Montant et date limite : contacter l'antenne Bpifrance régionale. "
            "Source : www.aides-entreprises.fr (portail DGE)."
        ),
        "expected": {
            "title": "Aide développement export PME — Bpifrance",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": True,
            "organism": "Bpifrance",
            "amount_min": None,
            "amount_max": None,
            "currency": "EUR",
            "amount_type": "unknown",
            "deadline": None,
            "is_recurring": None,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "SUSPECT",
        },
    },

    {
        "id": "B04",
        "category": "B",
        "source_name": "Banque Mondiale",
        "source_url": "https://projects.worldbank.org/en/projects-operations/project-detail/P180276",
        "raw_content": (
            "Mali Agricultural Sector Transformation Project. "
            "Total budget: USD 200 million. "
            "World Bank loan to Government of Mali. "
            "For investment in agricultural productivity and resilience. "
            "Project duration: 2024–2030."
        ),
        "expected": {
            "title": "Projet transformation secteur agricole — Mali (Banque Mondiale)",
            "content_nature": "INSTITUTIONAL_PROJECT",
            "should_publish": False,
            "organism": "Banque Mondiale",
            "amount_min": None,
            "amount_max": None,
            "currency": "USD",
            "amount_type": "program_budget",
            "deadline": "2030-12-31",
            "is_recurring": False,
            "country": "Mali",
            "source_language": "en",
            "requires_translation": True,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "B05",
        "category": "B",
        "source_name": "Global South Opportunities",
        "source_url": "https://globalsouthopportunities.com/travel-elevates-2026/",
        "raw_content": (
            "Travel Elevates 2027 — Grants for Travel Education Initiatives. "
            "Funding up to USD 50 000 for educational tourism projects. "
            "Deadline: September 30, 2026. "
            "Open to NGOs and social enterprises in the Global South."
        ),
        "expected": {
            "title": "Travel Elevates 2027 — subventions impact éducation, technologie et développement",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,
            "organism": "Travel Elevates Foundation",
            "amount_min": None,
            "amount_max": 50_000,
            "currency": "USD",
            "amount_type": "beneficiary_amount",
            "deadline": "2026-09-30",
            "is_recurring": False,
            "country": "International",
            "source_language": "en",
            "requires_translation": True,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "B06",
        "category": "B",
        "source_name": "Aides-entreprises.fr",
        "source_url": "https://www.bpifrance.fr/nos-solutions/financement/prets/pret-honneur-solidaire",
        "raw_content": (
            "Prêt d'honneur solidaire — Initiative France. "
            "Prêt à taux zéro de 3 000 à 50 000 EUR accordé à titre personnel au créateur d'entreprise. "
            "Ouverture permanente, dépôt mensuel en comité territorial. "
            "Bénéficiaires : créateurs et repreneurs d'entreprise en difficultés financières."
        ),
        "expected": {
            "title": "Prêt d'honneur solidaire — Initiative France",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": True,
            "organism": "Initiative France",
            "amount_min": 3_000,
            "amount_max": 50_000,
            "currency": "EUR",
            "amount_type": "range",
            "deadline": None,
            "is_recurring": True,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "VALID",  # recurrent + amounts known
        },
    },

    {
        "id": "B07",
        "category": "B",
        "source_name": "CIPME",
        "source_url": "https://www.cipme.ci/appels-a-candidatures/export-2025",
        "raw_content": (
            "Appel à candidatures — Programme Export CIPME 2025. "
            "Soutien aux PME ivoiriennes souhaitant accéder aux marchés export. "
            "Subvention disponible. Dépôt avant le 1er octobre 2025."
        ),
        "expected": {
            "title": "Appel à candidatures Programme Export CIPME 2025",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": True,
            "organism": "CIPME",
            "amount_min": None,
            "amount_max": None,
            "currency": "XOF",
            "amount_type": "unknown",
            "deadline": "2025-10-01",
            "is_recurring": False,
            "country": "Côte d'Ivoire",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "SUSPECT",
        },
    },

    {
        "id": "B08",
        "category": "B",
        "source_name": "Aides-entreprises.fr",
        "source_url": "https://www.bpifrance.fr/nos-solutions/financement/prets/pret-participatif-relance",
        "raw_content": (
            "Prêt participatif Relance — Bpifrance. "
            "Prêt participatif entre 50 000 et 100 000 EUR, durée 8 ans. "
            "Classe incorrectement comme subvention dans le CSV source. "
            "Pour les PME et ETI françaises souhaitant renforcer leurs fonds propres."
        ),
        "expected": {
            "title": "Prêt participatif Relance — Bpifrance",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": True,
            "organism": "Bpifrance",
            "amount_min": 50_000,
            "amount_max": 100_000,
            "currency": "EUR",
            "amount_type": "range",
            "deadline": None,
            "is_recurring": True,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "VALID",
        },
    },

    {
        "id": "B09",
        "category": "B",
        "source_name": "Global South Opportunities",
        "source_url": "https://globalsouthopportunities.com/developpp-ventures-2026/",
        "raw_content": (
            "develoPPP Ventures 2026 — financement startups africaines. "
            "Up to USD 200 000 per startup. "
            "Deadline: November 30, 2025. "
            "For startups operating in Sub-Saharan Africa. "
            "Currency erroneously stored as MAD in database."
        ),
        "expected": {
            "title": "develoPPP Ventures 2026 — financement startups africaines en croissance",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,
            "organism": "GIZ develoPPP",
            "amount_min": None,
            "amount_max": 200_000,
            "currency": "USD",
            "amount_type": "beneficiary_amount",
            "deadline": "2025-11-30",
            "is_recurring": False,
            "country": "International",
            "source_language": "en",
            "requires_translation": True,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "B10",
        "category": "B",
        "source_name": "Aides-territoires",
        "source_url": "/aides/5678-aide-renaturation-cours-eau",
        "raw_content": (
            "Aide renaturation cours d'eau "
            "Aide renaturation cours d'eau. "  # title == short_description
            "Objectif : soutenir les collectivités dans la renaturation. "
            "Sans montant communiqué. Sans date limite communiquée."
        ),
        "expected": {
            "title": "Aide renaturation cours d'eau",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,
            "organism": "ANCT",
            "amount_min": None,
            "amount_max": None,
            "currency": "EUR",
            "amount_type": "unknown",
            "deadline": None,
            "is_recurring": None,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "REVIEW_REQUIRED",  # URL relative
        },
    },

    # ══════════════════════════════════════════════
    # CATÉGORIE C — INVALID / Faux positifs
    # ══════════════════════════════════════════════

    {
        "id": "C01",
        "category": "C",
        "source_name": "CIPME",
        "source_url": "https://www.cipme.ci/actualites/atelier-formation-mars-2025",
        "raw_content": (
            "Atelier de formation PME — Abidjan, mars 2025. "
            "Le CIPME organise un atelier de formation à destination des PME ivoiriennes. "
            "Thème : accès aux financements bancaires. "
            "Inscription gratuite, 50 places disponibles. "
            "Date : 14 mars 2025, Centre des Conférences d'Abidjan."
        ),
        "expected": {
            "title": "Atelier de formation PME Abidjan mars 2025",
            "content_nature": "EVENT",
            "should_publish": False,
            "organism": "CIPME",
            "amount_min": None,
            "amount_max": None,
            "currency": "XOF",
            "amount_type": "unknown",
            "deadline": "2025-03-14",
            "is_recurring": False,
            "country": "Côte d'Ivoire",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "C02",
        "category": "C",
        "source_name": "CIPME",
        "source_url": "https://www.cipme.ci/actualites/resultats-programme-appui-2024",
        "raw_content": (
            "Résultats du programme d'appui aux PME 2024. "
            "Le CIPME annonce les résultats de son programme d'appui : 142 entreprises accompagnées, "
            "1,2 milliards XOF mobilisés. Félicitations aux entreprises sélectionnées. "
            "La prochaine session sera ouverte en 2026."
        ),
        "expected": {
            "title": "Résultats programme appui PME 2024 — CIPME",
            "content_nature": "RESULT_ANNOUNCEMENT",
            "should_publish": False,
            "organism": "CIPME",
            "amount_min": None,
            "amount_max": None,
            "currency": "XOF",
            "amount_type": "program_budget",
            "deadline": None,
            "is_recurring": False,
            "country": "Côte d'Ivoire",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "INVALID",
        },
    },

    {
        "id": "C03",
        "category": "C",
        "source_name": "FONSTI",
        "source_url": "https://www.fonsti.ci/actualites/ceremonie-remise-prix-2025",
        "raw_content": (
            "Cérémonie de remise des prix Innovation FONSTI 2025. "
            "Le FONSTI a organisé sa cérémonie annuelle de remise des prix. "
            "10 lauréats récompensés. Le Ministre de l'Enseignement Supérieur était présent. "
            "Retour sur les temps forts de la cérémonie."
        ),
        "expected": {
            "title": "Cérémonie remise prix Innovation FONSTI 2025",
            "content_nature": "RESULT_ANNOUNCEMENT",
            "should_publish": False,
            "organism": "FONSTI",
            "amount_min": None,
            "amount_max": None,
            "currency": "XOF",
            "amount_type": "unknown",
            "deadline": None,
            "is_recurring": False,
            "country": "Côte d'Ivoire",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "INVALID",
        },
    },

    {
        "id": "C04",
        "category": "C",
        "source_name": "Banque Mondiale",
        "source_url": "https://projects.worldbank.org/en/projects-operations/project-detail/P176050",
        "raw_content": (
            "Cameroon Roads Rehabilitation Project. "
            "World Bank loan of USD 300 million to the Government of Cameroon. "
            "For rehabilitation of 500 km of national roads. "
            "Implementing agency: Ministry of Public Works. "
            "Not accessible to private sector or NGOs."
        ),
        "expected": {
            "title": "Projet réhabilitation routes nationales — Cameroun (Banque Mondiale)",
            "content_nature": "INSTITUTIONAL_PROJECT",
            "should_publish": False,
            "organism": "Banque Mondiale",
            "amount_min": None,
            "amount_max": None,
            "currency": "USD",
            "amount_type": "program_budget",
            "deadline": None,
            "is_recurring": False,
            "country": "Cameroun",
            "source_language": "en",
            "requires_translation": True,
            "quality_state": "INVALID",
        },
    },

    {
        "id": "C05",
        "category": "C",
        "source_name": "Global South Opportunities",
        "source_url": "https://globalsouthopportunities.com/agnes-junior-grants-2026/",
        "raw_content": (
            "Subvention - Subvention - AGNES Intra-Africa Mobility Grants for Junior Researchers 2026. "
            "Funding up to USD 7 500. Deadline March 31 2026. "
            "[Title has been corrupted by repeated prefix ingestion]"
        ),
        "expected": {
            "title": "AGNES Intra-Africa Mobility Grants for Junior Researchers 2026",  # after prefix stripping
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,
            "organism": "AGNES",
            "amount_min": None,
            "amount_max": 7_500,
            "currency": "USD",
            "amount_type": "beneficiary_amount",
            "deadline": "2026-03-31",
            "is_recurring": False,
            "country": "International",
            "source_language": "en",
            "requires_translation": True,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "C06",
        "category": "C",
        "source_name": "Aides-territoires",
        "source_url": "/aides/9999-aide-vegetation",  # URL relative non résolvable
        "raw_content": (
            "Aide végétalisation espaces urbains. "
            "Sans données supplémentaires. Source non disponible."
        ),
        "expected": {
            "title": "Aide végétalisation espaces urbains",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,
            "organism": "ANCT",
            "amount_min": None,
            "amount_max": None,
            "currency": "EUR",
            "amount_type": "unknown",
            "deadline": None,
            "is_recurring": None,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "C07",
        "category": "C",
        "source_name": "Source 403",
        "source_url": "https://exemple-source-403.fr/aide-inaccessible",
        "raw_content": "Impossible d'acceder a l'URL (HTTP 403 Forbidden).",
        "expected": {
            "title": "Aide inaccessible (403)",
            "content_nature": "UNKNOWN",
            "should_publish": False,
            "organism": None,
            "amount_min": None,
            "amount_max": None,
            "currency": "EUR",
            "amount_type": "unknown",
            "deadline": None,
            "is_recurring": None,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "INVALID",
        },
    },

    {
        "id": "C08",
        "category": "C",
        "source_name": "Aides-entreprises.fr",
        "source_url": "https://www.bpifrance.fr/nos-solutions/conseil/diagnostic-numerique",
        "raw_content": (
            "Diagnostic numérique TPE — Bpifrance. "
            "Bilan de maturité numérique de votre entreprise, réalisé par un expert. "
            "Prestation de conseil financée à 100 % par Bpifrance pour les TPE. "
            "Pas de financement direct — accompagnement uniquement. "
            "Pas de date limite, dispositif permanent."
        ),
        "expected": {
            "title": "Diagnostic numérique TPE — Bpifrance",
            "content_nature": "NON_FINANCIAL_SUPPORT",
            "should_publish": True,
            "organism": "Bpifrance",
            "amount_min": None,
            "amount_max": None,
            "currency": "EUR",
            "amount_type": "unknown",
            "deadline": None,
            "is_recurring": True,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "SUSPECT",  # non-financial but publishable
        },
    },

    {
        "id": "C09",
        "category": "C",
        "source_name": "VC4A",
        "source_url": "https://vc4a.com/programs/orange-social-venture-prize-2026/",
        "raw_content": (
            "Orange Social Venture Prize 2026. "
            "The Orange Social Venture Prize rewards the best social and solidarity-based "
            "digital initiatives in Africa and the Middle East. "
            "Prize of 25 000 EUR per winner. Deadline: September 15, 2026. "
            "Apply via the VC4A platform."
        ),
        "expected": {
            "title": "Orange Social Venture Prize 2026",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,
            "organism": "Orange Foundation",
            "amount_min": None,
            "amount_max": 25_000,
            "currency": "EUR",
            "amount_type": "beneficiary_amount",
            "deadline": "2026-09-15",
            "is_recurring": False,
            "country": "International",
            "source_language": "en",
            "requires_translation": True,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "C10",
        "category": "C",
        "source_name": "CIPME",
        "source_url": "https://www.cipme.ci/actualites/signature-convention-bni-2025",
        "raw_content": (
            "Signature de convention — CIPME et BNI Côte d'Ivoire. "
            "Le CIPME et la BNI ont signé une convention de partenariat stratégique "
            "pour faciliter l'accès au financement des PME. "
            "Cette collaboration permettra aux entreprises appuyées par le CIPME "
            "de bénéficier de conditions préférentielles auprès de la BNI."
        ),
        "expected": {
            "title": "Signature convention partenariat CIPME-BNI 2025",
            "content_nature": "NEWS",
            "should_publish": False,
            "organism": "CIPME",
            "amount_min": None,
            "amount_max": None,
            "currency": "XOF",
            "amount_type": "unknown",
            "deadline": None,
            "is_recurring": False,
            "country": "Côte d'Ivoire",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "INVALID",
        },
    },

    # ══════════════════════════════════════════════
    # CATÉGORIE D — Edge cases
    # ══════════════════════════════════════════════

    {
        "id": "D01",
        "category": "D",
        "source_name": "Bpifrance",
        "source_url": "https://www.bpifrance.fr/nos-solutions/financement/prets/pret-croissance-industrie-expire",
        "raw_content": (
            "Prêt Croissance Industrie — dispositif clos. "
            "Ce dispositif a été clôturé le 31 mars 2025. "
            "Aucune nouvelle candidature n'est acceptée."
        ),
        "expected": {
            "title": "Prêt Croissance Industrie — dispositif clos",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,
            "organism": "Bpifrance",
            "amount_min": None,
            "amount_max": None,
            "currency": "EUR",
            "amount_type": "unknown",
            "deadline": "2025-03-31",
            "is_recurring": False,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "D02",
        "category": "D",
        "source_name": "ADEME",
        "source_url": "https://www.ademe.fr/nos-financements/eco-industrie-innovante",
        "raw_content": (
            "Programme Eco-industries innovantes — ADEME. "
            "Subvention récurrente annuelle pour projets d'éco-conception industrielle. "
            "Chaque année, appel à projets en janvier. Montant max 150 000 EUR. "
            "Récurrence confirmée : 8 éditions consécutives depuis 2018."
        ),
        "expected": {
            "title": "Programme Eco-industries innovantes — ADEME",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": True,
            "organism": "ADEME",
            "amount_min": None,
            "amount_max": 150_000,
            "currency": "EUR",
            "amount_type": "beneficiary_amount",
            "deadline": None,
            "is_recurring": True,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "VALID",
        },
    },

    {
        "id": "D03",
        "category": "D",
        "source_name": "Import manuel",
        "source_url": "https://www.globalfundforwomen.org/grantmaking/",
        "raw_content": (
            "Global Fund for Women — Grantmaking Program. "
            "Grants from USD 5 000 to USD 30 000 for women-led organizations worldwide. "
            "Ongoing rolling submissions. "
            "Open to any country — no geographic restriction."
        ),
        "expected": {
            "title": "Global Fund for Women — programme de subventions",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,
            "organism": "Global Fund for Women",
            "amount_min": 5_000,
            "amount_max": 30_000,
            "currency": "USD",
            "amount_type": "range",
            "deadline": None,
            "is_recurring": True,
            "country": "International",
            "source_language": "en",
            "requires_translation": True,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "D04",
        "category": "D",
        "source_name": "FONSTI",
        "source_url": "https://www.fonsti.ci/financement-projets-xof",
        "raw_content": (
            "Financement de projets de recherche — FONSTI. "
            "Subvention jusqu'à 25 000 000 XOF par projet. "
            "Dispositif spécifique Côte d'Ivoire, en franc CFA."
        ),
        "expected": {
            "title": "Financement projets de recherche — FONSTI",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": True,
            "organism": "FONSTI",
            "amount_min": None,
            "amount_max": 25_000_000,
            "currency": "XOF",
            "amount_type": "beneficiary_amount",
            "deadline": None,
            "is_recurring": True,
            "country": "Côte d'Ivoire",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "SUSPECT",
        },
    },

    {
        "id": "D05",
        "category": "D",
        "source_name": "Global South Opportunities (admin_only correct)",
        "source_url": "https://globalsouthopportunities.com/some-open-ended-program/",
        "raw_content": (
            "Some Open Ended Climate Program 2026. "
            "Supporting climate adaptation in Sub-Saharan Africa. "
            "No deadline specified. Apply anytime."
        ),
        "expected": {
            "title": None,  # admin_only → not published
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,
            "organism": None,
            "amount_min": None,
            "amount_max": None,
            "currency": "USD",
            "amount_type": "unknown",
            "deadline": None,
            "is_recurring": None,
            "country": "International",
            "source_language": "en",
            "requires_translation": True,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "D06",
        "category": "D",
        "source_name": "Bpifrance",
        "source_url": "https://www.bpifrance.fr/nos-solutions/past-device",
        "raw_content": (
            "Aide à l'investissement industriel — dispositif passé. "
            "Date limite : 15 février 2025. "
            "Statut incorrect en base : open. La date est dépassée."
        ),
        "expected": {
            "title": "Aide investissement industriel — dispositif passé",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,  # close_date in past + status open → REVIEW_REQUIRED
            "organism": "Bpifrance",
            "amount_min": None,
            "amount_max": None,
            "currency": "EUR",
            "amount_type": "unknown",
            "deadline": "2025-02-15",
            "is_recurring": False,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "D07",
        "category": "D",
        "source_name": "Import CSV",
        "source_url": "https://www.exemple-source.fr/aide-encoding",
        "raw_content": "Aide Ã  l'innovation numÃ©rique pour les PME. Budget : 50 000 â‚¬. Contact : aide@exemple.fr",
        "expected": {
            "title": "Aide à l'innovation numérique pour les PME",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,
            "organism": None,
            "amount_min": None,
            "amount_max": 50_000,
            "currency": "EUR",
            "amount_type": "beneficiary_amount",
            "deadline": None,
            "is_recurring": None,
            "country": "France",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "D08",
        "category": "D",
        "source_name": "Global South Opportunities (contradictory state)",
        "source_url": "https://globalsouthopportunities.com/contradictory-device/",
        "raw_content": (
            "Some program with admin_only tag but auto_published status. "
            "Deadline: January 31, 2026. Budget: USD 5 000 per grantee."
        ),
        "expected": {
            "title": None,
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,
            "organism": None,
            "amount_min": None,
            "amount_max": 5_000,
            "currency": "USD",
            "amount_type": "beneficiary_amount",
            "deadline": "2026-01-31",
            "is_recurring": False,
            "country": "International",
            "source_language": "en",
            "requires_translation": True,
            "quality_state": "REVIEW_REQUIRED",
        },
    },

    {
        "id": "D09",
        "category": "D",
        "source_name": "FONSTI (doublon sémantique)",
        "source_url": "https://www.fonsti.ci/appels-a-projets/technologie-2025",
        "raw_content": (
            "Appel à Projets Technologie 2025 — FONSTI. "
            "Même programme que l'AAP Innovation 2025 mais indexé via une autre URL. "
            "Date limite : 30 septembre 2025. Montant max : 50 000 000 XOF."
        ),
        "expected": {
            "title": "Appel à Projets Technologie 2025 — FONSTI",
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": True,
            "organism": "FONSTI",
            "amount_min": None,
            "amount_max": 50_000_000,
            "currency": "XOF",
            "amount_type": "beneficiary_amount",
            "deadline": "2025-09-30",
            "is_recurring": False,
            "country": "Côte d'Ivoire",
            "source_language": "fr",
            "requires_translation": False,
            "quality_state": "VALID",
        },
    },

    {
        "id": "D10",
        "category": "D",
        "source_name": "GSO admin_only correct (AGRA)",
        "source_url": "https://globalsouthopportunities.com/agra-research-fund/",
        "raw_content": (
            "AGRA Research Fund for African Agriculture. "
            "Grants for agricultural research in sub-Saharan Africa. "
            "Application process ongoing — no specific deadline. "
            "Eligibility: African research institutions."
        ),
        "expected": {
            "title": None,
            "content_nature": "FINANCING_OPPORTUNITY",
            "should_publish": False,
            "organism": "AGRA",
            "amount_min": None,
            "amount_max": None,
            "currency": "USD",
            "amount_type": "unknown",
            "deadline": None,
            "is_recurring": True,
            "country": "International",
            "source_language": "en",
            "requires_translation": True,
            "quality_state": "REVIEW_REQUIRED",
        },
    },
]


def get_cases_by_category(category: str) -> list:
    return [c for c in GOLDEN_DATASET if c["category"] == category]


def get_cases_expecting_publish() -> list:
    return [c for c in GOLDEN_DATASET if c["expected"]["should_publish"]]


def get_cases_expecting_no_publish() -> list:
    return [c for c in GOLDEN_DATASET if not c["expected"]["should_publish"]]
