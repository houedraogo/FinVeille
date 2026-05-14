import asyncio
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.source import Source
from app.utils.text_utils import generate_slug, normalize_title


TARGET_SOURCES = [
    {
        "name": "Orange Corners Benin - subventions OCIAC et OCIF",
        "organism": "Orange Corners / RVO",
        "country": "Bénin",
        "region": "Bénin",
        "source_type": "portail_officiel",
        "level": 1,
        "url": "https://www.orangecorners.com/orange-corners-subsidy-programmes-open-in-benin/",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Source officielle Orange Corners. Appel ponctuel à intégrer en manuel car la page est éditoriale.",
    },
    {
        "name": "UNIDO - A2D Facility calls",
        "organism": "UNIDO / UNGM",
        "country": "Afrique",
        "region": "Bénin, Burkina Faso, Côte d'Ivoire",
        "source_type": "institution_internationale",
        "level": 1,
        "url": "https://www.ungm.org/Public/Notice/297738",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Appels internationaux UNGM. Eligible pour plusieurs pays ODA dont Bénin, Burkina Faso et Côte d'Ivoire.",
    },
    {
        "name": "FONAME Côte d'Ivoire",
        "organism": "Direction Générale de l'Énergie - Côte d'Ivoire",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "source_type": "agence_nationale",
        "level": 1,
        "url": "https://www.dgenergie.ci/article-detail/53/284/avis-d-appel-a-projets-foname-2026",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "public",
        "notes": "Portefeuille de projets énergie. Pas une subvention directe immédiate, mais source stratégique à surveiller.",
    },
    {
        "name": "Investing for Employment - Côte d'Ivoire 2026",
        "organism": "Invest for Jobs / KfW",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "source_type": "institution_internationale",
        "level": 1,
        "url": "https://invest-for-jobs.com/en/investing-for-employment",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Appel officiel IFE 2026 pour projets créateurs d'emplois en Côte d'Ivoire.",
    },
    {
        "name": "Digital Energy Challenge 2026",
        "organism": "AFD / Digital Energy Facility",
        "country": "Afrique",
        "region": "Bénin, Côte d'Ivoire, Afrique",
        "source_type": "institution_internationale",
        "level": 1,
        "url": "https://digital-energy.eu/fr/digital-energy-challenge-appel-projets",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Challenge annuel AFD pour PME innovantes énergie digitale en Afrique.",
    },
    {
        "name": "ADPME Benin - e-PME et PAEB",
        "organism": "Agence de Developpement des PME du Benin",
        "country": "Benin",
        "region": "Benin",
        "source_type": "agence_nationale",
        "level": 1,
        "url": "https://epme.adpme.bj/",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Portail national e-PME. Source prioritaire pour l'accompagnement et l'acces au financement des PME beninoises.",
    },
    {
        "name": "FNDA Benin - financement agricole",
        "organism": "Fonds National de Developpement Agricole du Benin",
        "country": "Benin",
        "region": "Benin",
        "source_type": "agence_nationale",
        "level": 1,
        "url": "https://partenaires.fnda.bj/",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Guichet national agricole. Les appels ponctuels doivent etre verifies avant publication avec date.",
    },
    {
        "name": "AFP-PME Burkina Faso",
        "organism": "Agence de Financement et de Promotion des PME",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "agence_nationale",
        "level": 1,
        "url": "https://afppme.bf/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "public",
        "notes": "Agence nationale burkinabe proposant prets, incubation, prets d'honneur, bonification et fonds d'amorcage.",
    },
    {
        "name": "MEBF Burkina Faso - SEFAFI",
        "organism": "Maison de l'Entreprise du Burkina Faso",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "agence_nationale",
        "level": 1,
        "url": "https://monbusinessplan.me.bf/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "public",
        "notes": "Service national de facilitation du financement des entreprises par plans d'affaires et accompagnement bancaire.",
    },
    {
        "name": "FONRID Burkina Faso - recherche et innovation",
        "organism": "Fonds National de la Recherche et de l'Innovation pour le Developpement",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "agence_nationale",
        "level": 1,
        "url": "https://fonrid.com/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "public",
        "notes": "Fonds national pour appels a projets de recherche appliquee et innovation au Burkina Faso.",
    },
    {
        "name": "FONSTI Cote d'Ivoire - appels a projets",
        "organism": "Fonds pour la Science, la Technologie et l'Innovation",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "source_type": "agence_nationale",
        "level": 1,
        "url": "https://fonsti.org/appel-a-projets/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "public",
        "notes": "Guichet ivoirien de financement de la recherche, de l'innovation et de l'entrepreneuriat scientifique.",
    },
    {
        "name": "CCI-BF - Parcours du createur d'entreprise",
        "organism": "Chambre de Commerce et d'Industrie du Burkina Faso",
        "country": "Burkina Faso",
        "region": "Hauts-Bassins",
        "source_type": "chambre_consulaire",
        "level": 1,
        "url": "https://www.cci.bf/?q=fr%2Fdownload%2Ffile%2Ffid%2F1125",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "public",
        "notes": "Appel CCI-BF pour le financement de 60 initiatives d'entreprises dans les Hauts-Bassins.",
    },
    {
        "name": "CCI-BF - ZAD Bobo",
        "organism": "Chambre de Commerce et d'Industrie du Burkina Faso",
        "country": "Burkina Faso",
        "region": "Bobo-Dioulasso",
        "source_type": "chambre_consulaire",
        "level": 1,
        "url": "https://zadbobo.cci.bf/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "public",
        "notes": "Souscription aux parcelles de la zone d'activites diverses de Bobo-Dioulasso, utile pour projets productifs.",
    },
    {
        "name": "CNFEM Cote d'Ivoire - microfinancements FEM",
        "organism": "Commission Nationale du Fonds pour l'Environnement Mondial",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "source_type": "agence_nationale",
        "level": 1,
        "url": "https://cnfem.finances.gouv.ci/comment-soumettre-un-projet/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "public",
        "notes": "Programme de microfinancements FEM pour ONG, cooperatives, mutuelles et entreprises sociales en Cote d'Ivoire.",
    },
    {
        "name": "WEDAF Benin - entrepreneuriat feminin et acces au financement",
        "organism": "Ministere des PME et de la Promotion de l'Emploi du Benin",
        "country": "Benin",
        "region": "Benin",
        "source_type": "programme_national",
        "level": 1,
        "url": "https://pmepe.gouv.bj/article/81/projet-developpement-entrepreneuriat-feminin-acces-financement-wedaf",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Projet Banque mondiale de 100 M USD pour l'entrepreneuriat feminin et l'acces au financement au Benin.",
    },
    {
        "name": "Cote d'Ivoire PME - appels a projets",
        "organism": "Agence Cote d'Ivoire PME",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "source_type": "agence_nationale",
        "level": 2,
        "url": "https://cipme.ci/appel-projets/",
        "collection_mode": "manual",
        "reliability": 3,
        "category": "public",
        "notes": "Page de veille des appels a projets pour PME ivoiriennes. A surveiller et qualifier avant publication automatique.",
    },
    {
        "name": "Service Public Burkina Faso - FAIJ micro-projets jeunes",
        "organism": "Fonds d'Appui aux Initiatives des Jeunes",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "portail_officiel",
        "level": 1,
        "url": "https://servicepublic.gov.bf/fiches/emploi-financement-de-micro-projets",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Procedure officielle de financement des micro-projets jeunes via FAIJ.",
    },
    {
        "name": "Service Public Burkina Faso - FASI secteur informel",
        "organism": "Fonds d'Appui au Secteur Informel",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "portail_officiel",
        "level": 1,
        "url": "https://servicepublic.gov.bf/fiches/emploi-financement-de-microprojets",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Procedure officielle de credits pour microprojets du secteur informel.",
    },
    {
        "name": "Service Public Burkina Faso - financement AGR femmes",
        "organism": "Fonds d'Appui aux Activites Remuneratrices des Femmes",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "portail_officiel",
        "level": 1,
        "url": "https://servicepublic.gov.bf/fiches/emploi-demande-de-financement-des-activites-generatrices-de-revenus",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Procedure officielle de credits aux femmes pour activites generatrices de revenus.",
    },
    {
        "name": "Service Public Burkina Faso - microprojets jeunes diplomes",
        "organism": "Direction Generale de l'Insertion Professionnelle et de l'Emploi",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "portail_officiel",
        "level": 1,
        "url": "https://www.servicepublic.gov.bf/fiches/emploi-financement-des-microprojets-des-jeunes-diplomes-du-superieur",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Procedure officielle de financement des projets innovants portes par jeunes diplomes.",
    },
    {
        "name": "Benin - Micro Credit Alafia",
        "organism": "Fonds National de la Microfinance du Benin",
        "country": "Benin",
        "region": "Benin",
        "source_type": "programme_national",
        "level": 1,
        "url": "https://social.gouv.bj/micro-credit-alafia",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Programme national de microcredit pour personnes vulnerables et activites generatrices de revenus.",
    },
    {
        "name": "Benin - ProPME",
        "organism": "Ministere des PME et de la Promotion de l'Emploi du Benin",
        "country": "Benin",
        "region": "Benin",
        "source_type": "programme_national",
        "level": 1,
        "url": "https://pmepe.gouv.bj/article/86/projets-financement-s-a-etablissement-credit-specialise-dans-credits-pme",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Programme ProPME pour renforcer la croissance et la competitivite des MPME au Benin.",
    },
    {
        "name": "ADERIZ Cote d'Ivoire - appels et filiere riz",
        "organism": "Agence pour le Developpement de la Filiere Riz",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "source_type": "agence_nationale",
        "level": 2,
        "url": "https://www.aderiz.ci/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "public",
        "notes": "Source agricole ivoirienne a surveiller pour appels a manifestation d'interet et appuis filiere riz.",
    },
    {
        "name": "Orange Digital Center Burkina Faso - Damina",
        "organism": "Orange Digital Center Burkina Faso",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "incubateur",
        "level": 2,
        "url": "https://digitalmagazine.bf/2026/03/28/orange-digital-center-odc-lance-un-appel-a-candidature-pour-le-programme-damina-2026/",
        "collection_mode": "manual",
        "reliability": 3,
        "category": "private",
        "notes": "Programme Damina d'accompagnement startup. Source secondaire a surveiller pour les prochaines cohortes.",
    },
    {
        "name": "MTN Innovation Lab Benin",
        "organism": "MTN Benin",
        "country": "Benin",
        "region": "Benin",
        "source_type": "incubateur",
        "level": 2,
        "url": "https://innovation.mtn.bj/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "private",
        "notes": "Incubateur startup au Benin avec mentoring, partenariats et acces au financement.",
    },
    {
        "name": "Hub Ivoire Tech",
        "organism": "Hub Ivoire Tech",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "source_type": "incubateur",
        "level": 2,
        "url": "https://hubivoire.tech/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "public",
        "notes": "Campus ivoirien de startups, incubateurs, accelerateurs, investisseurs et mentors.",
    },
    {
        "name": "BeoogoLAB Burkina Faso",
        "organism": "BeoogoLAB",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "incubateur",
        "level": 2,
        "url": "https://www.beoogolab.org/",
        "collection_mode": "manual",
        "reliability": 3,
        "category": "private",
        "notes": "Startup studio burkinabe. Source a surveiller pour accompagnement, incubation et projets tech.",
    },
    {
        "name": "PNUD Burkina Faso - PMF FEM environnement",
        "organism": "PNUD / Programme de Microfinancements FEM",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "institution_internationale",
        "level": 1,
        "url": "https://www.undp.org/fr/burkina-faso/actualites/appel-projets-microfinancements-dans-le-secteur-de-lenvironnement",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "PMF/FEM Burkina Faso. L'appel 2025 est expire, mais le guichet environnement est recurrent.",
    },
    {
        "name": "OIF - appels a projets francophonie",
        "organism": "Organisation internationale de la Francophonie",
        "country": "International",
        "region": "Afrique de l'Ouest",
        "source_type": "institution_internationale",
        "level": 1,
        "url": "https://www.francophonie.org/appels-projets-candidatures-initiatives-1111",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Portail OIF des appels a projets, candidatures et initiatives pour pays francophones.",
    },
    {
        "name": "ASNOM - Fonds de Solidarite Sante Navale",
        "organism": "ASNOM / FSSN",
        "country": "International",
        "region": "Afrique",
        "source_type": "fondation",
        "level": 2,
        "url": "https://www.asnom.org/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "private",
        "notes": "Appel a projets sante locale pour 2027, utile pour associations et acteurs de sante en Afrique.",
    },
    {
        "name": "CORAF - innovations agricoles Afrique de l'Ouest",
        "organism": "CORAF",
        "country": "Afrique de l'Ouest",
        "region": "Afrique de l'Ouest",
        "source_type": "institution_regionale",
        "level": 1,
        "url": "https://www.coraf.org/passation-marche",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Source regionale pour appels MITA, Prix Abdoulaye Toure et innovation agricole.",
    },
    {
        "name": "BOAD Development Days - appels a projets",
        "organism": "Banque Ouest Africaine de Developpement",
        "country": "Afrique de l'Ouest",
        "region": "UEMOA",
        "source_type": "institution_regionale",
        "level": 2,
        "url": "https://www.boaddevelopmentdays.com/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "public",
        "notes": "Rendez-vous regional BOAD pouvant publier des appels a projets agriculture, energie et climat.",
    },
    {
        "name": "LuxAid Challenge Fund Benin",
        "organism": "LuxDev / LuxAid Business4Impact",
        "country": "Benin",
        "region": "Benin",
        "source_type": "institution_internationale",
        "level": 1,
        "url": "https://www.luxaidbusiness4impact.lu/fr/opportunites/",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Portail LuxAid Business4Impact. Le LCF Benin finance des entreprises beninoises innovantes avec cofinancement.",
    },
    {
        "name": "Gouvernement Benin - appels FNDA agriculture",
        "organism": "Gouvernement du Benin / FNDA",
        "country": "Benin",
        "region": "Benin",
        "source_type": "portail_officiel",
        "level": 1,
        "url": "https://www.gouv.bj/article/3241/",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Page gouvernementale d'appels FNDA pour investissements agricoles, services non financiers et innovation agricole.",
    },
    {
        "name": "Gouvernement Benin - PIICC incubation ICC",
        "organism": "ADAC / Gouvernement du Benin",
        "country": "Benin",
        "region": "Benin",
        "source_type": "portail_officiel",
        "level": 1,
        "url": "https://www.gouv.bj/article/3244/appel-candidatures-programme-incubation-secteur-industries-culturelles-creatives-benin/",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Programme d'incubation pour entrepreneurs culturels et creatifs au Benin.",
    },
    {
        "name": "Mastercard Foundation EdTech Fellowship Benin",
        "organism": "Mastercard Foundation / CPCCAF",
        "country": "Benin",
        "region": "Benin, Senegal",
        "source_type": "fondation",
        "level": 1,
        "url": "https://cpccaf.org/programme-et-appel-a-projet/appel-a-candidatures-mastercard-foundation-edtech-fellowship-cohorte-3-benin-senegal/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "private",
        "notes": "Programme EdTech recurrent a surveiller pour startups education au Benin.",
    },
    {
        "name": "FDCT Burkina Faso - culture et tourisme",
        "organism": "Fonds de Developpement Culturel et Touristique",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "fonds_national",
        "level": 1,
        "url": "https://www.fdct-bf.org/",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Fonds national burkinabe pour financement, subventions, prets et accompagnement culture/tourisme.",
    },
    {
        "name": "ECOTEC Burkina Faso - fonds de partenariat MPME",
        "organism": "Projet ECOTEC / Maison de l'Entreprise du Burkina Faso",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "programme_national",
        "level": 1,
        "url": "https://ecotec.me.bf/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "public",
        "notes": "Projet Banque mondiale pour MPME, adoption technologique, competences et financement au Burkina Faso.",
    },
    {
        "name": "PEEB Awards Burkina Faso",
        "organism": "PEEB Awards",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "concours",
        "level": 2,
        "url": "https://burkina24.com/2026/05/08/peeb-awards-2026-ouagadougou-veut-accelerer-lindustrialisation-et-reveler-les-champions-de-lentrepreneuriat-burkinabe/",
        "collection_mode": "manual",
        "reliability": 3,
        "category": "private",
        "notes": "Concours et plateforme de visibilite pour entrepreneurs et industriels burkinabe. Source a qualifier manuellement.",
    },
    {
        "name": "FIN CULTURE Cote d'Ivoire",
        "organism": "Ministere de la Culture et de la Francophonie / AEJ",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "source_type": "programme_national",
        "level": 1,
        "url": "https://culture.gouv.ci/projets/appel-a-projet-le-guichet-fin-culture-est-officiellement-ouvert/",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Guichet de prets FIN CULTURE pour acteurs ICC ivoiriens, a verifier pour les prochaines sessions.",
    },
    {
        "name": "Moov Innovation Cote d'Ivoire",
        "organism": "Moov Africa Cote d'Ivoire",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "source_type": "concours",
        "level": 2,
        "url": "https://www.moov-africa.ci/moov-innovation/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "private",
        "notes": "Concours innovation et startup numerique en Cote d'Ivoire.",
    },
    {
        "name": "Yello Startup Cote d'Ivoire",
        "organism": "MTN Cote d'Ivoire",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "source_type": "incubateur",
        "level": 2,
        "url": "https://yellostartup.mtn.ci/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "private",
        "notes": "Programme entrepreneurial MTN pour startups et solutions digitales a impact.",
    },
    {
        "name": "FIRCA NSIA Banque CI - agrotransformation",
        "organism": "FIRCA / NSIA Banque Cote d'Ivoire",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "source_type": "fonds_sectoriel",
        "level": 1,
        "url": "https://www.aip.ci/322325/cote-divoire-aip-programme-firca-nsia-banque-ci-les-criteres-et-modalites-du-premier-appel-a-projets-devoiles-fiche-technique/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "public",
        "notes": "Programme de financement des PME d'agro-transformation en Cote d'Ivoire, a surveiller pour les prochaines editions.",
    },
    {
        "name": "CECI MTWW - commerce feminin Afrique de l'Ouest",
        "organism": "CECI / TradeMark Africa / Affaires mondiales Canada",
        "country": "Afrique de l'Ouest",
        "region": "Benin, Burkina Faso, Cote d'Ivoire",
        "source_type": "ong_internationale",
        "level": 1,
        "url": "https://ceci.org/fr/nouvelles-et-evenements/appel-a-manifestation-dinteret-pre-selection-dentreprises-feminines-porteuses-de-projet-dexpansion-commerciale-sur-les-marches-regionaux-et-transfrontaliers-en-afrique-de-louest",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Projet MTWW 2024-2029 pour entreprises feminines et commerce transfrontalier en Afrique de l'Ouest.",
    },
    {
        "name": "SOE Benin - Semaine d'Opportunites aux Entrepreneurs",
        "organism": "SOE Benin",
        "country": "Benin",
        "region": "Benin",
        "source_type": "evenement_business",
        "level": 2,
        "url": "https://soe-benin.com/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "private",
        "notes": "Evenement business a Cotonou pour entrepreneurs, investisseurs, B2B et opportunites internationales.",
    },
    {
        "name": "African Cashew Alliance - appels cajou",
        "organism": "African Cashew Alliance",
        "country": "Afrique",
        "region": "Benin, Burkina Faso, Cote d'Ivoire",
        "source_type": "organisation_sectorielle",
        "level": 2,
        "url": "https://www.africancashewalliance.com/fr/news-and-info/cashew-news/2026-appel-candidatures-rejoignez-notre-initiative-du-systeme",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "private",
        "notes": "Source sectorielle cajou avec appels a candidatures, donnees marche et missions d'expertise.",
    },
    {
        "name": "Fondation Facilite Sahel - appels ONG locales",
        "organism": "Fondation Facilite Sahel",
        "country": "Sahel",
        "region": "Burkina Faso, Mali, Mauritanie, Niger, Tchad",
        "source_type": "fondation",
        "level": 1,
        "url": "https://www.pseau.org/appel-projet/la-fondation-facilite-sahel-lance-son-appel-a-projet/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "private",
        "notes": "Appels pour ONG locales au Sahel, avec prequalification 2026 en vue d'un appel debut 2027.",
    },
    {
        "name": "OSEZ Afrique de l'Ouest francophone",
        "organism": "T World Investment",
        "country": "Afrique de l'Ouest",
        "region": "Benin, Burkina Faso, Cote d'Ivoire, Togo, Niger",
        "source_type": "concours",
        "level": 2,
        "url": "https://startupmedias.africa/articles/osez-lappel-de-projet-dedie-aux-entrepreneurs-dafrique-occidentale-francophone",
        "collection_mode": "manual",
        "reliability": 3,
        "category": "private",
        "notes": "Concours prive regional pour entrepreneurs francophones d'Afrique de l'Ouest, a qualifier avant publication open.",
    },
    {
        "name": "Nice African Talents Awards Cote d'Ivoire",
        "organism": "Nicepay Group",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "source_type": "concours",
        "level": 2,
        "url": "https://nicepaygroup.com/Awards.php",
        "collection_mode": "manual",
        "reliability": 3,
        "category": "private",
        "notes": "Challenge jeunes entrepreneurs en Cote d'Ivoire, a surveiller pour les prochaines editions.",
    },
    {
        "name": "UNESCO FIDC - diversite culturelle",
        "organism": "UNESCO",
        "country": "International",
        "region": "Benin, Burkina Faso, Cote d'Ivoire",
        "source_type": "institution_internationale",
        "level": 1,
        "url": "https://www.unesco.org/creativity/fr/articles/lappel-demandes-de-financement-2026-du-fonds-international-pour-la-diversite-culturelle-est-present?hub=11",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Fonds international pour la diversite culturelle. Source annuelle utile pour ONG et institutions culturelles.",
    },
    {
        "name": "U.S. Embassy Abidjan - Freedom250 American Spaces",
        "organism": "U.S. Mission to Cote d'Ivoire",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "source_type": "ambassade",
        "level": 1,
        "url": "https://simpler.grants.gov/opportunity/018e7c4a-2f90-4cf5-b772-4976b21df920",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Grant officiel Grants.gov pour competences, employabilite, anglais, IA/coding et entrepreneuriat en Cote d'Ivoire.",
    },
    {
        "name": "AECF IIW Burkina Faso - entrepreneuriat feminin vert",
        "organism": "Africa Enterprise Challenge Fund",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "source_type": "fondation",
        "level": 1,
        "url": "https://www.aecfafrica.org/wp-content/uploads/2026/01/TOR-CALL-FOR-PROPOSALS-FOR-WRO-Burkina-Faso.pdf",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "private",
        "notes": "AECF Investing in Women pour entrepreneuriat feminin et economie verte au Burkina Faso.",
    },
    {
        "name": "AECF ODDF Benin - droits des femmes et entrepreneuriat",
        "organism": "Africa Enterprise Challenge Fund",
        "country": "Benin",
        "region": "Benin",
        "source_type": "fondation",
        "level": 1,
        "url": "https://www.aecfafrica.org/wp-content/uploads/2026/01/TDR-APPEL-A-PROJETS-ODDF-BENIN-FINAL.pdf",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "private",
        "notes": "Appel AECF pour organisations de defense des droits des femmes dans le cadre de l'entrepreneuriat feminin au Benin.",
    },
    {
        "name": "Fonds MIWA+ Afrique de l'Ouest",
        "organism": "Global Philanthropy Project / Fonds MIWA+",
        "country": "Afrique de l'Ouest",
        "region": "Benin, Burkina Faso, Cote d'Ivoire",
        "source_type": "fondation",
        "level": 2,
        "url": "https://globalphilanthropyproject.org/grants/fonds-miwa/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "private",
        "notes": "Fonds regional pour organisations LBTQI francophones en Afrique de l'Ouest.",
    },
    {
        "name": "WELA Rise - femmes entrepreneures Afrique francophone",
        "organism": "WELA Mawusse",
        "country": "Afrique francophone",
        "region": "Benin, Burkina Faso, Cote d'Ivoire",
        "source_type": "incubateur",
        "level": 2,
        "url": "https://www.wela-mawusse.com/wela-rise/",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "private",
        "notes": "Programme femmes entrepreneures : agrotransformation, tech inclusive, economie verte et levee de fonds.",
    },
    {
        "name": "Afrique Innovante - femmes entrepreneures CPCCAF",
        "organism": "CPCCAF / Afrique Innovante",
        "country": "Afrique",
        "region": "Benin, Burkina Faso, Cote d'Ivoire",
        "source_type": "concours",
        "level": 2,
        "url": "https://www.pi-francophone.org/blog/evenements-3/cpccaf-appel-a-candidatures-pour-femmes-entrepreneures-start-up-innovantes-et-pme-technologiques-africaines-68",
        "collection_mode": "manual",
        "reliability": 4,
        "category": "private",
        "notes": "Competition panafricaine pour femmes entrepreneures, startups innovantes et PME technologiques.",
    },
    {
        "name": "RISE 2 Benin - projet d'accompagnement PME",
        "organism": "RVO / Invest International / VC4A",
        "country": "Benin",
        "region": "Benin",
        "source_type": "programme_international",
        "level": 1,
        "url": "https://vc4a.com/rise/rise-2026/?lang=en",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Programme RISE 2 pour TPE/PME beninoises en croissance, avec appui technique et financier. Fenetre 2026 active.",
    },
    {
        "name": "CHINNOVA - climat et sante Afrique de l'Ouest",
        "organism": "Association of African Universities / CHINNOVA",
        "country": "Afrique de l'Ouest",
        "region": "Benin, Cote d'Ivoire",
        "source_type": "institution_recherche",
        "level": 1,
        "url": "https://chinnova.aau.org/chinnova-launches-second-call-for-proposals-to-strengthen-climate-resilient-health-systems-in-west-and-central-africa/",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Appels regionaux de recherche et innovation climat-sante en Afrique de l'Ouest et centrale.",
    },
    {
        "name": "FNEC Benin - environnement et climat",
        "organism": "Fonds National pour l'Environnement et le Climat du Benin",
        "country": "Benin",
        "region": "Benin",
        "source_type": "fonds_national",
        "level": 1,
        "url": "https://www.fnec.bj/appel-a-projet.php",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Fonds national beninois pour projets environnement, climat et developpement durable.",
    },
    {
        "name": "PeaceNexus - environnement et paix Afrique de l'Ouest",
        "organism": "PeaceNexus Foundation",
        "country": "Afrique de l'Ouest",
        "region": "Benin, Burkina Faso",
        "source_type": "fondation",
        "level": 1,
        "url": "https://peacenexus.org/environment-and-peace-open-calls-for-new-partners/",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "private",
        "notes": "Appels pour organisations environnementales integrant la sensibilite aux conflits, avec Benin et Burkina Faso eligibles.",
    },
    {
        "name": "OIF - cuisson propre Cote d'Ivoire",
        "organism": "Organisation internationale de la Francophonie",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "source_type": "institution_internationale",
        "level": 1,
        "url": "https://www.francophonie.org/consolidation-de-linitiative-cuisson-propre-en-cote-divoire-8442",
        "collection_mode": "manual",
        "reliability": 5,
        "category": "public",
        "notes": "Appel OIF pour projets autour de la cuisson propre en Cote d'Ivoire, utile climat/energie/entrepreneuriat social.",
    },
]


TARGET_DEVICES = [
    {
        "title": "Orange Corners Bénin - subventions OCIAC et OCIF 2026",
        "organism": "Orange Corners / RVO",
        "country": "Bénin",
        "region": "Bénin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "subvention",
        "sectors": ["entrepreneuriat", "formation", "finance", "jeunesse"],
        "beneficiaries": ["entreprise", "ong", "structure_accompagnement", "jeunes"],
        "short_description": (
            "Orange Corners finance un partenaire de mise en oeuvre au Bénin pour opérer un programme "
            "d'incubation/accélération et le Orange Corners Innovation Fund sur la période 2026-2033."
        ),
        "full_description": (
            "L'appel vise à sélectionner des partenaires locaux capables de gérer deux composantes : "
            "le programme OCIAC, dédié à la formation et à l'accompagnement entrepreneurial des jeunes "
            "de 18 à 35 ans, et le fonds OCIF, mécanisme d'accès au financement complété par de "
            "l'assistance technique. Le dispositif cible les organisations expérimentées dans "
            "l'accompagnement entrepreneurial, la gestion de fonds ou l'accès au financement au Bénin."
        ),
        "eligibility_criteria": (
            "Structures locales enregistrées au Bénin. Pour OCIAC : expérience en incubation, accélération, "
            "mentorat, services de développement d'affaires et gestion de programme. Pour OCIF : ONG ou "
            "entreprises privées ayant une expérience en gestion de fonds et autorisées à proposer des prêts "
            "sans intérêt selon le cadre local."
        ),
        "funding_details": (
            "OCIAC : enveloppe maximale de 750 000 EUR sur 2026-2031, couvrant jusqu'à 75% des coûts. "
            "OCIF : budget de 2,2 M EUR sur 2026-2033, couvrant jusqu'à 95% du budget avec 5% de contribution attendue."
        ),
        "amount_max": Decimal("2200000"),
        "currency": "EUR",
        "open_date": date(2026, 4, 22),
        "close_date": date(2026, 6, 4),
        "status": "open",
        "source_url": "https://www.orangecorners.com/orange-corners-subsidy-programmes-open-in-benin/",
        "source_name": "Orange Corners Benin - subventions OCIAC et OCIF",
        "keywords": ["Bénin", "Orange Corners", "OCIF", "OCIAC", "entrepreneuriat", "subvention"],
    },
    {
        "title": "UNIDO A2D Facility - projets de démonstration dans les pays éligibles ODA",
        "organism": "UNIDO",
        "country": "Afrique",
        "region": "Bénin, Burkina Faso, Côte d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "international",
        "device_type": "subvention",
        "aid_nature": "subvention",
        "sectors": ["industrie", "innovation", "environnement", "energie"],
        "beneficiaries": ["organisation", "entreprise", "ong", "institution"],
        "short_description": (
            "L'UNIDO lance un appel à propositions pour sélectionner des bénéficiaires de subventions "
            "chargés de mettre en oeuvre des projets de démonstration A2D dans des pays éligibles à l'aide publique au développement."
        ),
        "full_description": (
            "Cet appel à propositions vise des projets de démonstration dans des pays ODA, avec une liste "
            "incluant le Bénin, le Burkina Faso et la Côte d'Ivoire. Les candidats doivent soumettre leur "
            "proposition via UNGM et respecter les formulaires et annexes publiés avec l'avis officiel."
        ),
        "eligibility_criteria": (
            "Organisations capables de porter un projet de démonstration dans un pays éligible ODA, dont "
            "le Bénin, le Burkina Faso ou la Côte d'Ivoire. Les critères détaillés doivent être confirmés "
            "dans le dossier UNGM officiel."
        ),
        "funding_details": "Subvention attribuée après appel à propositions. Montant à confirmer dans les documents UNGM.",
        "open_date": date(2026, 4, 14),
        "close_date": date(2026, 6, 18),
        "status": "open",
        "source_url": "https://www.ungm.org/Public/Notice/297738",
        "source_name": "UNIDO - A2D Facility calls",
        "keywords": ["UNIDO", "UNGM", "Bénin", "Burkina Faso", "Côte d'Ivoire", "subvention"],
    },
    {
        "title": "FONAME Côte d'Ivoire - portefeuille national de projets énergie",
        "organism": "Direction Générale de l'Énergie - Côte d'Ivoire",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "aap",
        "aid_nature": "portefeuille_projets",
        "sectors": ["energie", "environnement", "innovation"],
        "beneficiaries": ["entreprise", "collectivite", "ong", "institution", "porteur projet"],
        "short_description": (
            "Le FONAME constitue un portefeuille national de projets innovants dans la maîtrise de l'énergie "
            "et les énergies renouvelables en Côte d'Ivoire."
        ),
        "full_description": (
            "L'appel permet aux porteurs de projets publics ou privés de faire analyser leur projet et de "
            "l'intégrer au portefeuille national EnR/EE. Ce portefeuille doit ensuite faciliter la mobilisation "
            "de financements auprès de l'État et des partenaires techniques et financiers. Ce n'est pas une "
            "subvention directe immédiate, mais une porte d'entrée stratégique pour les projets énergie."
        ),
        "eligibility_criteria": (
            "Personnes physiques ou morales, publiques ou privées, porteuses d'un projet contribuant à la "
            "transition énergétique en Côte d'Ivoire. Les projets de type IPP raccordés au réseau ne sont pas éligibles."
        ),
        "funding_details": (
            "Pas de financement direct garanti à ce stade. Les projets validés peuvent être intégrés au portefeuille "
            "utilisé pour mobiliser des financements futurs auprès de l'État et des partenaires techniques et financiers."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Appel à surveiller comme guichet stratégique énergie, sans date de clôture fiable publiée sur la page HTML.",
        "source_url": "https://www.dgenergie.ci/article-detail/53/284/avis-d-appel-a-projets-foname-2026",
        "source_name": "FONAME Côte d'Ivoire",
        "keywords": ["Côte d'Ivoire", "FONAME", "énergie", "efficacité énergétique", "EnR"],
    },
    {
        "title": "Investing for Employment 2026 - subventions de cofinancement en Côte d'Ivoire",
        "organism": "Invest for Jobs / KfW",
        "country": "Côte d'Ivoire",
        "region": "Côte d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "subvention_cofinancement",
        "sectors": ["industrie", "emploi", "formation", "transition_verte", "entrepreneuriat"],
        "beneficiaries": ["entreprise", "ong", "organisation", "institution"],
        "short_description": (
            "Investing for Employment finance des projets matures créateurs d'emplois en Côte d'Ivoire "
            "au moyen de subventions de cofinancement."
        ),
        "full_description": (
            "La facilité Investing for Employment, mise en oeuvre par KfW dans le cadre d'Invest for Jobs, "
            "ouvre un appel à propositions pour la Côte d'Ivoire. Les projets doivent lever un obstacle "
            "à l'investissement, créer de bons emplois dans le secteur privé et être suffisamment mûrs pour "
            "être mis en oeuvre rapidement. Les entreprises privées, organisations publiques et organisations "
            "à but non lucratif peuvent soumettre une note conceptuelle."
        ),
        "eligibility_criteria": (
            "Entités légalement constituées ou consortiums portant un projet d'investissement en Côte d'Ivoire. "
            "Le projet doit créer des emplois, améliorer les conditions de travail, soutenir la formation ou "
            "contribuer à une transition juste. L'apport propre du candidat et la viabilité du projet doivent "
            "être démontrés."
        ),
        "funding_details": (
            "Subventions de cofinancement pouvant atteindre 10 M EUR par projet pour la composante de création "
            "d'emplois. Le montant par emploi créé ne doit pas dépasser 10 000 EUR."
        ),
        "amount_max": Decimal("10000000"),
        "currency": "EUR",
        "open_date": date(2026, 4, 15),
        "close_date": date(2026, 6, 30),
        "status": "open",
        "source_url": "https://invest-for-jobs.com/en/investing-for-employment",
        "source_name": "Investing for Employment - Côte d'Ivoire 2026",
        "keywords": ["Côte d'Ivoire", "Invest for Jobs", "KfW", "emploi", "subvention", "cofinancement"],
    },
    {
        "title": "Digital Energy Challenge 2026 - PME énergie digitale en Afrique",
        "organism": "AFD / Digital Energy Facility",
        "country": "Afrique",
        "region": "Bénin, Côte d'Ivoire, Afrique",
        "zone": "Afrique",
        "geographic_scope": "continental",
        "device_type": "concours",
        "aid_nature": "challenge_finance",
        "sectors": ["energie", "numerique", "innovation", "climat"],
        "beneficiaries": ["startup", "pme", "entreprise", "operateur_energie"],
        "short_description": (
            "Le Digital Energy Challenge 2026 soutient des PME et startups africaines développant des solutions "
            "digitales pour l'accès à l'énergie, les mini-réseaux et la performance des opérateurs."
        ),
        "full_description": (
            "L'appel 2026 du Digital Energy Challenge, porté par l'AFD et ses partenaires, cible les solutions "
            "numériques appliquées à l'énergie : planification des réseaux, intégration des données de mini-réseaux, "
            "pilotage des actifs distribués et performance opérationnelle. Les projets sélectionnés bénéficient "
            "d'un soutien financier, d'un accompagnement technique, d'un bootcamp d'experts et d'une visibilité "
            "dans l'écosystème énergie digitale."
        ),
        "eligibility_criteria": (
            "PME, startups, fournisseurs technologiques ou opérateurs énergétiques portant un projet en Afrique. "
            "Les pays éligibles incluent notamment le Bénin et la Côte d'Ivoire. Les propositions doivent répondre "
            "aux thèmes 2026 du challenge et démontrer une solution digitale applicable au secteur de l'énergie."
        ),
        "funding_details": (
            "Soutien financier et accompagnement technique pour les projets lauréats. Le montant exact dépend de "
            "la catégorie et doit être confirmé dans le dossier officiel."
        ),
        "open_date": date(2026, 4, 20),
        "close_date": date(2026, 6, 17),
        "status": "open",
        "source_url": "https://digital-energy.eu/fr/digital-energy-challenge-appel-projets",
        "source_name": "Digital Energy Challenge 2026",
        "keywords": ["Bénin", "Côte d'Ivoire", "AFD", "énergie", "digital", "startup", "challenge"],
    },
    {
        "title": "ADPME Benin - accompagnement et acces au financement des PME",
        "organism": "Agence de Developpement des PME du Benin",
        "country": "Benin",
        "region": "Benin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "accompagnement_financement",
        "sectors": ["entrepreneuriat", "pme", "finance", "formation"],
        "beneficiaries": ["pme", "mpme", "entreprise", "porteur projet"],
        "short_description": (
            "L'ADPME Benin centralise des programmes d'accompagnement pour aider les MPME a structurer leur croissance "
            "et a acceder plus facilement aux financements."
        ),
        "full_description": (
            "La plateforme e-PME de l'ADPME Benin donne acces aux programmes nationaux d'appui aux MPME, dont le PAEB, "
            "finance par l'AFD, l'Union europeenne et Expertise France. Le dispositif vise a renforcer la gestion, la "
            "strategie, le developpement commercial et la capacite des entreprises a mobiliser des financements."
        ),
        "eligibility_criteria": (
            "PME ou MPME basees au Benin, avec un projet de croissance ou de structuration. Les criteres exacts dependent "
            "des cohortes ouvertes et doivent etre confirmes sur la plateforme e-PME."
        ),
        "funding_details": (
            "Accompagnement technique, diagnostic, appui a la structuration et facilitation de l'acces au financement. "
            "Les aides financieres directes dependent des appels ou cohortes publies par l'ADPME."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Guichet national permanent avec cohortes et programmes publies par periode.",
        "source_url": "https://epme.adpme.bj/",
        "source_name": "ADPME Benin - e-PME et PAEB",
        "keywords": ["Benin", "ADPME", "PAEB", "PME", "financement", "accompagnement"],
    },
    {
        "title": "FNDA Benin - financement des projets agricoles",
        "organism": "Fonds National de Developpement Agricole du Benin",
        "country": "Benin",
        "region": "Benin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "subvention_agricole",
        "sectors": ["agriculture", "agroalimentaire", "elevage", "innovation"],
        "beneficiaries": ["exploitant agricole", "pme", "organisation agricole", "collectivite"],
        "short_description": (
            "Le FNDA est le guichet national beninois de financement agricole, avec des appels a projets pour investissements "
            "agricoles, services non financiers et renforcement de capacites."
        ),
        "full_description": (
            "Le Fonds National de Developpement Agricole publie des appels a projets destines aux acteurs agricoles : "
            "exploitants, organisations professionnelles, PME agroalimentaires, collectivites et partenaires techniques. "
            "Les appuis peuvent prendre la forme de subventions partielles ou integrales selon les appels."
        ),
        "eligibility_criteria": (
            "Acteurs agricoles ou agroalimentaires au Benin. Les projets doivent generalement viser des filieres prioritaires "
            "et presenter un impact productif, commercial ou de renforcement de capacites."
        ),
        "funding_details": (
            "Subventions ou facilites de financement selon les appels publies. Le montant et la date limite doivent etre "
            "verifies pour chaque appel actif sur le portail officiel."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Guichet agricole recurrent. Publier les appels actifs uniquement lorsqu'une date fiable est disponible.",
        "source_url": "https://partenaires.fnda.bj/",
        "source_name": "FNDA Benin - financement agricole",
        "keywords": ["Benin", "FNDA", "agriculture", "subvention", "agroalimentaire"],
    },
    {
        "title": "AFP-PME Burkina Faso - financement et promotion des PME",
        "organism": "Agence de Financement et de Promotion des PME",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "pret_accompagnement",
        "sectors": ["entrepreneuriat", "pme", "industrie", "services"],
        "beneficiaries": ["pme", "pmi", "entreprise", "porteur projet"],
        "short_description": (
            "L'AFP-PME accompagne les PME burkinabe avec des solutions de financement, d'incubation, de prets d'honneur "
            "et de bonification."
        ),
        "full_description": (
            "L'Agence de Financement et de Promotion des PME est un fonds national de financement cree pour repondre aux "
            "difficultes d'acces aux fonds propres et aux garanties des PME/PMI du Burkina Faso. Elle propose plusieurs "
            "produits : credits d'exploitation, prets moyen et long terme, incubation, prets d'honneur, bonification et "
            "fonds d'amorcage."
        ),
        "eligibility_criteria": (
            "PME, PMI ou porteurs de projets de droit burkinabe installes au Burkina Faso. L'entreprise doit porter un "
            "projet de creation, d'extension ou de developpement economiquement viable."
        ),
        "funding_details": (
            "Prets, prets d'honneur, bonifications et accompagnement. Les montants, taux et conditions dependent du produit "
            "retenu et doivent etre confirmes directement aupres de l'AFP-PME."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Dispositif national permanent sans fenetre unique de cloture.",
        "source_url": "https://afppme.bf/",
        "source_name": "AFP-PME Burkina Faso",
        "keywords": ["Burkina Faso", "AFP-PME", "PME", "pret", "financement"],
    },
    {
        "title": "MEBF SEFAFI - facilitation du financement des entreprises au Burkina Faso",
        "organism": "Maison de l'Entreprise du Burkina Faso",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "appui_bancarisation",
        "sectors": ["entrepreneuriat", "pme", "finance", "formation"],
        "beneficiaries": ["createur entreprise", "pme", "association", "groupement professionnel"],
        "short_description": (
            "Le SEFAFI de la MEBF aide les entrepreneurs burkinabe a preparer des plans d'affaires bancables et a acceder "
            "plus efficacement aux financements."
        ),
        "full_description": (
            "La Maison de l'Entreprise du Burkina Faso propose un Service de Facilitation du Financement des Entreprises "
            "pour renforcer la qualite des dossiers de financement, ameliorer les relations avec les institutions financieres "
            "et accompagner les porteurs de projets apres obtention du financement."
        ),
        "eligibility_criteria": (
            "Createurs d'entreprises, PME en developpement, beneficiaires de projets geres par la MEBF, associations et "
            "groupements professionnels au Burkina Faso."
        ),
        "funding_details": (
            "Appui au montage de plan d'affaires, formation, suivi post-financement et facilitation bancaire. Ce n'est pas "
            "une subvention directe, mais un levier d'acces au financement."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Service permanent de facilitation du financement.",
        "source_url": "https://monbusinessplan.me.bf/",
        "source_name": "MEBF Burkina Faso - SEFAFI",
        "keywords": ["Burkina Faso", "MEBF", "SEFAFI", "plan d'affaires", "financement"],
    },
    {
        "title": "FONRID Burkina Faso - appels a projets recherche et innovation",
        "organism": "Fonds National de la Recherche et de l'Innovation pour le Developpement",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "appel à projets",
        "aid_nature": "subvention_recherche",
        "sectors": ["recherche", "innovation", "agriculture", "energie"],
        "beneficiaries": ["chercheur", "universite", "centre de recherche", "innovateur"],
        "short_description": (
            "Le FONRID finance des projets de recherche appliquee et d'innovation utiles au developpement du Burkina Faso."
        ),
        "full_description": (
            "Le Fonds National de la Recherche et de l'Innovation pour le Developpement lance periodiquement des appels "
            "a projets sur des thematiques prioritaires comme l'agriculture, l'energie, la transformation locale ou "
            "l'innovation technologique. Certains appels peuvent etre nationaux ou conjoints avec d'autres fonds africains."
        ),
        "eligibility_criteria": (
            "Equipes de recherche, enseignants-chercheurs, centres de recherche, institutions ou porteurs de projets "
            "d'innovation bases au Burkina Faso selon les termes de reference de chaque appel."
        ),
        "funding_details": (
            "Subventions de recherche et innovation selon l'appel publie. Les montants et dates limites doivent etre "
            "confirmes dans les termes de reference officiels."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Fonds national recurrent avec appels thematiques publies par periode.",
        "source_url": "https://fonrid.com/",
        "source_name": "FONRID Burkina Faso - recherche et innovation",
        "keywords": ["Burkina Faso", "FONRID", "recherche", "innovation", "subvention"],
    },
    {
        "title": "FONSTI Cote d'Ivoire - guichets recherche, innovation et entrepreneuriat",
        "organism": "Fonds pour la Science, la Technologie et l'Innovation",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "appel à projets",
        "aid_nature": "subvention_recherche",
        "sectors": ["recherche", "innovation", "entrepreneuriat", "technologie"],
        "beneficiaries": ["chercheur", "startup", "universite", "centre de recherche", "innovateur"],
        "short_description": (
            "Le FONSTI soutient la recherche, l'innovation technologique et l'entrepreneuriat scientifique en Cote d'Ivoire."
        ),
        "full_description": (
            "Le Fonds pour la Science, la Technologie et l'Innovation dispose de guichets de financement pour la recherche "
            "fondamentale, la recherche appliquee, les infrastructures, le developpement experimental, l'innovation et "
            "l'entrepreneuriat. Les appels doivent etre suivis source par source afin de publier uniquement les sessions actives."
        ),
        "eligibility_criteria": (
            "Chercheurs, institutions de recherche, universites, innovateurs et porteurs de projets bases en Cote d'Ivoire, "
            "selon le guichet ouvert et les termes de reference de l'appel."
        ),
        "funding_details": (
            "Financement de programmes et projets de recherche ou d'innovation. Montants et dates limites variables selon "
            "les appels publies par le FONSTI."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Guichets recurrents. Les appels actifs doivent etre verifies avant publication avec date.",
        "source_url": "https://fonsti.org/appel-a-projets/",
        "source_name": "FONSTI Cote d'Ivoire - appels a projets",
        "keywords": ["Cote d'Ivoire", "FONSTI", "innovation", "recherche", "subvention"],
    },
    {
        "title": "CCI-BF Parcours du createur - financement de 60 initiatives d'entreprises",
        "organism": "Chambre de Commerce et d'Industrie du Burkina Faso",
        "country": "Burkina Faso",
        "region": "Hauts-Bassins",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "regional",
        "device_type": "subvention",
        "aid_nature": "financement_tpe",
        "sectors": ["entrepreneuriat", "agriculture", "artisanat", "commerce", "services"],
        "beneficiaries": ["porteur projet", "tpe", "entreprise"],
        "short_description": (
            "La CCI-BF et la plateforme de prets d'honneur des Hauts-Bassins soutiennent 60 initiatives "
            "d'entreprises dans la region."
        ),
        "full_description": (
            "Le programme Parcours du createur d'entreprise est un mecanisme alternatif de financement au profit "
            "des tres petites entreprises des Hauts-Bassins. Il cible des porteurs de projets implantes dans la "
            "region, notamment dans la transformation, le commerce, les services, l'artisanat et l'agriculture."
        ),
        "eligibility_criteria": (
            "Porteurs de projets implantes dans la region des Hauts-Bassins au Burkina Faso. Les projets doivent "
            "etre economiquement viables, createurs d'emplois ou de richesses et appartenir aux domaines cibles "
            "par l'appel."
        ),
        "funding_details": (
            "Financement et accompagnement de 60 initiatives via un fonds local d'aide a l'entreprise. Les montants "
            "et modalites definitives doivent etre verifies dans le dossier officiel."
        ),
        "status": "open",
        "open_date": date(2026, 5, 10),
        "close_date": date(2026, 6, 30),
        "source_url": "https://www.cci.bf/?q=fr%2Fdownload%2Ffile%2Ffid%2F1125",
        "source_name": "CCI-BF - Parcours du createur d'entreprise",
        "keywords": ["Burkina Faso", "CCI-BF", "Hauts-Bassins", "TPE", "financement", "entrepreneuriat"],
    },
    {
        "title": "ZAD Bobo - souscription pour projets productifs a Bobo-Dioulasso",
        "organism": "Chambre de Commerce et d'Industrie du Burkina Faso",
        "country": "Burkina Faso",
        "region": "Bobo-Dioulasso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "local",
        "device_type": "accompagnement",
        "aid_nature": "implantation_economique",
        "sectors": ["industrie", "production", "commerce", "services", "agroalimentaire"],
        "beneficiaries": ["entreprise", "pme", "porteur projet", "investisseur"],
        "short_description": (
            "La ZAD Bobo permet aux porteurs de projets de souscrire a des parcelles pour implanter une activite "
            "economique a Bobo-Dioulasso."
        ),
        "full_description": (
            "La Chambre de Commerce et d'Industrie du Burkina Faso ouvre les souscriptions aux parcelles de la zone "
            "d'activites diverses de Bobo-Dioulasso. La selection repose sur la pertinence et la qualite des projets, "
            "ce qui en fait une opportunite utile pour les entreprises ayant un besoin d'implantation productive."
        ),
        "eligibility_criteria": (
            "Porteurs de projets ou entreprises souhaitant implanter une activite economique dans la ZAD de Bobo. "
            "Le dossier doit presenter les informations sur l'entreprise et le projet envisage."
        ),
        "funding_details": (
            "Il ne s'agit pas d'une subvention directe mais d'une opportunite d'implantation economique. Les frais, "
            "conditions d'attribution et obligations doivent etre confirmes sur la plateforme officielle."
        ),
        "status": "open",
        "open_date": date(2026, 4, 1),
        "close_date": date(2026, 5, 31),
        "source_url": "https://zadbobo.cci.bf/",
        "source_name": "CCI-BF - ZAD Bobo",
        "keywords": ["Burkina Faso", "Bobo-Dioulasso", "ZAD", "implantation", "industrie"],
    },
    {
        "title": "PMF-FEM Cote d'Ivoire - microfinancements environnement et communautes",
        "organism": "Commission Nationale du Fonds pour l'Environnement Mondial",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "microfinancement",
        "sectors": ["environnement", "climat", "biodiversite", "agriculture", "communautes"],
        "beneficiaries": ["ong", "association", "cooperative", "mutuelle", "entreprise sociale"],
        "short_description": (
            "Le Programme de Microfinancements du FEM finance des projets locaux environnementaux portes par des "
            "organisations ivoiriennes."
        ),
        "full_description": (
            "Le PMF-FEM en Cote d'Ivoire soutient des initiatives locales qui produisent des benefices environnementaux "
            "et contribuent a la reduction de la pauvrete. Les projets peuvent concerner la biodiversite, le climat, "
            "les paysages prioritaires, les communautes rurales et les solutions locales innovantes."
        ),
        "eligibility_criteria": (
            "ONG, associations, cooperatives, mutuelles de developpement, organisations communautaires de base ou "
            "entreprises sociales reconnues par l'Etat et etablies en Cote d'Ivoire."
        ),
        "funding_details": (
            "Subventions pouvant aller jusqu'a 50 000 USD selon les conditions du Programme de Microfinancements FEM. "
            "Les appels et enveloppes disponibles doivent etre confirmes sur la source officielle."
        ),
        "amount_max": Decimal("50000"),
        "currency": "USD",
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Guichet de microfinancements environnementaux recurrent, sans date unique de cloture.",
        "source_url": "https://cnfem.finances.gouv.ci/comment-soumettre-un-projet/",
        "source_name": "CNFEM Cote d'Ivoire - microfinancements FEM",
        "keywords": ["Cote d'Ivoire", "FEM", "PMF", "environnement", "subvention", "ONG"],
    },
    {
        "title": "WEDAF Benin - entrepreneuriat feminin et acces au financement",
        "organism": "Ministere des PME et de la Promotion de l'Emploi du Benin",
        "country": "Benin",
        "region": "Benin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "programme_financement",
        "sectors": ["entrepreneuriat", "finance", "femmes", "pme"],
        "beneficiaries": ["femme entrepreneure", "pme", "mpme", "institution financiere"],
        "short_description": (
            "WEDAF est un programme national visant a renforcer l'entrepreneuriat feminin et l'acces au financement "
            "au Benin."
        ),
        "full_description": (
            "Le Projet de Developpement de l'Entrepreneuriat Feminin et d'Acces au Financement est appuye par la Banque "
            "mondiale et vise a transformer durablement l'ecosysteme entrepreneurial feminin au Benin. Il combine reformes, "
            "appui aux institutions financieres, accompagnement des entrepreneures et dispositifs d'acces au financement."
        ),
        "eligibility_criteria": (
            "Femmes entrepreneures, MPME dirigees par des femmes, institutions et partenaires de l'ecosysteme financier "
            "au Benin. Les criteres operationnels seront precises lors des guichets ou appels ouverts."
        ),
        "funding_details": (
            "Programme d'environ 100 M USD sur six ans. Les financements directs aux beneficiaires dependent des "
            "instruments deployes et doivent etre confirmes dans les appels operationnels."
        ),
        "amount_max": Decimal("100000000"),
        "currency": "USD",
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme national pluriannuel. Les opportunites operationnelles doivent etre suivies au fil des guichets.",
        "source_url": "https://pmepe.gouv.bj/article/81/projet-developpement-entrepreneuriat-feminin-acces-financement-wedaf",
        "source_name": "WEDAF Benin - entrepreneuriat feminin et acces au financement",
        "keywords": ["Benin", "WEDAF", "femmes", "PME", "Banque mondiale", "financement"],
    },
    {
        "title": "Cote d'Ivoire PME - veille des appels a projets pour PME",
        "organism": "Agence Cote d'Ivoire PME",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "appel à projets",
        "aid_nature": "veille_opportunites",
        "sectors": ["pme", "entrepreneuriat", "innovation", "formation"],
        "beneficiaries": ["pme", "startup", "entreprise", "porteur projet"],
        "short_description": (
            "Cote d'Ivoire PME publie ou relaie des appels a projets et programmes utiles aux PME ivoiriennes."
        ),
        "full_description": (
            "La page des appels a projets de Cote d'Ivoire PME constitue une source de veille pour identifier les "
            "programmes d'appui, concours, formations et opportunites destines aux entrepreneurs et PME en Cote d'Ivoire. "
            "Chaque appel doit etre qualifie individuellement avant d'etre affiche comme opportunite ouverte."
        ),
        "eligibility_criteria": (
            "PME, startups, entrepreneurs et porteurs de projets bases en Cote d'Ivoire selon les criteres de chaque "
            "appel publie."
        ),
        "funding_details": (
            "Les montants et avantages dependent de chaque appel. Cette fiche sert de source de veille et ne doit pas "
            "etre interpretee comme un financement ouvert unique."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Source de veille nationale. Publier chaque appel separement quand les informations sont fiables.",
        "source_url": "https://cipme.ci/appel-projets/",
        "source_name": "Cote d'Ivoire PME - appels a projets",
        "keywords": ["Cote d'Ivoire", "PME", "appel a projets", "entrepreneuriat"],
    },
    {
        "title": "FAIJ Burkina Faso - financement de micro-projets jeunes",
        "organism": "Fonds d'Appui aux Initiatives des Jeunes",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "microcredit_jeunes",
        "sectors": ["entrepreneuriat", "emploi", "commerce", "services", "agriculture"],
        "beneficiaries": ["jeune", "porteur projet", "collectif jeunes"],
        "short_description": (
            "Le FAIJ finance des micro-projets portes par des jeunes burkinabe formes en entrepreneuriat."
        ),
        "full_description": (
            "Cette procedure officielle permet aux jeunes porteurs de projets de solliciter un financement pour une "
            "activite generatrice de revenus et creatrice d'emplois. Le fonds accompagne aussi les beneficiaires par "
            "des actions de formation, d'encadrement et de suivi jusqu'au remboursement."
        ),
        "eligibility_criteria": (
            "Jeunes burkinabe de 18 a 35 ans, scolarises ou non, ayant suivi une formation en entrepreneuriat et portant "
            "un projet generateur de revenus. Les organisations ou collectifs de jeunes peuvent aussi etre eligibles."
        ),
        "funding_details": (
            "Prets individuels de 200 000 a 2 000 000 FCFA et prets collectifs de 500 000 a 5 000 000 FCFA. Taux indicatifs : "
            "2% pour les personnes handicapees, 3,5% pour les filles et 4% pour les garcons."
        ),
        "amount_min": Decimal("200000"),
        "amount_max": Decimal("5000000"),
        "currency": "XOF",
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Procedure nationale permanente, sans fenetre de cloture unique.",
        "source_url": "https://servicepublic.gov.bf/fiches/emploi-financement-de-micro-projets",
        "source_name": "Service Public Burkina Faso - FAIJ micro-projets jeunes",
        "keywords": ["Burkina Faso", "FAIJ", "jeunes", "microcredit", "emploi"],
    },
    {
        "title": "FASI Burkina Faso - financement de microprojets du secteur informel",
        "organism": "Fonds d'Appui au Secteur Informel",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "microcredit",
        "sectors": ["secteur informel", "agriculture", "elevage", "artisanat", "commerce"],
        "beneficiaries": ["microentrepreneur", "non salarie", "association", "cooperative"],
        "short_description": (
            "Le FASI accorde des credits aux acteurs du secteur informel pour financer des microprojets rentables."
        ),
        "full_description": (
            "Le Fonds d'Appui au Secteur Informel finance des credits d'investissement, d'equipement et d'approvisionnement "
            "en facteurs de production ou matieres premieres. Il cible les activites agropastorales, artisanales, "
            "commerciales et de services."
        ),
        "eligibility_criteria": (
            "Personne de nationalite burkinabe, non salariee, agee de 18 a 60 ans, portant une activite viable et rentable. "
            "Les associations et cooperatives peuvent etre concernees sous caution solidaire."
        ),
        "funding_details": (
            "Credits plafonnes a 1 500 000 FCFA. Premier credit jusqu'a 500 000 FCFA, second credit jusqu'a 1 000 000 FCFA. "
            "Taux indicatifs : 10% agriculture/elevage, 13% commerce/services/artisanat, 4% pour certaines activites de personnes handicapees."
        ),
        "amount_max": Decimal("1500000"),
        "currency": "XOF",
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Procedure officielle permanente pour le secteur informel.",
        "source_url": "https://servicepublic.gov.bf/fiches/emploi-financement-de-microprojets",
        "source_name": "Service Public Burkina Faso - FASI secteur informel",
        "keywords": ["Burkina Faso", "FASI", "secteur informel", "microprojet", "credit"],
    },
    {
        "title": "FAARF Burkina Faso - credit aux femmes pour activites generatrices de revenus",
        "organism": "Fonds d'Appui aux Activites Remuneratrices des Femmes",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "credit_femmes",
        "sectors": ["entrepreneuriat feminin", "commerce", "artisanat", "agriculture", "services"],
        "beneficiaries": ["femme entrepreneure", "groupement femmes", "association femmes"],
        "short_description": (
            "Le FAARF facilite l'acces au credit pour les femmes burkinabe exercant une activite generatrice de revenus."
        ),
        "full_description": (
            "La procedure officielle prevoit l'octroi de credits aux femmes et la formation des beneficiaires du credit. "
            "Elle cible les femmes membres de groupements ou associations reconnus, ainsi que les groupes de solidarite."
        ),
        "eligibility_criteria": (
            "Femmes burkinabe exercant une activite generatrice de revenus, membres d'un groupement ou d'une association "
            "de femmes reconnu, ou d'un groupe de solidarite de 3 a 6 personnes."
        ),
        "funding_details": (
            "Credit avec frais de dossier de 1% du montant sollicite et cotisation obligatoire au fonds de garantie de 10% "
            "du montant octroye."
        ),
        "currency": "XOF",
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Procedure officielle permanente d'appui aux activites generatrices de revenus des femmes.",
        "source_url": "https://servicepublic.gov.bf/fiches/emploi-demande-de-financement-des-activites-generatrices-de-revenus",
        "source_name": "Service Public Burkina Faso - financement AGR femmes",
        "keywords": ["Burkina Faso", "FAARF", "femmes", "credit", "AGR"],
    },
    {
        "title": "Burkina Faso - financement des microprojets de jeunes diplomes",
        "organism": "Direction Generale de l'Insertion Professionnelle et de l'Emploi",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "financement_jeunes_diplomes",
        "sectors": ["innovation", "emploi", "entrepreneuriat", "formation"],
        "beneficiaries": ["jeune diplome", "jeune qualifie", "porteur projet"],
        "short_description": (
            "Ce dispositif finance des projets innovants, structurants et porteurs d'emplois portes par des jeunes diplomes."
        ),
        "full_description": (
            "La procedure vise les jeunes diplomes des universites, instituts et ecoles superieures, ainsi que les jeunes "
            "qualifies issus de centres de formation professionnelle. Le financement concerne des projets innovants et "
            "createurs d'emplois."
        ),
        "eligibility_criteria": (
            "Etre jeune, diplome de l'enseignement superieur ou qualifie d'un centre de formation professionnelle, et porter "
            "un projet innovant."
        ),
        "funding_details": (
            "Financement de microprojets innovants. Les montants et modalites doivent etre confirmes aupres de la Direction "
            "Generale de l'Insertion Professionnelle et de l'Emploi."
        ),
        "currency": "XOF",
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Procedure officielle permanente sans date de cloture unique.",
        "source_url": "https://www.servicepublic.gov.bf/fiches/emploi-financement-des-microprojets-des-jeunes-diplomes-du-superieur",
        "source_name": "Service Public Burkina Faso - microprojets jeunes diplomes",
        "keywords": ["Burkina Faso", "jeunes diplomes", "innovation", "emploi", "financement"],
    },
    {
        "title": "Micro Credit Alafia Benin - financement des activites generatrices de revenus",
        "organism": "Fonds National de la Microfinance du Benin",
        "country": "Benin",
        "region": "Benin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "microcredit",
        "sectors": ["microfinance", "commerce", "agriculture", "artisanat", "services"],
        "beneficiaries": ["personne vulnerable", "microentrepreneur", "femme", "jeune"],
        "short_description": (
            "Micro Credit Alafia facilite l'acces au financement pour les personnes vulnerables portant ou souhaitant lancer une activite."
        ),
        "full_description": (
            "Le programme Micro Credit Alafia vise l'inclusion financiere des personnes exclues du systeme financier classique. "
            "Il s'adresse aux personnes vulnerables ayant une activite generatrice de revenus ou souhaitant en exercer une, "
            "en s'appuyant sur des systemes financiers decentralises partenaires."
        ),
        "eligibility_criteria": (
            "Personnes vulnerables au Benin, exclues du systeme financier classique, ayant ou souhaitant lancer une activite "
            "generatrice de revenus."
        ),
        "funding_details": (
            "Microcredit distribue via des structures de finance decentralisee partenaires. Les montants et conditions varient "
            "selon le departement et le partenaire financier."
        ),
        "currency": "XOF",
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme national permanent de microcredit.",
        "source_url": "https://social.gouv.bj/micro-credit-alafia",
        "source_name": "Benin - Micro Credit Alafia",
        "keywords": ["Benin", "Micro Credit Alafia", "microfinance", "microcredit", "inclusion financiere"],
    },
    {
        "title": "ProPME Benin - croissance et competitivite des MPME",
        "organism": "Ministere des PME et de la Promotion de l'Emploi du Benin",
        "country": "Benin",
        "region": "Benin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "appui_pme",
        "sectors": ["pme", "emploi", "formation", "finance", "competitivite"],
        "beneficiaries": ["mpme", "pme", "jeune", "femme entrepreneure"],
        "short_description": (
            "ProPME renforce la competitivite des MPME beninoises et soutient la creation d'emplois de qualite."
        ),
        "full_description": (
            "Le programme ProPME soutient la croissance efficace et durable des micro, petites et moyennes entreprises au Benin. "
            "Il agit sur les capacites entrepreneuriales et techniques, l'acces aux marches, la qualite, la conformite et "
            "l'amelioration des conditions de travail."
        ),
        "eligibility_criteria": (
            "MPME beninoises, notamment entreprises portees par des jeunes ou des femmes, selon les boucles et programmes "
            "operationnels ouverts avec l'ADPME, la CCI Benin et les partenaires."
        ),
        "funding_details": (
            "Programme d'appui d'environ 9 M EUR. L'appui peut inclure accompagnement, renforcement de capacites et facilitation "
            "de l'acces au financement selon les guichets operationnels."
        ),
        "amount_max": Decimal("9000000"),
        "currency": "EUR",
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme national pluriannuel avec cohortes et actions publiees par periode.",
        "source_url": "https://pmepe.gouv.bj/article/86/projets-financement-s-a-etablissement-credit-specialise-dans-credits-pme",
        "source_name": "Benin - ProPME",
        "keywords": ["Benin", "ProPME", "MPME", "competitivite", "emploi"],
    },
    {
        "title": "ADERIZ Cote d'Ivoire - veille des appels et appuis filiere riz",
        "organism": "Agence pour le Developpement de la Filiere Riz",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "appel à projets",
        "aid_nature": "veille_filiere_agricole",
        "sectors": ["agriculture", "riz", "agroalimentaire", "transformation"],
        "beneficiaries": ["producteur agricole", "pme agricole", "cooperative", "agregateur"],
        "short_description": (
            "ADERIZ est une source a surveiller pour les appels et appuis lies a la filiere riz en Cote d'Ivoire."
        ),
        "full_description": (
            "L'Agence pour le Developpement de la Filiere Riz publie des informations sur les projets, appels a manifestation "
            "d'interet, programmes d'appui et initiatives de structuration de la filiere riz ivoirienne. La source est utile "
            "pour detecter les opportunites agricoles nationales."
        ),
        "eligibility_criteria": (
            "Acteurs de la filiere riz en Cote d'Ivoire : producteurs, cooperatives, agregateurs, PME de transformation ou "
            "structures d'appui, selon les appels publies."
        ),
        "funding_details": (
            "Les montants et avantages varient selon les appels et projets. Cette fiche sert de source de veille et doit etre "
            "qualifiee avant publication d'un appel specifique."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Source nationale a surveiller pour appels agricoles et manifestations d'interet.",
        "source_url": "https://www.aderiz.ci/",
        "source_name": "ADERIZ Cote d'Ivoire - appels et filiere riz",
        "keywords": ["Cote d'Ivoire", "ADERIZ", "riz", "agriculture", "appel a manifestation d'interet"],
    },
    {
        "title": "Orange Digital Center Burkina Faso - programme Damina",
        "organism": "Orange Digital Center Burkina Faso",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "incubation_startup",
        "sectors": ["numerique", "startup", "innovation", "entrepreneuriat"],
        "beneficiaries": ["startup", "porteur projet", "jeune entrepreneur"],
        "short_description": (
            "Le programme Damina accompagne les porteurs de projets et startups innovantes au Burkina Faso."
        ),
        "full_description": (
            "Orange Digital Center Burkina Faso lance des appels a candidatures pour le programme Damina, destine aux "
            "porteurs d'idees innovantes et aux jeunes startups. Le programme apporte un cadre d'accompagnement, de "
            "formation et de structuration pour transformer une idee numerique en projet entrepreneurial plus solide."
        ),
        "eligibility_criteria": (
            "Porteurs d'idees innovantes, jeunes entrepreneurs ou startups bases au Burkina Faso. Les criteres exacts "
            "dependent de chaque cohorte publiee par Orange Digital Center."
        ),
        "funding_details": (
            "Accompagnement, formation, mentorat et acces a l'ecosysteme Orange Digital Center. Les appuis financiers "
            "eventuels doivent etre confirmes pour chaque cohorte."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme par cohortes. L'appel 2026 identifie doit etre verifie avant publication comme ouvert.",
        "source_url": "https://digitalmagazine.bf/2026/03/28/orange-digital-center-odc-lance-un-appel-a-candidature-pour-le-programme-damina-2026/",
        "source_name": "Orange Digital Center Burkina Faso - Damina",
        "keywords": ["Burkina Faso", "Orange Digital Center", "Damina", "startup", "numerique"],
    },
    {
        "title": "MTN Innovation Lab Benin - incubation startups",
        "organism": "MTN Benin",
        "country": "Benin",
        "region": "Benin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "incubation_startup",
        "sectors": ["numerique", "startup", "innovation", "telecom", "entrepreneuriat"],
        "beneficiaries": ["startup", "porteur projet", "pme innovante"],
        "short_description": (
            "MTN Innovation Lab accompagne les startups beninoises avec mentorat, ressources, partenariats et acces a l'ecosysteme."
        ),
        "full_description": (
            "MTN Innovation Lab est un incubateur de startups au Benin. Il propose un programme d'accompagnement avec "
            "mentoring, acces a la plateforme, mise en relation, partenariats strategiques et soutien au developpement "
            "des projets innovants."
        ),
        "eligibility_criteria": (
            "Startups, PME innovantes ou porteurs de projets bases au Benin, notamment dans le numerique, les services, "
            "les technologies mobiles et l'innovation."
        ),
        "funding_details": (
            "Accompagnement, mentorat, acces a l'ecosysteme MTN et opportunites de partenariats. Les conditions de financement "
            "eventuel varient selon les promotions."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme d'incubation recurrent avec sessions publiees par periode.",
        "source_url": "https://innovation.mtn.bj/",
        "source_name": "MTN Innovation Lab Benin",
        "keywords": ["Benin", "MTN Innovation Lab", "startup", "incubation", "numerique"],
    },
    {
        "title": "Hub Ivoire Tech - accompagnement startups en Cote d'Ivoire",
        "organism": "Hub Ivoire Tech",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "incubation_acceleration",
        "sectors": ["startup", "innovation", "numerique", "technologie"],
        "beneficiaries": ["startup", "porteur projet", "incubateur", "accelerateur"],
        "short_description": (
            "Hub Ivoire Tech rassemble incubateurs, accelerateurs, mentors et investisseurs pour accompagner les startups ivoiriennes."
        ),
        "full_description": (
            "Hub Ivoire Tech est un campus ivoirien dedie aux startups. Il vise a connecter porteurs d'idees, startups, "
            "incubateurs, accelerateurs, experts, mentors et investisseurs afin de transformer les projets innovants en "
            "opportunites entrepreneuriales concretes."
        ),
        "eligibility_criteria": (
            "Startups, porteurs d'idees et acteurs de l'ecosysteme d'innovation en Cote d'Ivoire. Les criteres dependent "
            "des cohortes et appels publies."
        ),
        "funding_details": (
            "Accompagnement, acces a l'ecosysteme, mentorat et mise en relation avec investisseurs. Les financements directs "
            "dependent des programmes ou cohortes actifs."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Campus et programme par cohortes. La cohorte 1 etait cloturee le 18/01/2026, surveiller les prochaines sessions.",
        "source_url": "https://hubivoire.tech/",
        "source_name": "Hub Ivoire Tech",
        "keywords": ["Cote d'Ivoire", "Hub Ivoire Tech", "startup", "incubateur", "investisseurs"],
    },
    {
        "title": "BeoogoLAB Burkina Faso - startup studio et accompagnement tech",
        "organism": "BeoogoLAB",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "startup_studio",
        "sectors": ["startup", "numerique", "innovation", "entrepreneuriat"],
        "beneficiaries": ["startup", "porteur projet", "entrepreneur tech"],
        "short_description": (
            "BeoogoLAB est un startup studio burkinabe a surveiller pour l'accompagnement de projets tech et innovants."
        ),
        "full_description": (
            "BeoogoLAB accompagne l'ecosysteme startup au Burkina Faso avec des ressources d'incubation, de structuration "
            "et de developpement de projets numeriques. La source est utile pour detecter des appels, programmes ou "
            "opportunites d'accompagnement locales."
        ),
        "eligibility_criteria": (
            "Startups, porteurs de projets et entrepreneurs tech bases au Burkina Faso, selon les programmes ouverts."
        ),
        "funding_details": (
            "Accompagnement entrepreneurial et technique. Les financements directs ne sont pas systematiques et doivent "
            "etre confirmes par programme."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Source locale d'incubation a surveiller pour les appels et programmes actifs.",
        "source_url": "https://www.beoogolab.org/",
        "source_name": "BeoogoLAB Burkina Faso",
        "keywords": ["Burkina Faso", "BeoogoLAB", "startup", "innovation", "tech"],
    },
    {
        "title": "PMF-FEM Burkina Faso - microfinancements environnement",
        "organism": "PNUD / Programme de Microfinancements FEM",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "microfinancement_environnement",
        "sectors": ["environnement", "climat", "biodiversite", "communautes", "agriculture"],
        "beneficiaries": ["ong", "organisation communautaire", "association"],
        "short_description": (
            "Le PMF-FEM Burkina Faso finance des microprojets environnementaux portes par des ONG et organisations communautaires."
        ),
        "full_description": (
            "Le Programme de Microfinancements du Fonds pour l'Environnement Mondial accompagne des organisations engagees "
            "sur les questions environnementales au Burkina Faso. Les appels visent des projets locaux contribuant a la "
            "protection de l'environnement, a la resilience communautaire et au developpement durable."
        ),
        "eligibility_criteria": (
            "ONG nationales et organisations communautaires a la base engagees sur les questions environnementales au Burkina Faso."
        ),
        "funding_details": (
            "Microfinancements environnementaux selon les appels PMF/FEM. Le dernier appel identifie etait cloture en 2025 ; "
            "surveiller les prochains cycles avant publication comme opportunite ouverte."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Guichet recurrent de microfinancements environnementaux. Ne pas afficher comme appel ouvert sans nouvelle date.",
        "source_url": "https://www.undp.org/fr/burkina-faso/actualites/appel-projets-microfinancements-dans-le-secteur-de-lenvironnement",
        "source_name": "PNUD Burkina Faso - PMF FEM environnement",
        "keywords": ["Burkina Faso", "PNUD", "PMF", "FEM", "environnement", "subvention"],
    },
    {
        "title": "OIF - soutien a la mobilite des artistes et circulation des biens culturels",
        "organism": "Organisation internationale de la Francophonie",
        "country": "International",
        "region": "Benin, Burkina Faso, Cote d'Ivoire, Francophonie",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "international",
        "device_type": "subvention",
        "aid_nature": "aide_culture",
        "sectors": ["culture", "arts", "mobilite", "creative"],
        "beneficiaries": ["artiste", "structure culturelle", "organisation", "association"],
        "short_description": (
            "L'OIF soutient la mobilite des artistes et la circulation des biens culturels dans l'espace francophone."
        ),
        "full_description": (
            "Le portail des appels de l'OIF publie des opportunites de soutien financier pour des projets culturels, "
            "artistiques et de mobilite. L'appel identifie concerne la mobilite des artistes et la circulation des biens "
            "culturels, avec une date limite au 31 aout 2026."
        ),
        "eligibility_criteria": (
            "Personnes morales ou acteurs culturels eligibles dans les pays membres de la Francophonie, selon les criteres "
            "precis de l'appel. Les pays cibles de Kafundo comme le Benin, le Burkina Faso et la Cote d'Ivoire font partie "
            "de l'espace francophone."
        ),
        "funding_details": (
            "Aide financiere OIF selon les modalites de l'appel. Le montant doit etre confirme dans le dossier officiel."
        ),
        "status": "open",
        "open_date": date(2026, 5, 1),
        "close_date": date(2026, 8, 31),
        "source_url": "https://www.francophonie.org/appels-projets-candidatures-initiatives-1111",
        "source_name": "OIF - appels a projets francophonie",
        "keywords": ["OIF", "Francophonie", "culture", "Benin", "Burkina Faso", "Cote d'Ivoire"],
    },
    {
        "title": "ASNOM/FSSN - appel a projets sante locale 2027",
        "organism": "ASNOM / Fonds de Solidarite Sante Navale",
        "country": "International",
        "region": "Afrique",
        "zone": "Afrique",
        "geographic_scope": "international",
        "device_type": "appel à projets",
        "aid_nature": "subvention_sante",
        "sectors": ["sante", "solidarite", "association", "innovation sociale"],
        "beneficiaries": ["association", "ong", "structure sante", "acteur local"],
        "short_description": (
            "Le FSSN soutient des actions de sante locales, innovantes et suivies, avec une pre-selection jusqu'au 30 mai 2026."
        ),
        "full_description": (
            "Le Fonds de Solidarite Sante Navale soutient des actions pertinentes avec les besoins exprimes par les populations "
            "et les acteurs locaux de sante. Les projets doivent etre coherents avec les politiques sanitaires nationales ou locales, "
            "pouvoir etre suivis et favoriser une transition vers l'autonomie apres l'aide exterieure."
        ),
        "eligibility_criteria": (
            "Associations, ONG ou acteurs de sante capables de porter une action locale de sante, innovante, evaluable et "
            "coherente avec les besoins du terrain."
        ),
        "funding_details": (
            "Subvention sante selon la selection du FSSN. Pre-selection au 30 mai 2026, dossier complet au 20 septembre 2026."
        ),
        "status": "open",
        "open_date": date(2026, 4, 1),
        "close_date": date(2026, 5, 30),
        "source_url": "https://www.asnom.org/",
        "source_name": "ASNOM - Fonds de Solidarite Sante Navale",
        "keywords": ["sante", "Afrique", "association", "ONG", "subvention"],
    },
    {
        "title": "CORAF - veille innovations agricoles et Prix Abdoulaye Toure",
        "organism": "CORAF",
        "country": "Afrique de l'Ouest",
        "region": "Benin, Burkina Faso, Cote d'Ivoire, Afrique de l'Ouest",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "regional",
        "device_type": "concours",
        "aid_nature": "prix_innovation_agricole",
        "sectors": ["agriculture", "innovation", "elevage", "aquaculture", "climat"],
        "beneficiaries": ["chercheur", "innovateur", "entrepreneur agricole", "institution"],
        "short_description": (
            "Le CORAF publie des appels regionaux pour valoriser les innovations agricoles en Afrique de l'Ouest et du Centre."
        ),
        "full_description": (
            "Le CORAF anime des dispositifs comme le MITA et le Prix de l'Innovation Agricole Abdoulaye Toure. Ces appels "
            "permettent aux chercheurs, innovateurs, entrepreneurs et institutions de valoriser des technologies agricoles "
            "a fort impact pour la productivite, la resilience climatique et l'acces aux marches."
        ),
        "eligibility_criteria": (
            "Chercheurs, innovateurs, entrepreneurs, organisations ou institutions ayant developpe une innovation agricole "
            "pertinente pour l'Afrique de l'Ouest ou du Centre."
        ),
        "funding_details": (
            "Prix et subventions selon les editions. L'edition 2026 du Prix Abdoulaye Toure prevoyait 30 000 USD pour les "
            "trois premiers innovateurs, mais la date limite est passee ; surveiller les prochaines editions."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Source regionale recurrente. Ne publier comme open que lorsqu'un nouvel appel avec date future est confirme.",
        "source_url": "https://www.coraf.org/passation-marche",
        "source_name": "CORAF - innovations agricoles Afrique de l'Ouest",
        "keywords": ["CORAF", "MITA", "Prix Abdoulaye Toure", "agriculture", "innovation"],
    },
    {
        "title": "BOAD Development Days - projets agriculture et energie en Afrique de l'Ouest",
        "organism": "Banque Ouest Africaine de Developpement",
        "country": "Afrique de l'Ouest",
        "region": "UEMOA",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "regional",
        "device_type": "appel à projets",
        "aid_nature": "accompagnement_financement",
        "sectors": ["agriculture", "energie", "climat", "transition verte"],
        "beneficiaries": ["entreprise", "pme", "ong", "porteur projet"],
        "short_description": (
            "Les BOAD Development Days peuvent ouvrir des appels a projets pour des initiatives agriculture, energie et climat dans l'UEMOA."
        ),
        "full_description": (
            "La BOAD utilise les Development Days comme plateforme de selection et de valorisation de projets prives ouest-africains "
            "dans des secteurs strategiques comme l'agriculture durable et l'energie propre. Les projets selectionnes peuvent acceder "
            "a de l'accompagnement technique, des partenariats et des pistes de financement."
        ),
        "eligibility_criteria": (
            "Porteurs de projets, entreprises, ONG ou partenariats publics-prives bases dans l'espace UEMOA et proposant un projet "
            "viable a impact agricole, energetique ou climatique."
        ),
        "funding_details": (
            "Financement, accompagnement technique ou mise en relation selon les appels publies. Le dernier appel identifie etait clos ; "
            "surveiller les prochaines editions."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Source regionale recurrente, a transformer en appel open uniquement lorsqu'une nouvelle date est disponible.",
        "source_url": "https://www.boaddevelopmentdays.com/",
        "source_name": "BOAD Development Days - appels a projets",
        "keywords": ["BOAD", "UEMOA", "agriculture", "energie", "climat"],
    },
    {
        "title": "LuxAid Challenge Fund Benin - cofinancement d'entreprises innovantes",
        "organism": "LuxDev / LuxAid Business4Impact",
        "country": "Benin",
        "region": "Benin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "cofinancement",
        "sectors": ["agritech", "edtech", "fintech", "healthtech", "tourisme", "numerique"],
        "beneficiaries": ["entreprise", "pme", "startup", "cooperative"],
        "short_description": (
            "Le LuxAid Challenge Fund soutient des entreprises beninoises innovantes avec un cofinancement significatif."
        ),
        "full_description": (
            "Le LuxAid Challenge Fund Benin cible les entreprises formelles proposant des solutions innovantes, viables "
            "commercialement et capables de produire un impact social ou economique mesurable. Les secteurs cites incluent "
            "notamment AgTech, EdTech, HealthTech, FinTech, tourisme et solutions numeriques."
        ),
        "eligibility_criteria": (
            "Entreprises commerciales ou cooperatives legalement enregistrees au Benin, capables de porter un projet innovant "
            "et de mobiliser une part de cofinancement. Les criteres exacts doivent etre confirmes a chaque appel."
        ),
        "funding_details": (
            "Cofinancement pouvant atteindre environ 140 000 EUR selon l'appel. Le dernier appel identifie est clos ; surveiller "
            "les nouvelles editions via le portail LuxAid Business4Impact."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Source a surveiller pour les prochaines editions Benin du LuxAid Challenge Fund.",
        "source_url": "https://www.luxaidbusiness4impact.lu/fr/opportunites/",
        "source_name": "LuxAid Challenge Fund Benin",
        "keywords": ["Benin", "LuxAid", "LCF", "cofinancement", "startup", "PME"],
    },
    {
        "title": "FNDA Benin - appels pour investissements agricoles et services non financiers",
        "organism": "Fonds National de Developpement Agricole du Benin",
        "country": "Benin",
        "region": "Benin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "subvention_agricole",
        "sectors": ["agriculture", "agroalimentaire", "innovation agricole", "services agricoles"],
        "beneficiaries": ["exploitant agricole", "opa", "pme", "mairie", "association intercommunale"],
        "short_description": (
            "Le FNDA publie des appels pour financer des investissements agricoles et des services non financiers au Benin."
        ),
        "full_description": (
            "Les appels FNDA visent les filieres agricoles prioritaires au Benin. Ils peuvent financer des investissements "
            "agricoles, la recherche agricole appliquee, la vulgarisation, le renforcement de capacites, la certification ou "
            "la mise en marche."
        ),
        "eligibility_criteria": (
            "Mairies, associations intercommunales, exploitants agricoles, organisations professionnelles agricoles, faitieres "
            "d'OPA et MPME regulierement enregistrees ayant un lien prouve avec le secteur agricole."
        ),
        "funding_details": (
            "Subventions integrales ou partielles selon l'appel. Les dates changent par edition ; verifier le portail officiel "
            "avant toute candidature."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Guichet agricole recurrent. Publier comme open uniquement lorsqu'une nouvelle date est confirmee.",
        "source_url": "https://www.gouv.bj/article/3241/",
        "source_name": "Gouvernement Benin - appels FNDA agriculture",
        "keywords": ["Benin", "FNDA", "agriculture", "subvention", "MPME"],
    },
    {
        "title": "PIICC Benin - incubation des industries culturelles et creatives",
        "organism": "ADAC / Gouvernement du Benin",
        "country": "Benin",
        "region": "Benin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "incubation",
        "sectors": ["culture", "industries creatives", "arts", "entrepreneuriat"],
        "beneficiaries": ["entrepreneur culturel", "porteur projet", "startup creative"],
        "short_description": (
            "Le PIICC accompagne les entrepreneurs culturels et creatifs au Benin dans la structuration de leurs projets."
        ),
        "full_description": (
            "Le programme d'incubation PIICC vise a renforcer l'ecosysteme des industries culturelles et creatives au Benin. "
            "Il aide les entrepreneurs a structurer leur activite, ameliorer leur modele economique et preparer leur croissance."
        ),
        "eligibility_criteria": (
            "Entrepreneurs culturels et creatifs en activite ou porteurs d'un projet structure au Benin. Les conditions exactes "
            "dependent de chaque appel a candidatures."
        ),
        "funding_details": (
            "Accompagnement, formation, incubation et mise en relation. Le dispositif n'indique pas toujours une subvention directe."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme d'incubation a surveiller pour les nouvelles cohortes.",
        "source_url": "https://www.gouv.bj/article/3244/appel-candidatures-programme-incubation-secteur-industries-culturelles-creatives-benin/",
        "source_name": "Gouvernement Benin - PIICC incubation ICC",
        "keywords": ["Benin", "PIICC", "culture", "incubation", "ICC"],
    },
    {
        "title": "Mastercard Foundation EdTech Fellowship - Benin",
        "organism": "Mastercard Foundation / CPCCAF",
        "country": "Benin",
        "region": "Benin, Senegal",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "regional",
        "device_type": "concours",
        "aid_nature": "acceleration_financement",
        "sectors": ["education", "edtech", "numerique", "startup"],
        "beneficiaries": ["startup", "entrepreneur", "pme innovante"],
        "short_description": (
            "Le fellowship accompagne les startups EdTech du Benin avec acceleration, expertise et financement."
        ),
        "full_description": (
            "Le Mastercard Foundation EdTech Fellowship cible des startups qui transforment l'education par des solutions "
            "innovantes. La cohorte identifiee concernait le Benin et le Senegal avec un accompagnement strategique et un "
            "financement significatif."
        ),
        "eligibility_criteria": (
            "Startups EdTech basees au Benin ou operant sur le marche beninois, avec une solution educative innovante et un "
            "potentiel d'impact."
        ),
        "funding_details": (
            "Acceleration, accompagnement d'experts et financement selon les modalites de chaque cohorte. La cohorte 2026 "
            "identifiee est cloturee ; surveiller la prochaine edition."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme de cohorte recurrent. Ne pas afficher comme appel ouvert sans nouvelle date.",
        "source_url": "https://cpccaf.org/programme-et-appel-a-projet/appel-a-candidatures-mastercard-foundation-edtech-fellowship-cohorte-3-benin-senegal/",
        "source_name": "Mastercard Foundation EdTech Fellowship Benin",
        "keywords": ["Benin", "Mastercard Foundation", "EdTech", "startup", "education"],
    },
    {
        "title": "FDCT Burkina Faso - financement culture et tourisme",
        "organism": "Fonds de Developpement Culturel et Touristique",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "subvention_pret",
        "sectors": ["culture", "tourisme", "arts", "audiovisuel", "patrimoine"],
        "beneficiaries": ["entreprise culturelle", "association", "cooperative", "collectivite"],
        "short_description": (
            "Le FDCT est le guichet national burkinabe pour financer les projets culturels et touristiques."
        ),
        "full_description": (
            "Le Fonds de Developpement Culturel et Touristique accompagne les acteurs culturels et touristiques du Burkina Faso. "
            "Ses outils peuvent inclure subventions, prets a taux preferentiel, garanties, portage de projets et renforcement "
            "des capacites."
        ),
        "eligibility_criteria": (
            "Entreprises culturelles, associations, cooperatives, collectivites territoriales et agences culturelles legalement "
            "constituees au Burkina Faso."
        ),
        "funding_details": (
            "Financement selon les appels FDCT : subventions, prets, garanties ou accompagnement. Les dates doivent etre confirmees "
            "sur le site officiel."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Fonds national recurrent pour les appels culture/tourisme.",
        "source_url": "https://www.fdct-bf.org/",
        "source_name": "FDCT Burkina Faso - culture et tourisme",
        "keywords": ["Burkina Faso", "FDCT", "culture", "tourisme", "subvention"],
    },
    {
        "title": "ECOTEC Burkina Faso - fonds de partenariat pour MPME",
        "organism": "Projet ECOTEC / Maison de l'Entreprise du Burkina Faso",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "fonds_partenariat",
        "sectors": ["pme", "technologie", "competences", "energie verte", "innovation"],
        "beneficiaries": ["mpme", "entrepreneur", "entreprise"],
        "short_description": (
            "ECOTEC appuie les MPME burkinabe pour le financement, l'adoption technologique et le renforcement des competences."
        ),
        "full_description": (
            "Le projet ECOTEC soutient l'entrepreneuriat, le developpement des competences et l'adoption technologique au Burkina Faso. "
            "Le fonds de partenariat vise notamment les MPME qui adoptent de nouvelles technologies, y compris des technologies vertes."
        ),
        "eligibility_criteria": (
            "MPME ou entrepreneurs bases au Burkina Faso, avec un projet de croissance, d'adoption technologique ou de transformation "
            "productive. Les criteres precis dependent de chaque appel."
        ),
        "funding_details": (
            "Financement par appel a projets selon les enveloppes ECOTEC. Les appels doivent etre verifies sur la plateforme officielle."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme a surveiller pour les prochains appels de financement MPME.",
        "source_url": "https://ecotec.me.bf/",
        "source_name": "ECOTEC Burkina Faso - fonds de partenariat MPME",
        "keywords": ["Burkina Faso", "ECOTEC", "MPME", "technologie", "financement"],
    },
    {
        "title": "PEEB Awards Burkina Faso - valorisation des entrepreneurs et industriels",
        "organism": "PEEB Awards",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "concours",
        "aid_nature": "visibilite_accompagnement",
        "sectors": ["entrepreneuriat", "industrie", "innovation", "pme"],
        "beneficiaries": ["entrepreneur", "pme", "industriel", "startup"],
        "short_description": (
            "Les PEEB Awards mettent en avant les entrepreneurs et projets industriels burkinabe a fort potentiel."
        ),
        "full_description": (
            "Les PEEB Awards constituent une plateforme de valorisation des initiatives entrepreneuriales et industrielles au Burkina Faso. "
            "L'evenement combine conferences, masterclass, rencontres B2B et visibilite pour les porteurs de projets."
        ),
        "eligibility_criteria": (
            "Entrepreneurs, PME, startups ou acteurs industriels burkinabe selon les categories de chaque edition."
        ),
        "funding_details": (
            "Visibilite, mise en relation et opportunites business. La presence d'un prix financier doit etre confirmee selon l'edition."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Concours recurrent a qualifier lors de chaque nouvelle edition.",
        "source_url": "https://burkina24.com/2026/05/08/peeb-awards-2026-ouagadougou-veut-accelerer-lindustrialisation-et-reveler-les-champions-de-lentrepreneuriat-burkinabe/",
        "source_name": "PEEB Awards Burkina Faso",
        "keywords": ["Burkina Faso", "PEEB Awards", "entrepreneuriat", "industrie", "concours"],
    },
    {
        "title": "FIN CULTURE Cote d'Ivoire - prets pour industries culturelles et creatives",
        "organism": "Ministere de la Culture et de la Francophonie / AEJ",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "pret_culture",
        "sectors": ["culture", "industries creatives", "arts", "audiovisuel"],
        "beneficiaries": ["jeune entrepreneur", "acteur culturel", "pme creative"],
        "short_description": (
            "FIN CULTURE finance les projets culturels et creatifs ivoiriens sous forme de prets."
        ),
        "full_description": (
            "Le guichet FIN CULTURE cible les acteurs des industries culturelles et creatives en Cote d'Ivoire. Dans le cadre "
            "du MASA 2026, le dispositif a ete presente comme une opportunite de prets pour aider les jeunes ivoiriens a "
            "concretiser leurs projets culturels."
        ),
        "eligibility_criteria": (
            "Acteurs ICC, jeunes entrepreneurs et structures creatives en Cote d'Ivoire. Les criteres d'age, de statut et de "
            "dossier doivent etre confirmes sur la plateforme AEJ."
        ),
        "funding_details": (
            "Prets de 1 a 20 millions FCFA selon le guichet. Date limite non publiee clairement sur la page ; verifier avant candidature."
        ),
        "amount_min": Decimal("1524"),
        "amount_max": Decimal("30490"),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Guichet culture a verifier pour la session active avant affichage comme appel ouvert.",
        "source_url": "https://culture.gouv.ci/projets/appel-a-projet-le-guichet-fin-culture-est-officiellement-ouvert/",
        "source_name": "FIN CULTURE Cote d'Ivoire",
        "keywords": ["Cote d'Ivoire", "FIN CULTURE", "ICC", "culture", "pret"],
    },
    {
        "title": "Moov Innovation Cote d'Ivoire - concours startup digitale",
        "organism": "Moov Africa Cote d'Ivoire",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "concours",
        "aid_nature": "prix_accompagnement",
        "sectors": ["numerique", "startup", "innovation", "impact social"],
        "beneficiaries": ["startup", "jeune entrepreneur", "porteur projet"],
        "short_description": (
            "Moov Innovation soutient les startups ivoiriennes proposant des solutions digitales a impact."
        ),
        "full_description": (
            "Moov Innovation est un programme d'entrepreneuriat et d'innovation qui encourage les jeunes porteurs de projets "
            "et startups developpant des solutions digitales a impact social ou economique en Cote d'Ivoire."
        ),
        "eligibility_criteria": (
            "Startups ou porteurs de projets en Cote d'Ivoire, avec une solution digitale innovante et un potentiel d'impact."
        ),
        "funding_details": (
            "Prix, accompagnement, bootcamp et visibilite selon les editions. Verifier l'ouverture de l'edition en cours."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Concours recurrent a surveiller pour les nouvelles editions.",
        "source_url": "https://www.moov-africa.ci/moov-innovation/",
        "source_name": "Moov Innovation Cote d'Ivoire",
        "keywords": ["Cote d'Ivoire", "Moov Innovation", "startup", "digital", "concours"],
    },
    {
        "title": "Yello Startup Cote d'Ivoire - programme entrepreneurial MTN",
        "organism": "MTN Cote d'Ivoire",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "incubation",
        "sectors": ["numerique", "startup", "innovation", "services digitaux"],
        "beneficiaries": ["startup", "entrepreneur", "pme innovante"],
        "short_description": (
            "Y'ello Startup aide les startups ivoiriennes a deployer des solutions digitales avec l'ecosysteme MTN."
        ),
        "full_description": (
            "Y'ello Startup est un programme entrepreneurial de MTN Cote d'Ivoire destine aux startups et entrepreneurs "
            "qui developpent des solutions digitales innovantes exploitables sur les plateformes ou reseaux de l'operateur."
        ),
        "eligibility_criteria": (
            "Startups, entrepreneurs ou PME innovantes en Cote d'Ivoire avec une solution digitale a impact social ou economique."
        ),
        "funding_details": (
            "Accompagnement, acces technique, partenariats et opportunites de deploiement. Les avantages financiers doivent etre confirmes."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme startup a surveiller pour les cohortes et appels actifs.",
        "source_url": "https://yellostartup.mtn.ci/",
        "source_name": "Yello Startup Cote d'Ivoire",
        "keywords": ["Cote d'Ivoire", "Yello Startup", "MTN", "startup", "digital"],
    },
    {
        "title": "FIRCA NSIA Banque CI - financement PME agro-transformation",
        "organism": "FIRCA / NSIA Banque Cote d'Ivoire",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "pret",
        "aid_nature": "financement_agrotransformation",
        "sectors": ["agriculture", "agrotransformation", "pme", "chaine de valeur"],
        "beneficiaries": ["pme", "entreprise agroalimentaire", "cooperative"],
        "short_description": (
            "Le programme FIRCA-NSIA finance les PME ivoiriennes actives dans l'agro-transformation."
        ),
        "full_description": (
            "Le programme FIRCA-NSIA Banque Cote d'Ivoire cible les PME d'agro-transformation et vise a faciliter leur acces "
            "au financement pour renforcer les chaines de valeur agricoles locales."
        ),
        "eligibility_criteria": (
            "PME evoluant dans l'agro-transformation en Cote d'Ivoire, selon les criteres techniques et financiers de l'appel."
        ),
        "funding_details": (
            "Financement bancaire ou fonds dedie selon les modalites de l'appel. Le premier appel identifie est cloture ; surveiller "
            "les prochaines vagues."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme sectoriel a surveiller pour les prochains appels FIRCA-NSIA.",
        "source_url": "https://www.aip.ci/322325/cote-divoire-aip-programme-firca-nsia-banque-ci-les-criteres-et-modalites-du-premier-appel-a-projets-devoiles-fiche-technique/",
        "source_name": "FIRCA NSIA Banque CI - agrotransformation",
        "keywords": ["Cote d'Ivoire", "FIRCA", "NSIA", "agrotransformation", "PME"],
    },
    {
        "title": "CECI MTWW - expansion commerciale des entreprises feminines",
        "organism": "CECI / TradeMark Africa / Affaires mondiales Canada",
        "country": "Afrique de l'Ouest",
        "region": "Benin, Burkina Faso, Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "regional",
        "device_type": "accompagnement",
        "aid_nature": "accompagnement_export",
        "sectors": ["entrepreneuriat feminin", "commerce", "export", "agroalimentaire", "services"],
        "beneficiaries": ["entreprise feminine", "pme", "cooperative", "groupement"],
        "short_description": (
            "MTWW accompagne les entreprises feminines d'Afrique de l'Ouest qui veulent acceder aux marches regionaux."
        ),
        "full_description": (
            "Le projet Making Trade Work for Women in West Africa preselectionne des entreprises feminines porteuses de projets "
            "d'expansion commerciale sur les marches regionaux et transfrontaliers. Il cible le renforcement des capacites, "
            "l'acces au marche, la structuration commerciale et les opportunites d'export regional."
        ),
        "eligibility_criteria": (
            "Entreprises dirigees ou fortement portees par des femmes, basees dans les pays cibles du projet, avec un projet "
            "d'expansion commerciale ou transfrontaliere."
        ),
        "funding_details": (
            "Accompagnement, appui technique et mise en relation. L'appel identifie est clos, mais le projet couvre 2024-2029 "
            "et peut relancer de nouvelles vagues."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme pluriannuel a surveiller pour les prochains appels entreprises feminines.",
        "source_url": "https://ceci.org/fr/nouvelles-et-evenements/appel-a-manifestation-dinteret-pre-selection-dentreprises-feminines-porteuses-de-projet-dexpansion-commerciale-sur-les-marches-regionaux-et-transfrontaliers-en-afrique-de-louest",
        "source_name": "CECI MTWW - commerce feminin Afrique de l'Ouest",
        "keywords": ["CECI", "MTWW", "femmes", "commerce", "Benin", "Burkina Faso", "Cote d'Ivoire"],
    },
    {
        "title": "SOE Benin 2026 - rencontres investisseurs et opportunites business",
        "organism": "SOE Benin",
        "country": "Benin",
        "region": "Benin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "accompagnement",
        "aid_nature": "mise_en_relation",
        "sectors": ["entrepreneuriat", "investissement", "business", "partenariats"],
        "beneficiaries": ["entrepreneur", "pme", "startup", "investisseur"],
        "short_description": (
            "SOE Benin est un rendez-vous d'affaires pour connecter entrepreneurs, investisseurs et partenaires."
        ),
        "full_description": (
            "La Semaine d'Opportunites aux Entrepreneurs au Benin propose des panels, rencontres B2B, masterclass et espaces "
            "de networking pour aider les entrepreneurs a acceder a des partenaires, investisseurs et opportunites d'affaires."
        ),
        "eligibility_criteria": (
            "Entrepreneurs, PME, startups, investisseurs ou acteurs de l'ecosysteme entrepreneurial souhaitant developper des "
            "partenariats au Benin."
        ),
        "funding_details": (
            "Evenement de mise en relation et d'opportunites business, pas une subvention directe. Inscriptions annoncees jusqu'au 31 mai 2026."
        ),
        "status": "open",
        "open_date": date(2026, 5, 1),
        "close_date": date(2026, 5, 31),
        "source_url": "https://soe-benin.com/",
        "source_name": "SOE Benin - Semaine d'Opportunites aux Entrepreneurs",
        "keywords": ["Benin", "SOE", "entrepreneurs", "investisseurs", "B2B"],
    },
    {
        "title": "African Cashew Alliance - appels et opportunites cajou",
        "organism": "African Cashew Alliance",
        "country": "Afrique",
        "region": "Benin, Burkina Faso, Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "regional",
        "device_type": "appel à projets",
        "aid_nature": "opportunite_sectorielle",
        "sectors": ["cajou", "agriculture", "agrotransformation", "export"],
        "beneficiaries": ["entreprise agroalimentaire", "cooperative", "expert", "consultant", "pme"],
        "short_description": (
            "L'African Cashew Alliance publie des appels sectoriels pour la filiere cajou en Afrique."
        ),
        "full_description": (
            "L'African Cashew Alliance relaie des appels a candidatures, initiatives de donnees de marche, expertises et "
            "programmes sectoriels utiles aux acteurs de la filiere cajou dans les pays producteurs d'Afrique de l'Ouest."
        ),
        "eligibility_criteria": (
            "Entreprises, cooperatives, experts ou organisations travaillant dans la filiere cajou, notamment au Benin, au Burkina Faso "
            "et en Cote d'Ivoire selon les appels."
        ),
        "funding_details": (
            "Opportunites sectorielles variables : missions, appels a expertise, donnees marche ou programmes d'appui. Verifier chaque appel."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Source sectorielle a surveiller pour les prochains appels cajou.",
        "source_url": "https://www.africancashewalliance.com/fr/news-and-info/cashew-news/2026-appel-candidatures-rejoignez-notre-initiative-du-systeme",
        "source_name": "African Cashew Alliance - appels cajou",
        "keywords": ["cajou", "Benin", "Burkina Faso", "Cote d'Ivoire", "agrotransformation"],
    },
    {
        "title": "Fondation Facilite Sahel - prequalification ONG locales",
        "organism": "Fondation Facilite Sahel",
        "country": "Sahel",
        "region": "Burkina Faso, Mali, Mauritanie, Niger, Tchad",
        "zone": "Sahel",
        "geographic_scope": "regional",
        "device_type": "appel à projets",
        "aid_nature": "subvention_ong",
        "sectors": ["eau", "assainissement", "developpement rural", "ong", "resilience"],
        "beneficiaries": ["ong locale", "association", "organisation communautaire"],
        "short_description": (
            "La Fondation Facilite Sahel prequalifie des ONG locales pour de futurs appels a projets au Sahel."
        ),
        "full_description": (
            "La Fondation Facilite Sahel finance ou prepare des appels pour des ONG locales actives dans l'acces a l'eau, "
            "l'assainissement, le developpement rural et la resilience dans les pays du Sahel, dont le Burkina Faso."
        ),
        "eligibility_criteria": (
            "ONG locales ou organisations de terrain presentes dans les pays saheliens cibles, avec une capacite de mise en oeuvre "
            "de projets communautaires."
        ),
        "funding_details": (
            "La prequalification 2026 est close depuis le 10 mai 2026. Les ONG retenues pourront acceder a un appel complet prevu "
            "debut 2027."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Source importante pour ONG au Burkina Faso, a suivre pour l'appel complet 2027.",
        "source_url": "https://www.pseau.org/appel-projet/la-fondation-facilite-sahel-lance-son-appel-a-projet/",
        "source_name": "Fondation Facilite Sahel - appels ONG locales",
        "keywords": ["Burkina Faso", "Sahel", "ONG", "eau", "assainissement", "subvention"],
    },
    {
        "title": "OSEZ - entrepreneurs d'Afrique occidentale francophone",
        "organism": "T World Investment",
        "country": "Afrique de l'Ouest",
        "region": "Benin, Burkina Faso, Cote d'Ivoire, Togo, Niger",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "regional",
        "device_type": "concours",
        "aid_nature": "prix_accompagnement",
        "sectors": ["entrepreneuriat", "pme", "startup", "innovation"],
        "beneficiaries": ["entrepreneur", "startup", "pme", "porteur projet"],
        "short_description": (
            "OSEZ est un appel regional pour entrepreneurs francophones d'Afrique de l'Ouest."
        ),
        "full_description": (
            "OSEZ cible les entrepreneurs d'Afrique occidentale francophone et met en avant des projets a potentiel de croissance. "
            "La source est utile pour Kafundo, mais doit rester qualifiee manuellement car les informations de date et de montant "
            "peuvent varier selon l'edition."
        ),
        "eligibility_criteria": (
            "Entrepreneurs ou porteurs de projets bases dans les pays francophones cibles, dont Benin, Burkina Faso et Cote d'Ivoire."
        ),
        "funding_details": (
            "Prix, accompagnement ou mise en relation selon l'edition. Les montants et dates doivent etre confirmes sur la source officielle."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Concours prive regional a qualifier avant publication comme appel ouvert.",
        "source_url": "https://startupmedias.africa/articles/osez-lappel-de-projet-dedie-aux-entrepreneurs-dafrique-occidentale-francophone",
        "source_name": "OSEZ Afrique de l'Ouest francophone",
        "keywords": ["OSEZ", "entrepreneuriat", "Benin", "Burkina Faso", "Cote d'Ivoire"],
    },
    {
        "title": "Nice African Talents Awards - jeunes entrepreneurs en Cote d'Ivoire",
        "organism": "Nicepay Group",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "concours",
        "aid_nature": "prix_startup",
        "sectors": ["entrepreneuriat", "innovation", "startup", "jeunesse"],
        "beneficiaries": ["jeune entrepreneur", "startup", "porteur projet"],
        "short_description": (
            "Nice African Talents Awards recompense des jeunes entrepreneurs ivoiriens avec des prix financiers."
        ),
        "full_description": (
            "Nice African Talents Awards est un challenge entrepreneurial en Cote d'Ivoire qui vise a identifier et soutenir "
            "des jeunes entrepreneurs prometteurs. Les editions precedentes prevoient des dotations et de la visibilite."
        ),
        "eligibility_criteria": (
            "Jeunes entrepreneurs ou startups bases en Cote d'Ivoire selon les categories de l'edition."
        ),
        "funding_details": (
            "Dotations indiquees sur certaines editions : jusqu'a 10 000 USD pour les premiers prix. L'edition identifiee est close ; "
            "surveiller la prochaine ouverture."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Concours a surveiller pour les prochaines editions.",
        "source_url": "https://nicepaygroup.com/Awards.php",
        "source_name": "Nice African Talents Awards Cote d'Ivoire",
        "keywords": ["Cote d'Ivoire", "Nice African Talents", "startup", "concours", "jeunes"],
    },
    {
        "title": "UNESCO FIDC - financement pour diversite culturelle",
        "organism": "UNESCO",
        "country": "International",
        "region": "Benin, Burkina Faso, Cote d'Ivoire",
        "zone": "International",
        "geographic_scope": "international",
        "device_type": "subvention",
        "aid_nature": "subvention_culture",
        "sectors": ["culture", "industries creatives", "politique culturelle", "ong"],
        "beneficiaries": ["ong", "institution publique", "organisation internationale"],
        "short_description": (
            "Le FIDC finance des projets qui renforcent les industries culturelles et creatives dans les pays en developpement."
        ),
        "full_description": (
            "Le Fonds international pour la diversite culturelle de l'UNESCO soutient des projets structurants pour les secteurs "
            "culturels et creatifs, en particulier dans les pays en developpement parties a la Convention 2005."
        ),
        "eligibility_criteria": (
            "Organisations non gouvernementales, institutions publiques ou organisations internationales eligibles dans les pays "
            "parties a la Convention 2005, dont les pays cibles de Kafundo selon les criteres UNESCO."
        ),
        "funding_details": (
            "Subvention UNESCO selon l'appel annuel. L'appel 2026 est clos depuis debut mai 2026 ; surveiller l'appel 2027."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Fonds annuel a surveiller pour les prochaines fenetres de candidature.",
        "source_url": "https://www.unesco.org/creativity/fr/articles/lappel-demandes-de-financement-2026-du-fonds-international-pour-la-diversite-culturelle-est-present?hub=11",
        "source_name": "UNESCO FIDC - diversite culturelle",
        "keywords": ["UNESCO", "FIDC", "culture", "Benin", "Burkina Faso", "Cote d'Ivoire"],
    },
    {
        "title": "Freedom250 Cote d'Ivoire - competences, IA et entrepreneuriat",
        "organism": "U.S. Mission to Cote d'Ivoire",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "grant_education",
        "sectors": ["education", "entrepreneuriat", "technologie", "ia", "anglais"],
        "beneficiaries": ["ong", "institution education", "association", "individu"],
        "short_description": (
            "L'ambassade des Etats-Unis finance des projets de formation aux competences, a l'anglais, a l'IA et a l'entrepreneuriat."
        ),
        "full_description": (
            "Freedom250 in Cote d'Ivoire American Spaces soutient des projets qui renforcent l'employabilite des jeunes, "
            "les competences en anglais, les technologies pratiques comme l'IA et le codage, ainsi que l'entrepreneuriat. "
            "Les activites doivent etre mises en oeuvre via le reseau American Spaces en Cote d'Ivoire."
        ),
        "eligibility_criteria": (
            "Organisations a but non lucratif, institutions educatives ou individus capables de deployer des activites pour les "
            "jeunes de 17 a 40 ans a Abidjan, Yamoussoukro, Bouake ou Korhogo."
        ),
        "funding_details": (
            "Subventions de 10 000 a 19 000 USD. Date limite : 15 juin 2026."
        ),
        "amount_min": Decimal("9200"),
        "amount_max": Decimal("17480"),
        "status": "open",
        "open_date": date(2026, 5, 5),
        "close_date": date(2026, 6, 15),
        "source_url": "https://simpler.grants.gov/opportunity/018e7c4a-2f90-4cf5-b772-4976b21df920",
        "source_name": "U.S. Embassy Abidjan - Freedom250 American Spaces",
        "keywords": ["Cote d'Ivoire", "Freedom250", "American Spaces", "IA", "entrepreneuriat"],
    },
    {
        "title": "AECF IIW Burkina Faso - entrepreneuriat feminin et economie verte",
        "organism": "Africa Enterprise Challenge Fund",
        "country": "Burkina Faso",
        "region": "Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "subvention_femmes",
        "sectors": ["entrepreneuriat feminin", "economie verte", "energie", "agriculture", "climat"],
        "beneficiaries": ["organisation femmes", "ong", "consortium", "structure accompagnement"],
        "short_description": (
            "AECF soutient l'entrepreneuriat feminin et les entreprises travaillant pour une economie plus verte au Burkina Faso."
        ),
        "full_description": (
            "L'appel IIW Burkina Faso vise des organisations ou consortiums capables de renforcer l'acces des femmes entrepreneures "
            "au financement, aux marches et aux solutions d'economie verte. La source reste importante pour les prochaines vagues AECF."
        ),
        "eligibility_criteria": (
            "Organisations ou consortiums actifs au Burkina Faso, avec experience en entrepreneuriat feminin, inclusion economique "
            "ou economie verte."
        ),
        "funding_details": (
            "Subvention selon les termes AECF. La fenetre 2026 identifiee est close ; surveiller les prochaines editions."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Source AECF prioritaire pour le Burkina Faso, a surveiller pour nouvelles fenetres.",
        "source_url": "https://www.aecfafrica.org/wp-content/uploads/2026/01/TOR-CALL-FOR-PROPOSALS-FOR-WRO-Burkina-Faso.pdf",
        "source_name": "AECF IIW Burkina Faso - entrepreneuriat feminin vert",
        "keywords": ["AECF", "Burkina Faso", "femmes", "economie verte", "subvention"],
    },
    {
        "title": "AECF ODDF Benin - organisations de droits des femmes",
        "organism": "Africa Enterprise Challenge Fund",
        "country": "Benin",
        "region": "Benin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "subvention_ong",
        "sectors": ["droits des femmes", "entrepreneuriat feminin", "inclusion", "plaidoyer"],
        "beneficiaries": ["ong", "organisation femmes", "consortium"],
        "short_description": (
            "AECF soutient des organisations beninoises qui renforcent les droits des femmes et l'entrepreneuriat feminin."
        ),
        "full_description": (
            "L'appel ODDF Benin cible des organisations ou consortiums de defense des droits des femmes dans le cadre du programme "
            "Investir dans l'entrepreneuriat feminin. Il vise a lever les obstacles structurels a l'acces au financement et aux marches."
        ),
        "eligibility_criteria": (
            "Organisations de defense des droits des femmes ou consortiums operant au Benin, avec capacite de mise en oeuvre et "
            "experience sur l'autonomisation economique."
        ),
        "funding_details": (
            "Subvention AECF selon appel. La fenetre 2026 identifiee est close ; surveiller les prochains appels."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Source AECF prioritaire pour le Benin, a surveiller pour prochaines fenetres.",
        "source_url": "https://www.aecfafrica.org/wp-content/uploads/2026/01/TDR-APPEL-A-PROJETS-ODDF-BENIN-FINAL.pdf",
        "source_name": "AECF ODDF Benin - droits des femmes et entrepreneuriat",
        "keywords": ["AECF", "Benin", "femmes", "ONG", "subvention"],
    },
    {
        "title": "Fonds MIWA+ - soutien aux organisations LBTQI francophones",
        "organism": "Global Philanthropy Project / Fonds MIWA+",
        "country": "Afrique de l'Ouest",
        "region": "Benin, Burkina Faso, Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "regional",
        "device_type": "subvention",
        "aid_nature": "subvention_osc",
        "sectors": ["droits humains", "genre", "association", "inclusion"],
        "beneficiaries": ["organisation communautaire", "association", "osc"],
        "short_description": (
            "Le Fonds MIWA+ soutient des organisations communautaires francophones en Afrique de l'Ouest."
        ),
        "full_description": (
            "Le Fonds MIWA+ est une opportunite de financement regional pour renforcer l'autonomie et la capacite d'action "
            "d'organisations LBTQI francophones en Afrique de l'Ouest."
        ),
        "eligibility_criteria": (
            "Organisations communautaires ou associations francophones travaillant sur les droits, l'inclusion et l'autonomisation "
            "des publics cibles en Afrique de l'Ouest."
        ),
        "funding_details": (
            "Subvention selon l'appel annuel ou edition speciale. Verifier la fenetre active avant candidature."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Fonds regional a surveiller pour les prochaines fenetres.",
        "source_url": "https://globalphilanthropyproject.org/grants/fonds-miwa/",
        "source_name": "Fonds MIWA+ Afrique de l'Ouest",
        "keywords": ["MIWA", "Afrique de l'Ouest", "OSC", "genre", "subvention"],
    },
    {
        "title": "WELA Rise - preparation a la levee de fonds pour femmes entrepreneures",
        "organism": "WELA Mawusse",
        "country": "Afrique francophone",
        "region": "Benin, Burkina Faso, Cote d'Ivoire",
        "zone": "Afrique francophone",
        "geographic_scope": "regional",
        "device_type": "accompagnement",
        "aid_nature": "preparation_financement",
        "sectors": ["entrepreneuriat feminin", "agrotransformation", "tech", "economie verte"],
        "beneficiaries": ["femme entrepreneure", "startup", "pme"],
        "short_description": (
            "WELA Rise aide les femmes entrepreneures francophones a structurer leur croissance et leur levee de fonds."
        ),
        "full_description": (
            "WELA Rise est un programme d'accompagnement pour femmes entrepreneures en Afrique francophone. Il cible notamment "
            "l'agrotransformation, la tech inclusive et l'economie verte, avec un accent sur le dossier d'investissement, la "
            "strategie de croissance et la preparation a la levee de fonds."
        ),
        "eligibility_criteria": (
            "Femmes entrepreneures portant une entreprise ou un projet dans les secteurs cibles, avec ambition de croissance et "
            "besoin de structuration financiere."
        ),
        "funding_details": (
            "Accompagnement, mentorat, reseau et preparation au financement. Pas de subvention directe garantie."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme recurrent a surveiller pour nouvelles cohortes.",
        "source_url": "https://www.wela-mawusse.com/wela-rise/",
        "source_name": "WELA Rise - femmes entrepreneures Afrique francophone",
        "keywords": ["WELA Rise", "femmes", "levee de fonds", "Benin", "Burkina Faso", "Cote d'Ivoire"],
    },
    {
        "title": "Afrique Innovante - competition femmes entrepreneures et PME tech",
        "organism": "CPCCAF / Afrique Innovante",
        "country": "Afrique",
        "region": "Benin, Burkina Faso, Cote d'Ivoire",
        "zone": "Afrique",
        "geographic_scope": "international",
        "device_type": "concours",
        "aid_nature": "prix_accompagnement",
        "sectors": ["innovation", "entrepreneuriat feminin", "technologie", "pme"],
        "beneficiaries": ["femme entrepreneure", "startup", "pme technologique"],
        "short_description": (
            "Afrique Innovante valorise les projets innovants portes par des femmes entrepreneures africaines."
        ),
        "full_description": (
            "Afrique Innovante est une competition panafricaine qui identifie et propulse des projets innovants portes par des "
            "femmes entrepreneures, startups et PME technologiques engagees dans la transformation du continent."
        ),
        "eligibility_criteria": (
            "Femmes entrepreneures, startups innovantes ou PME technologiques africaines, selon les criteres de l'appel."
        ),
        "funding_details": (
            "Prix, visibilite, accompagnement et mise en reseau selon l'edition. Dates et montants a confirmer sur la source."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Competition a surveiller pour les prochaines editions.",
        "source_url": "https://www.pi-francophone.org/blog/evenements-3/cpccaf-appel-a-candidatures-pour-femmes-entrepreneures-start-up-innovantes-et-pme-technologiques-africaines-68",
        "source_name": "Afrique Innovante - femmes entrepreneures CPCCAF",
        "keywords": ["Afrique Innovante", "femmes", "startup", "PME", "innovation"],
    },
    {
        "title": "RISE 2 Benin - appui technique et financier pour TPE/PME",
        "organism": "RVO / Invest International / VC4A",
        "country": "Benin",
        "region": "Benin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "appui_technique_financier",
        "sectors": ["artisanat", "industries creatives", "restauration", "numerique", "ville durable"],
        "beneficiaries": ["tpe", "pme", "femme entrepreneure", "entreprise en croissance"],
        "short_description": (
            "RISE 2 accompagne les TPE/PME beninoises avec un appui technique et financier pour accelerer leur croissance."
        ),
        "full_description": (
            "RISE 2 poursuit l'accompagnement des entreprises beninoises avec deux guichets : un guichet PAEB pour TPE/PME en croissance, "
            "notamment dans les regions Centre et Nord et pour les femmes porteuses de projets, et un accompagnement sur des secteurs "
            "comme artisanat, industries culturelles et creatives, restauration, numerique et ville durable."
        ),
        "eligibility_criteria": (
            "TPE/PME formalisees au Benin, en croissance ou porteuses d'un projet structurant dans les secteurs cibles. Une attention "
            "particuliere est portee aux femmes et aux entreprises des regions Centre et Nord."
        ),
        "funding_details": (
            "Appui technique et financier selon le guichet. Appel ouvert du 7 mai au 7 juin 2026."
        ),
        "status": "open",
        "open_date": date(2026, 5, 7),
        "close_date": date(2026, 6, 7),
        "source_url": "https://vc4a.com/rise/rise-2026/?lang=en",
        "source_name": "RISE 2 Benin - projet d'accompagnement PME",
        "keywords": ["Benin", "RISE 2", "PME", "femmes", "appui financier", "VC4A"],
    },
    {
        "title": "CHINNOVA - recherche et innovation climat-sante",
        "organism": "Association of African Universities / CHINNOVA",
        "country": "Afrique de l'Ouest",
        "region": "Benin, Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "regional",
        "device_type": "subvention",
        "aid_nature": "subvention_recherche",
        "sectors": ["sante", "climat", "recherche", "innovation", "politique publique"],
        "beneficiaries": ["universite", "institut recherche", "ong recherche", "institution"],
        "short_description": (
            "CHINNOVA finance des projets de recherche et innovation sur la resilience climat-sante en Afrique de l'Ouest."
        ),
        "full_description": (
            "CHINNOVA soutient des projets collaboratifs sur les liens entre changement climatique et systemes de sante. Les projets "
            "doivent produire des resultats utiles aux politiques publiques, aux communautes et aux systemes de sante resilients."
        ),
        "eligibility_criteria": (
            "Universites, instituts de recherche, ONG avec mandat de recherche et institutions engagees dans la recherche climat-sante "
            "dans les pays eligibles, dont le Benin et la Cote d'Ivoire."
        ),
        "funding_details": (
            "Jusqu'a 200 000 USD par projet sur 24 mois selon l'appel. La fenetre 2026 est close depuis le 8 mai 2026 ; surveiller les prochains appels."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Programme de financement recherche climat-sante a surveiller pour futures vagues.",
        "source_url": "https://chinnova.aau.org/chinnova-launches-second-call-for-proposals-to-strengthen-climate-resilient-health-systems-in-west-and-central-africa/",
        "source_name": "CHINNOVA - climat et sante Afrique de l'Ouest",
        "keywords": ["CHINNOVA", "Benin", "Cote d'Ivoire", "climat", "sante", "recherche"],
    },
    {
        "title": "FNEC Benin - appels environnement et climat",
        "organism": "Fonds National pour l'Environnement et le Climat du Benin",
        "country": "Benin",
        "region": "Benin",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "subvention",
        "aid_nature": "subvention_environnement",
        "sectors": ["environnement", "climat", "developpement durable", "biodiversite"],
        "beneficiaries": ["ong", "association", "collectivite", "pme verte"],
        "short_description": (
            "Le FNEC finance des projets environnementaux et climatiques au Benin via des appels a projets."
        ),
        "full_description": (
            "Le Fonds National pour l'Environnement et le Climat du Benin publie des appels a projets pour soutenir des initiatives "
            "de protection de l'environnement, d'adaptation climatique, de gestion durable des ressources et de developpement durable."
        ),
        "eligibility_criteria": (
            "Organisations, collectivites, associations ou acteurs economiques portant un projet environnemental au Benin, selon les "
            "criteres de chaque appel."
        ),
        "funding_details": (
            "Subvention selon les editions FNEC. Les appels actifs doivent etre verifies sur la page officielle avant publication comme ouverts."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Fonds national recurrent a surveiller pour nouvelles dates.",
        "source_url": "https://www.fnec.bj/appel-a-projet.php",
        "source_name": "FNEC Benin - environnement et climat",
        "keywords": ["Benin", "FNEC", "environnement", "climat", "subvention"],
    },
    {
        "title": "PeaceNexus - environnement et paix pour organisations locales",
        "organism": "PeaceNexus Foundation",
        "country": "Afrique de l'Ouest",
        "region": "Benin, Burkina Faso",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "regional",
        "device_type": "subvention",
        "aid_nature": "grant_accompagnement",
        "sectors": ["environnement", "climat", "biodiversite", "paix", "cohesion sociale"],
        "beneficiaries": ["ong environnement", "organisation locale", "organisation regionale"],
        "short_description": (
            "PeaceNexus accompagne et finance des organisations environnementales qui veulent integrer la sensibilite aux conflits."
        ),
        "full_description": (
            "L'appel Environment and Peace cible les organisations environnementales basees au Benin, au Burkina Faso ou dans la region, "
            "qui souhaitent renforcer leurs pratiques de sensibilite aux conflits dans leurs actions climat, biodiversite ou conservation."
        ),
        "eligibility_criteria": (
            "Organisations locales, nationales ou regionales dont la mission principale porte sur l'environnement, la biodiversite ou le climat, "
            "basees au Benin, Burkina Faso, Niger, Senegal ou Cameroun, ou operant regionalement."
        ),
        "funding_details": (
            "Accompagnement et subventions de 15 000 a 45 000 CHF par phase, jusqu'a trois phases. La fenetre 2026 est close ; surveiller les prochains appels."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Source forte pour ONG environnement Benin/Burkina, a surveiller pour nouvelles fenetres.",
        "source_url": "https://peacenexus.org/environment-and-peace-open-calls-for-new-partners/",
        "source_name": "PeaceNexus - environnement et paix Afrique de l'Ouest",
        "keywords": ["PeaceNexus", "Benin", "Burkina Faso", "environnement", "paix", "subvention"],
    },
    {
        "title": "OIF Cote d'Ivoire - consolidation de l'initiative cuisson propre",
        "organism": "Organisation internationale de la Francophonie",
        "country": "Cote d'Ivoire",
        "region": "Cote d'Ivoire",
        "zone": "Afrique de l'Ouest",
        "geographic_scope": "national",
        "device_type": "appel à projets",
        "aid_nature": "subvention_climat",
        "sectors": ["energie", "climat", "cuisson propre", "entrepreneuriat social"],
        "beneficiaries": ["association", "ong", "entreprise sociale", "acteur energie"],
        "short_description": (
            "L'OIF soutient des projets de cuisson propre et d'ancrage economique de la filiere en Cote d'Ivoire."
        ),
        "full_description": (
            "Dans le cadre du projet Innovations et Plaidoyers francophones, l'OIF a lance un appel pour consolider l'initiative "
            "cuisson propre en Cote d'Ivoire et renforcer son ancrage economique."
        ),
        "eligibility_criteria": (
            "Organisations, associations, entreprises sociales ou acteurs de la filiere cuisson propre en Cote d'Ivoire, selon les criteres "
            "de l'appel."
        ),
        "funding_details": (
            "Subvention selon appel OIF. La fenetre identifiee etait ouverte jusqu'au 10 mai 2026 et est maintenant close ; surveiller une nouvelle edition."
        ),
        "status": "recurring",
        "is_recurring": True,
        "recurrence_notes": "Source OIF sectorielle a surveiller pour nouvelles initiatives climat/energie en Cote d'Ivoire.",
        "source_url": "https://www.francophonie.org/consolidation-de-linitiative-cuisson-propre-en-cote-divoire-8442",
        "source_name": "OIF - cuisson propre Cote d'Ivoire",
        "keywords": ["OIF", "Cote d'Ivoire", "cuisson propre", "energie", "climat"],
    },
]


def _sections(device: dict) -> list[dict]:
    sections = [
        ("Présentation", device["full_description"]),
        ("Critères d'éligibilité", device["eligibility_criteria"]),
        ("Montant / avantages", device["funding_details"]),
    ]
    if device.get("close_date"):
        sections.append(("Calendrier", f"Clôture : {device['close_date'].strftime('%d/%m/%Y')}."))
    else:
        sections.append(("Calendrier", "Date limite non communiquée par la source officielle."))
    sections.append(("Démarche", "Consulter la source officielle et déposer le dossier selon les modalités indiquées."))
    return [{"title": title, "content": content} for title, content in sections if content]


async def upsert_source(db, data: dict) -> Source:
    row = await db.execute(select(Source).where(Source.url == data["url"]))
    source = row.scalar_one_or_none()
    if not source:
        source = Source(**data, is_active=True)
        db.add(source)
        await db.flush()
        return source
    for key, value in data.items():
        setattr(source, key, value)
    source.is_active = True
    return source


async def upsert_device(db, data: dict, source: Source) -> str:
    row = await db.execute(select(Device).where(Device.source_url == data["source_url"]))
    device = row.scalar_one_or_none()
    created = False
    if not device:
        device = Device(source_url=data["source_url"])
        db.add(device)
        created = True

    payload = {k: v for k, v in data.items() if k != "source_name"}
    for key, value in payload.items():
        setattr(device, key, value)
    device.slug = generate_slug(data["title"])
    device.title_normalized = normalize_title(data["title"])
    device.source_id = source.id
    device.source_raw = data["full_description"]
    device.content_sections_json = _sections(data)
    device.ai_rewrite_status = "done"
    device.ai_rewritten_sections_json = _sections(data)
    device.language = "fr"
    device.confidence_score = 90
    device.completeness_score = 88
    device.ai_readiness_score = 88
    device.ai_readiness_label = "pret_pour_recommandation_ia"
    device.ai_readiness_reasons = ["source officielle", "date ou statut exploitable", "sections métier complètes"]
    device.validation_status = "auto_published"
    return "created" if created else "updated"


async def main():
    async with AsyncSessionLocal() as db:
        sources = {}
        for source_data in TARGET_SOURCES:
            source = await upsert_source(db, source_data)
            sources[source_data["name"]] = source

        counts = {"created": 0, "updated": 0}
        for device_data in TARGET_DEVICES:
            status = await upsert_device(db, device_data, sources[device_data["source_name"]])
            counts[status] += 1

        # Renforce la fiche AECF déjà présente pour Bénin/Burkina afin qu'elle remonte sur les profils ciblés.
        row = await db.execute(
            select(Device).where(Device.title.ilike("%entrepreneuriat feminin%Benin%Burkina Faso%"))
        )
        aecf = row.scalar_one_or_none()
        if aecf:
            aecf.country = "Afrique de l'Ouest"
            aecf.region = "Bénin, Burkina Faso"
            aecf.zone = "Afrique de l'Ouest"
            aecf.device_type = "subvention"
            aecf.status = "recurring"
            aecf.is_recurring = True
            aecf.validation_status = "auto_published"
            aecf.confidence_score = max(aecf.confidence_score or 0, 85)
            aecf.completeness_score = max(aecf.completeness_score or 0, 80)
            aecf.ai_readiness_score = max(aecf.ai_readiness_score or 0, 82)
            aecf.ai_readiness_label = "pret_pour_recommandation_ia"
            counts["updated"] += 1

        noisy_geo_rules = [
            ("%Eswatini%", "Eswatini", "Eswatini", "national"),
            ("%East Africa%", "Afrique de l'Est", "Afrique de l'Est", "regional"),
            ("%Funguo Innovation Programme%", "Tanzanie", "Tanzanie", "national"),
            ("%iHatch%", "Nigeria", "Nigeria", "national"),
            ("%PRIMA Young Innovators%", "Méditerranée", "Méditerranée", "regional"),
        ]
        for pattern, country, region, scope in noisy_geo_rules:
            noise_rows = (
                await db.execute(select(Device).where(Device.title.ilike(pattern)))
            ).scalars().all()
            for device in noise_rows:
                if device.country == "Afrique":
                    device.country = country
                    device.region = region
                    device.geographic_scope = scope
                    counts["updated"] += 1

        await db.commit()
        print(counts)


if __name__ == "__main__":
    asyncio.run(main())
