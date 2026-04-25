from datetime import date

from app.services.content_section_builder import build_content_sections, render_sections_markdown


def make_device(**overrides):
    payload = {
        "title": "Aide a l'innovation",
        "organism": "Bpifrance",
        "country": "France",
        "device_type": "subvention",
        "source_url": "https://example.org/aide",
        "short_description": "Aide destinee a soutenir les PME dans leurs projets innovants.",
        "eligibility_criteria": "PME francaises avec un projet innovant et un dossier complet.",
        "funding_details": "Subvention jusqu'a 30 000 EUR selon le projet.",
        "open_date": None,
        "close_date": date(2026, 6, 30),
        "recurrence_notes": None,
        "tags": ["deadline:known", "taxonomy:subvention"],
    }
    payload.update(overrides)
    return payload


def test_builds_all_ai_sections():
    sections = build_content_sections(make_device(), {"name": "Bpifrance", "reliability": 5})

    keys = [section["key"] for section in sections]

    assert keys == [
        "presentation",
        "eligibility",
        "funding",
        "calendar",
        "procedure",
        "official_source",
        "checks",
    ]
    assert "Cloture : 30/06/2026" in sections[3]["content"]
    assert "Source de reference : Bpifrance." in sections[5]["content"]


def test_renders_markdown_for_front_and_rag():
    markdown = render_sections_markdown(build_content_sections(make_device()))

    assert "## Presentation" in markdown
    assert "## Criteres d'eligibilite" in markdown
    assert "## Montant / avantages" in markdown
    assert "## Points a verifier" in markdown


def test_unknown_deadline_creates_cautious_calendar_and_check():
    sections = build_content_sections(
        make_device(close_date=None, tags=["deadline:not_communicated", "quality:unknown_deadline"])
    )

    calendar = next(section for section in sections if section["key"] == "calendar")
    checks = next(section for section in sections if section["key"] == "checks")

    assert "Date limite non communiquee" in calendar["content"]
    assert "Date limite absente" in checks["content"]


def test_bpifrance_html_noise_is_removed_from_sections():
    noisy = (
        "Accueil Appels a projets et concours Concours d'innovation: i-PhD 23 mars au 30 avril 2026 "
        "Concours d'innovation: i-PhD Jeunes chercheurs: La science est un super-pouvoir, activez-le avec le concours i-PhD, "
        "et rejoignez une communaute de chercheurs entrepreneurs. Appels a projets Deeptech Innovation AAP Nationale Innovation "
        "Date 23 mars au 30 avril 2026 Deposez votre dossier Documents a telecharger Guide Demarche Numerique 2026 "
        "Reglement i-PhD 2026 FAQ concours i-PhD 2026 i-PhD est un concours d'innovation de l'Etat opere par Bpifrance."
    )

    sections = build_content_sections(
        make_device(
            title="Concours d'innovation : i-PhD",
            short_description=noisy,
            funding_details="",
            device_type="aap",
        ),
        {"name": "Bpifrance - appels a projets et concours", "reliability": 4},
    )

    presentation = next(section for section in sections if section["key"] == "presentation")["content"]
    funding = next(section for section in sections if section["key"] == "funding")["content"]

    assert not presentation.startswith("Accueil")
    assert "Documents a telecharger" not in presentation
    assert "jeunes chercheurs" in presentation.lower()
    assert "programme d'accompagnement" in funding
    assert "doivent etre confirmes" in funding
