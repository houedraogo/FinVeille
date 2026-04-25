from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import and_, delete, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.organization import OrganizationMember
from app.models.relevance import DeviceRelevanceCache, FundingProject, OrganizationProfile
from app.models.user import User


@dataclass
class RelevanceResult:
    device_id: UUID
    organization_id: UUID
    funding_project_id: UUID | None
    relevance_score: int
    relevance_label: str
    priority_level: str
    eligibility_confidence: str
    decision_hint: str
    reason_codes: list[str]
    reason_texts: list[str]
    computed_at: datetime


class OpportunityRelevanceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_current_organization_id(self, user: User) -> UUID | None:
        result = await self.db.execute(
            select(OrganizationMember)
            .where(OrganizationMember.user_id == user.id, OrganizationMember.is_active == True)
            .order_by(OrganizationMember.joined_at.asc())
        )
        memberships = list(result.scalars().all())
        if not memberships:
            return None
        if user.default_organization_id:
            for membership in memberships:
                if membership.organization_id == user.default_organization_id:
                    return membership.organization_id
        return memberships[0].organization_id

    async def get_profile(self, organization_id: UUID) -> OrganizationProfile | None:
        result = await self.db.execute(
            select(OrganizationProfile).where(OrganizationProfile.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_project(self, organization_id: UUID, project_id: UUID | None = None) -> FundingProject | None:
        query = select(FundingProject).where(FundingProject.organization_id == organization_id)
        if project_id:
            query = query.where(FundingProject.id == project_id)
        else:
            query = query.order_by(FundingProject.is_primary.desc(), FundingProject.updated_at.desc())
        result = await self.db.execute(query.limit(1))
        return result.scalar_one_or_none()

    def evaluate_device(
        self,
        device: Device,
        *,
        organization_id: UUID,
        profile: OrganizationProfile | None,
        project: FundingProject | None = None,
    ) -> RelevanceResult:
        computed_at = datetime.now(timezone.utc)
        reason_codes: list[str] = []
        reason_texts: list[str] = []
        score = 0

        target_countries = self._merged_values(profile.countries if profile else None, project.countries if project else None)
        target_sectors = self._merged_values(profile.sectors if profile else None, project.sectors if project else None)
        target_types = self._merged_values(
            profile.target_funding_types if profile else None,
            project.target_funding_types if project else None,
        )
        target_beneficiaries = self._normalized_set(project.beneficiaries if project else None)

        if target_sectors:
            matched = sorted(self._normalized_set(device.sectors) & target_sectors)
            if matched:
                score += 24
                reason_codes.append("sector_match")
                reason_texts.append(f"Correspond à vos secteurs prioritaires : {', '.join(matched[:2])}.")

        if target_countries and self._normalize_text(device.country) in target_countries:
            score += 22
            reason_codes.append("country_match")
            reason_texts.append(f"Disponible dans votre zone prioritaire : {device.country}.")

        if target_types and self._normalize_text(device.device_type) in target_types:
            score += 18
            reason_codes.append("funding_type_match")
            reason_texts.append("Le type de financement correspond à votre recherche actuelle.")

        if target_beneficiaries:
            matched = sorted(self._normalized_set(device.beneficiaries) & target_beneficiaries)
            if matched:
                score += 10
                reason_codes.append("beneficiary_match")
                reason_texts.append(f"Le public visé est cohérent avec votre profil : {', '.join(matched[:2])}.")

        amount_alignment = self._score_amount_alignment(device, profile, project)
        if amount_alignment:
            score += amount_alignment
            reason_codes.append("ticket_match")
            reason_texts.append("Le montant semble cohérent avec votre besoin de financement.")

        if device.status == "open":
            score += 8
            reason_codes.append("status_open")
            reason_texts.append("L'opportunité est actuellement ouverte.")
        elif device.status == "recurring":
            score += 6
            reason_codes.append("status_recurring")
            reason_texts.append("Le financement semble permanent ou récurrent.")

        if device.close_date:
            days_left = (device.close_date - date.today()).days
            if 0 <= days_left <= 14:
                score += 4
                reason_codes.append("deadline_close")
                reason_texts.append(f"Deadline proche : {days_left} jours restants.")
            elif 15 <= days_left <= 60:
                score += 8
                reason_codes.append("deadline_usable")
                reason_texts.append("Le calendrier laisse encore un délai d'action raisonnable.")
        elif device.status == "open":
            score -= 8
            reason_codes.append("deadline_unknown")
            reason_texts.append("La date limite n'est pas clairement confirmée par la source.")

        if (device.confidence_score or 0) >= 75:
            score += 6
            reason_codes.append("source_confident")
            reason_texts.append("La qualité de la fiche est jugée fiable.")
        elif (device.confidence_score or 0) < 45:
            score -= 6
            reason_codes.append("source_weak")
            reason_texts.append("La fiche reste partiellement incertaine et demande une vérification.")

        if device.validation_status == "pending_review":
            score -= 8
            reason_codes.append("pending_review")
            reason_texts.append("Certaines informations sont encore à confirmer avant décision.")

        score = max(0, min(100, score))
        relevance_label = self._label_from_score(score)
        priority_level = self._priority_from_score(score, device)
        eligibility_confidence = self._eligibility_confidence(device, score)
        decision_hint = self._decision_hint(device, score, priority_level)

        if not reason_texts:
            reason_codes.append("generic_fit")
            reason_texts.append("Cette opportunité présente quelques signaux d'intérêt, mais demande une vérification métier.")

        return RelevanceResult(
            device_id=device.id,
            organization_id=organization_id,
            funding_project_id=project.id if project else None,
            relevance_score=score,
            relevance_label=relevance_label,
            priority_level=priority_level,
            eligibility_confidence=eligibility_confidence,
            decision_hint=decision_hint,
            reason_codes=reason_codes[:6],
            reason_texts=reason_texts[:4],
            computed_at=computed_at,
        )

    async def evaluate_devices(
        self,
        devices: Iterable[Device],
        *,
        user: User,
        project_id: UUID | None = None,
    ) -> list[RelevanceResult]:
        organization_id = await self.get_current_organization_id(user)
        if not organization_id:
            return []
        profile = await self.get_profile(organization_id)
        project = await self.get_project(organization_id, project_id)
        return [
            self.evaluate_device(device, organization_id=organization_id, profile=profile, project=project)
            for device in devices
        ]

    async def attach_runtime_relevance(
        self,
        devices: Iterable[Device],
        *,
        user: User,
        project_id: UUID | None = None,
    ) -> list[Device]:
        items = list(devices)
        results = await self.evaluate_devices(items, user=user, project_id=project_id)
        by_device_id = {result.device_id: result for result in results}
        for item in items:
            result = by_device_id.get(item.id)
            if not result:
                continue
            if inspect(item).session is not None:
                self.db.expunge(item)
            item.relevance_score = result.relevance_score
            item.relevance_label = result.relevance_label
            item.relevance_reasons = result.reason_texts
            item.priority_level = result.priority_level
            item.eligibility_confidence = result.eligibility_confidence
            item.decision_hint = result.decision_hint
            item.match_reasons = result.reason_texts[:3]
        return items

    async def save_cache(self, result: RelevanceResult) -> DeviceRelevanceCache:
        query = select(DeviceRelevanceCache).where(
            DeviceRelevanceCache.device_id == result.device_id,
            DeviceRelevanceCache.organization_id == result.organization_id,
        )
        if result.funding_project_id:
            query = query.where(DeviceRelevanceCache.funding_project_id == result.funding_project_id)
        else:
            query = query.where(DeviceRelevanceCache.funding_project_id.is_(None))

        existing = (await self.db.execute(query)).scalar_one_or_none()
        if existing:
            existing.relevance_score = result.relevance_score
            existing.relevance_label = result.relevance_label
            existing.priority_level = result.priority_level
            existing.eligibility_confidence = result.eligibility_confidence
            existing.decision_hint = result.decision_hint
            existing.reason_codes = result.reason_codes
            existing.reason_texts = result.reason_texts
            existing.computed_at = result.computed_at
            cache = existing
        else:
            cache = DeviceRelevanceCache(
                device_id=result.device_id,
                organization_id=result.organization_id,
                funding_project_id=result.funding_project_id,
                relevance_score=result.relevance_score,
                relevance_label=result.relevance_label,
                priority_level=result.priority_level,
                eligibility_confidence=result.eligibility_confidence,
                decision_hint=result.decision_hint,
                reason_codes=result.reason_codes,
                reason_texts=result.reason_texts,
                computed_at=result.computed_at,
            )
            self.db.add(cache)

        await self.db.flush()
        return cache

    async def refresh_cache_for_scope(
        self,
        *,
        user: User,
        devices: Iterable[Device],
        project_id: UUID | None = None,
    ) -> list[DeviceRelevanceCache]:
        results = await self.evaluate_devices(list(devices), user=user, project_id=project_id)
        caches: list[DeviceRelevanceCache] = []
        for result in results:
            caches.append(await self.save_cache(result))
        await self.db.commit()
        return caches

    async def clear_project_cache(self, organization_id: UUID, project_id: UUID) -> None:
        await self.db.execute(
            delete(DeviceRelevanceCache).where(
                and_(
                    DeviceRelevanceCache.organization_id == organization_id,
                    DeviceRelevanceCache.funding_project_id == project_id,
                )
            )
        )
        await self.db.commit()

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        return " ".join((value or "").strip().lower().split())

    def _normalized_set(self, values: Iterable[str] | None) -> set[str]:
        return {self._normalize_text(value) for value in values or [] if self._normalize_text(value)}

    def _merged_values(self, left: Iterable[str] | None, right: Iterable[str] | None) -> set[str]:
        return self._normalized_set(left) | self._normalized_set(right)

    def _score_amount_alignment(
        self,
        device: Device,
        profile: OrganizationProfile | None,
        project: FundingProject | None,
    ) -> int:
        desired_min = (project.budget_min if project and project.budget_min is not None else None) or (
            profile.preferred_ticket_min if profile else None
        )
        desired_max = (project.budget_max if project and project.budget_max is not None else None) or (
            profile.preferred_ticket_max if profile else None
        )
        device_min = self._to_decimal(device.amount_min)
        device_max = self._to_decimal(device.amount_max)
        if desired_min is None and desired_max is None:
            return 0
        if device_min is None and device_max is None:
            return 0

        floor = self._to_decimal(desired_min)
        ceiling = self._to_decimal(desired_max)
        low = device_min or device_max
        high = device_max or device_min
        if low is None or high is None:
            return 0

        if floor is not None and high < floor:
            return -4
        if ceiling is not None and low > ceiling:
            return -2
        return 8

    @staticmethod
    def _to_decimal(value) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except Exception:
            return None

    @staticmethod
    def _label_from_score(score: int) -> str:
        if score >= 80:
            return "Très pertinent pour votre structure"
        if score >= 60:
            return "Pertinent mais à vérifier"
        if score >= 40:
            return "Possible sous conditions"
        return "Peu prioritaire pour votre profil"

    @staticmethod
    def _priority_from_score(score: int, device: Device) -> str:
        if device.close_date:
            days_left = (device.close_date - date.today()).days
            if 0 <= days_left <= 14 and score >= 55:
                return "haute"
        if score >= 75:
            return "haute"
        if score >= 50:
            return "moyenne"
        return "faible"

    @staticmethod
    def _eligibility_confidence(device: Device, score: int) -> str:
        if device.eligibility_criteria and len((device.eligibility_criteria or "").strip()) >= 120 and score >= 60:
            return "éligibilité probable"
        if score >= 45:
            return "à confirmer"
        return "incertaine"

    @staticmethod
    def _decision_hint(device: Device, score: int, priority_level: str) -> str:
        if priority_level == "haute" and device.close_date:
            return "Bonne opportunité à traiter rapidement. Confirmez les critères puis lancez l'action."
        if score >= 70:
            return "Bonne opportunité pour votre profil. Priorisez cette aide dans votre suivi."
        if score >= 45:
            return "Opportunité intéressante, mais certaines conditions doivent être confirmées avant décision."
        return "À surveiller seulement si elle s'inscrit dans une priorité stratégique claire."
