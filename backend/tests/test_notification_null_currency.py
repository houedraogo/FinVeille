"""Notification amounts: a NULL currency renders the bare amount, never "None"/"null"/EUR/an inferred currency."""
import datetime
import re
from types import SimpleNamespace as NS

import pytest

from app.services import notification_service as ns
from app.services.notification_service import NotificationService


def dev(amount, currency, **kw):
    base = dict(id="1", title="Fonds test", amount_max=amount, amount_min=None, currency=currency, close_date=datetime.date(2026, 12, 1),
                status="open", organism="Org", country="France", device_type="subvention", short_description="desc",
                source_url="https://example.org/x", funding_rate=None, tags=[], sectors=[], deadline=None, days_left=10)
    base.update(kw)
    return NS(**base)


def text(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


class TestHelper:
    @pytest.mark.parametrize("amount,currency,expected", [
        (5_000_000, None, "jusqu'à 5,000,000"),
        (5_000_000, "EUR", "jusqu'à 5,000,000 EUR"),
        (20_000, "USD", "jusqu'à 20,000 USD"),
        (None, None, ""),
        (0, None, ""),
        (None, "EUR", ""),
        (5_000_000, "", "jusqu'à 5,000,000"),
        (5_000_000, "None", "jusqu'à 5,000,000"),
    ])
    def test_object_and_dict(self, amount, currency, expected):
        assert ns._format_device_amount(dev(amount, currency)) == expected
        assert ns._format_device_amount({"amount_max": amount, "currency": currency}) == expected

    def test_dict_without_currency_key_shows_bare_amount(self):
        assert ns._format_device_amount({"amount_max": 1000}) == "jusqu'à 1,000"


class TestAllTemplates:
    def renderers(self, d):
        return {
            "device_row": lambda: ns._device_row(d),
            "alert": lambda: NotificationService.build_alert_email("U", [d], "Alerte"),
            "new_opportunity": lambda: NotificationService.build_new_opportunity_alert_email("U", "Alerte", [d], 1),
            "digest": lambda: NotificationService.build_digest_email("U", [d], [d]),
            "deadline": lambda: NotificationService.build_deadline_reminder_email("U", [d]),
        }

    @pytest.mark.parametrize("name", ["device_row", "alert", "new_opportunity", "digest", "deadline"])
    def test_null_currency_renders_bare_amount(self, name):
        html = self.renderers(dev(5_000_000, None))[name]()
        t = text(html)
        assert "5,000,000" in t
        assert not re.search(r"\b(None|null)\b", t)
        assert not re.search(r"5,000,000\s*(EUR|USD|€)", t)

    @pytest.mark.parametrize("name", ["device_row", "alert", "new_opportunity", "digest", "deadline"])
    def test_source_currency_still_displayed(self, name):
        t = text(self.renderers(dev(20_000, "USD"))[name]())
        assert "20,000 USD" in t

    @pytest.mark.parametrize("name", ["device_row", "alert", "new_opportunity", "digest", "deadline"])
    def test_no_amount_no_monetary_fragment(self, name):
        t = text(self.renderers(dev(None, None))[name]())
        assert "jusqu'à" not in t
        assert not re.search(r"\b(None|null)\b", t)
