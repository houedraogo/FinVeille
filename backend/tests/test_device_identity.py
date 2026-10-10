"""Identité des fiches : cas réels relevés dans l'audit de production (octobre 2026)."""
import pytest

from app.services.device_identity import (
    DuplicateIndex,
    DuplicateTier,
    assess_pair,
    canonical_url,
    is_generic_organism,
    title_key,
    title_key_loose,
    url_variants,
)

GENERIC = "DGE / aides-entreprises.fr"


def device(title, url, organism=GENERIC, country="France", id=None):
    return {"id": id, "title": title, "organism": organism, "country": country, "source_url": url}


# --- canonicalisation ------------------------------------------------------

def test_title_key_unifies_apostrophes_accents_and_case():
    assert title_key("Aide à l’investissement immobilier") == title_key("AIDE A L'INVESTISSEMENT  IMMOBILIER")


def test_title_key_keeps_years_but_loose_key_drops_years_and_type_prefix():
    assert title_key("Appel 2025") != title_key("Appel 2026")
    assert title_key_loose("Appel 2025") == title_key_loose("Appel 2026")
    assert title_key_loose("Concours - UNESCO Prize 2026") == title_key_loose("UNESCO Prize 2026")


def test_canonical_url_ignores_scheme_www_slash_fragment_and_tracking():
    base = canonical_url("https://www.cnm.fr/aides/international/")
    assert base == "cnm.fr/aides/international"
    assert canonical_url("http://cnm.fr/aides/international#top") == base
    assert canonical_url("https://cnm.fr/aides/international?utm_source=x") == base


def test_home_pages_and_relative_urls_do_not_identify_a_device():
    assert canonical_url("https://www.schwabfound.org") is None
    assert canonical_url("http://www.amjura.fr/") is None
    assert canonical_url("/aides/9c30-etre-accompagne/") is None
    assert canonical_url(None) is None


def test_url_variants_cover_scheme_and_www_forms():
    variants = url_variants("https://www.cnm.fr/aides/international")
    assert "http://cnm.fr/aides/international" in variants
    assert "https://www.cnm.fr/aides/international/" in variants


def test_generic_organisms_are_recognised():
    assert is_generic_organism("DGE / aides-entreprises.fr")
    assert is_generic_organism(None)
    assert not is_generic_organism("Bpifrance")


# --- paliers de doublon ----------------------------------------------------

def test_same_page_and_title_across_sources_is_certain():
    manual = device("Fonds de soutien au commerce rural", "https://anct.gouv.fr/programmes-dispositifs/reconquete-commerce-rural", organism="ANCT")
    csv = device("Fonds de soutien au commerce rural", "https://anct.gouv.fr/programmes-dispositifs/reconquete-commerce-rural/", organism=GENERIC)
    result = assess_pair(manual, csv)
    assert result.tier is DuplicateTier.CERTAIN and result.mergeable


def test_old_and_new_slug_rows_of_the_same_aid_are_certain():
    old = device("Programme LEADER 2023-2027 - Action 'Soutenir les services et commerces'", "http://www.syndicat-mixte-sarreguemines.org/upload/documents/synthese.pdf")
    new = device("Programme LEADER 2023-2027 - Action ’Soutenir les services et commerces’", "http://www.syndicat-mixte-sarreguemines.org/upload/documents/synthese.pdf")
    assert assess_pair(old, new).tier is DuplicateTier.CERTAIN


def test_type_prefix_variant_on_the_same_page_is_certain():
    a = device("Concours - UNESCO Opens Nominations for the Al Fozan Prize", "https://globalsouthopportunities.com/unesco-al-fozan-prize", organism="UNESCO")
    b = device("UNESCO Opens Nominations for the Al Fozan Prize", "https://globalsouthopportunities.com/unesco-al-fozan-prize", organism="UNESCO")
    assert assess_pair(a, b).tier is DuplicateTier.CERTAIN


def test_homonymous_territorial_aids_are_never_mergeable():
    """71 « Aide à l'immobilier d'entreprise » : une par collectivité, règlements distincts."""
    a = device("Aide à l'immobilier d'entreprise", "https://sologne-des-rivieres.fr/wp-content/uploads/2023/07/Reglement-aide-immo.pdf")
    b = device("Aide à l'immobilier d'entreprise", "https://www.grandreims.fr/reimsbusiness/reims-business-des-services-aux-entreprises")
    result = assess_pair(a, b)
    assert result.tier is DuplicateTier.HOMONYM
    assert not result.mergeable


def test_homonym_guard_also_holds_for_typographic_variants_of_the_generic_title():
    a = device("Aide à l’investissement immobilier industriel, artisanal ou tertiaire", "https://www.aides-entreprises.fr/aide/12492")
    b = device("Aide à l'investissement immobilier, industriel, artisanal ou tertiaire", "https://www.aides-entreprises.fr/aide/10679")
    assert assess_pair(a, b).tier is DuplicateTier.HOMONYM


def test_same_title_same_specific_organism_without_common_page_is_only_probable():
    a = device("Prêt d'honneur création", "https://initiative-france.fr/pret-a", organism="Initiative France")
    b = device("Prêt d'honneur création", "https://initiative-france.fr/pret-b", organism="Initiative France")
    result = assess_pair(a, b)
    assert result.tier is DuplicateTier.PROBABLE
    assert not result.mergeable


def test_cross_portal_same_title_with_generic_vs_specific_organism_is_probable_not_certain():
    ae = device("Crédit d'impôt recherche (CIR)", "https://www.aides-entreprises.fr/aide/4521")
    la = device("Crédit d'impôt recherche (CIR)", "https://les-aides.fr/aide/XyZ/cir", organism="CCI Hauts-de-France / les-aides.fr")
    assert assess_pair(ae, la).tier is DuplicateTier.PROBABLE


def test_different_edition_years_of_the_same_call_are_not_duplicates():
    a = device("Programme d'accélération 2025 pour startups africaines", "https://vc4a.com/programme", organism="VC4A")
    b = device("Programme d'accélération 2026 pour startups africaines", "https://vc4a.com/programme", organism="VC4A")
    assert assess_pair(a, b).tier is DuplicateTier.NONE


def test_other_country_is_never_a_duplicate():
    a = device("Fonds PME", "https://x.org/fonds-pme", organism="Org", country="France")
    b = device("Fonds PME", "https://x.org/fonds-pme", organism="Org", country="Bénin")
    assert assess_pair(a, b).tier is DuplicateTier.NONE


def test_same_title_other_specific_organism_is_not_a_duplicate():
    a = device("Fonds d'amorçage", "https://a.fr/fonds", organism="Bpifrance")
    b = device("Fonds d'amorçage", "https://b.fr/fonds", organism="Région Bretagne")
    assert assess_pair(a, b).tier is DuplicateTier.NONE


# --- pages « liste » -------------------------------------------------------

def test_listing_page_shared_by_many_different_titles_proves_nothing():
    """Jeu de données AFD (114 projets) : même URL, titres différents."""
    url = "https://opendata.afd.fr/explore/dataset/les-projets-de-l-afd"
    devices = [device(f"Projet AFD numéro {i}", url, organism="AFD", id=i) for i in range(5)]
    index = DuplicateIndex(devices)
    assert index.distinct_titles_for_url("opendata.afd.fr/explore/dataset/les-projets-de-l-afd") == 5
    assert index.assess(devices[0]) == []


def test_listing_page_with_identical_title_twice_is_still_not_certain_when_page_is_a_listing():
    url = "http://www.cc-montesquieu.fr/livret.pdf"
    devices = [
        device("Programme LEADER - Action A", url, id=1),
        device("Programme LEADER - Action B", url, id=2),
        device("Programme LEADER - Action C", url, id=3),
        device("Programme LEADER - Action A", url, id=4),
    ]
    index = DuplicateIndex(devices)
    pairs = index.assess(devices[0])
    assert all(not assessment.mergeable for _other, assessment in pairs)


def test_index_finds_certain_duplicate_among_many():
    devices = [device(f"Aide numéro {i}", f"https://exemple.fr/aide-{i}", organism="Org", id=i) for i in range(50)]
    devices.append(device("Aide numéro 7", "https://www.exemple.fr/aide-7/", organism="Org", id=999))
    index = DuplicateIndex(devices)
    found = index.assess(devices[7])
    assert [other["id"] for other, _a in found] == [999]
    assert found[0][1].mergeable
