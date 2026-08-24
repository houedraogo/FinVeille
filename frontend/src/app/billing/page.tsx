"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Check, X, CreditCard, Loader2, Sparkles, Zap,
  BarChart3, Globe, HeartHandshake, Star, ArrowRight,
  FileSearch, Target, TrendingUp, PhoneCall,
} from "lucide-react";
import clsx from "clsx";

import AppLayout from "@/components/AppLayout";
import LimitNotice from "@/components/LimitNotice";
import { billing } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ApiPlan {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  price_monthly_eur: number;
  currency: string;
  limits: Record<string, number>;
  features: Record<string, boolean>;
}

interface Subscription {
  plan: ApiPlan;
  subscription_status: string;
  usage: Record<string, number>;
  limits: Record<string, number>;
  features: Record<string, boolean>;
}

// ---------------------------------------------------------------------------
// Plan catalog — design-driven, API overrides price/status
// ---------------------------------------------------------------------------

interface PlanDef {
  slug: string;
  name: string;
  tagline: string;
  price: number | null;         // null = sur devis
  priceNote?: string;
  accentClass: string;          // Tailwind classes for accent colour
  headerClass: string;          // card header bg
  badge?: string;
  target: string;
  features: { label: string; included: boolean }[];
  limits: { label: string; value: string }[];
  ctaLabel: string;
  ctaClass: string;
  isContact?: boolean;
}

const PLANS: PlanDef[] = [
  {
    slug: "free",
    name: "Découverte",
    tagline: "Explorez la plateforme sans engagement",
    price: 0,
    accentClass: "border-emerald-200",
    headerClass: "bg-emerald-50",
    target: "Premiers pas",
    features: [
      { label: "Accès à 50 dispositifs/mois", included: true },
      { label: "2 alertes de veille", included: true },
      { label: "3 recherches sauvegardées", included: true },
      { label: "Pipeline limité (5 dossiers)", included: true },
      { label: "Matching IA", included: false },
      { label: "Exports CSV / Excel", included: false },
      { label: "Collaboration équipe", included: false },
    ],
    limits: [
      { label: "Utilisateurs", value: "1" },
      { label: "Alertes", value: "2" },
      { label: "Dossiers pipeline", value: "5" },
    ],
    ctaLabel: "Commencer gratuitement",
    ctaClass: "border border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100",
  },
  {
    slug: "pro",
    name: "Pro",
    tagline: "Maximisez vos chances de financement",
    price: 49,
    accentClass: "border-primary-300",
    headerClass: "bg-primary-600",
    badge: "Populaire",
    target: "Indépendants & PME",
    features: [
      { label: "Dispositifs illimités", included: true },
      { label: "Matching IA personnalisé", included: true },
      { label: "Scoring intelligent", included: true },
      { label: "20 alertes personnalisées", included: true },
      { label: "Pipeline complet", included: true },
      { label: "Exports CSV / Excel", included: false },
      { label: "Collaboration équipe", included: false },
    ],
    limits: [
      { label: "Utilisateurs", value: "1" },
      { label: "Alertes", value: "20" },
      { label: "Dossiers pipeline", value: "100" },
    ],
    ctaLabel: "Démarrer en Pro",
    ctaClass: "bg-primary-600 text-white hover:bg-primary-700",
  },
  {
    slug: "team",
    name: "Team",
    tagline: "Collaborez sur les dossiers en équipe",
    price: 179,
    accentClass: "border-violet-300",
    headerClass: "bg-violet-600",
    badge: "Équipes",
    target: "Cabinets & équipes",
    features: [
      { label: "Tout le plan Pro", included: true },
      { label: "Jusqu'à 10 utilisateurs", included: true },
      { label: "Espace de collaboration", included: true },
      { label: "Dossiers partagés", included: true },
      { label: "100 alertes", included: true },
      { label: "Exports CSV / Excel", included: true },
      { label: "Sources privées", included: true },
    ],
    limits: [
      { label: "Utilisateurs", value: "10" },
      { label: "Alertes", value: "100" },
      { label: "Dossiers pipeline", value: "500" },
    ],
    ctaLabel: "Essayer Team",
    ctaClass: "bg-violet-600 text-white hover:bg-violet-700",
  },
  {
    slug: "expert",
    name: "Expert",
    tagline: "Veille stratégique et analyse avancée",
    price: 399,
    accentClass: "border-orange-300",
    headerClass: "bg-slate-950",
    badge: "Avancé",
    target: "Experts & grandes structures",
    features: [
      { label: "Tout le plan Team", included: true },
      { label: "Utilisateurs illimités", included: true },
      { label: "Analyse avancée & rapports", included: true },
      { label: "Alertes illimitées", included: true },
      { label: "Accès API REST", included: true },
      { label: "Sources privées & exclusives", included: true },
      { label: "Veille stratégique dédiée", included: true },
    ],
    limits: [
      { label: "Utilisateurs", value: "Illimité" },
      { label: "Alertes", value: "Illimitées" },
      { label: "Dossiers pipeline", value: "Illimité" },
    ],
    ctaLabel: "Passer Expert",
    ctaClass: "bg-slate-900 text-white hover:bg-slate-800",
  },
];

const ACCOMPAGNEMENT: PlanDef = {
  slug: "accompagnement",
  name: "Accompagnement Financement",
  tagline: "Un expert dédié à votre stratégie de financement",
  price: null,
  priceNote: "Sur devis — engagement personnalisé",
  accentClass: "border-amber-300",
  headerClass: "bg-gradient-to-r from-amber-500 to-orange-500",
  target: "Startups, ETI, grandes entreprises",
  features: [],
  limits: [],
  ctaLabel: "Nous contacter",
  ctaClass: "bg-amber-500 text-white hover:bg-amber-600",
  isContact: true,
};

const ACCOMPAGNEMENT_FEATURES = [
  { icon: FileSearch, label: "Audit de financement", detail: "Analyse complète de votre situation et des financements accessibles." },
  { icon: Target, label: "Stratégie sur-mesure", detail: "Plan de financement personnalisé avec priorisation des dispositifs à fort impact." },
  { icon: HeartHandshake, label: "Accompagnement dossier", detail: "Un expert vous guide de la candidature jusqu'à l'obtention des fonds." },
  { icon: TrendingUp, label: "Maximisation des chances", detail: "Revue et optimisation des dossiers pour maximiser le taux de succès." },
  { icon: PhoneCall, label: "Coach dédié", detail: "Accès direct à votre référent financement, disponible tout au long du processus." },
  { icon: Star, label: "Accès Expert inclus", detail: "Toutes les fonctionnalités de l'offre Expert incluses pendant la mission." },
];

// ---------------------------------------------------------------------------
// Composants
// ---------------------------------------------------------------------------

function FeatureRow({ label, included }: { label: string; included: boolean }) {
  return (
    <div className="flex items-start gap-2.5 text-sm">
      {included
        ? <Check className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-emerald-500" />
        : <X className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-slate-300" />
      }
      <span className={included ? "text-slate-700" : "text-slate-400"}>{label}</span>
    </div>
  );
}

function PlanCard({
  plan,
  isCurrent,
  onCheckout,
  busy,
}: {
  plan: PlanDef;
  isCurrent: boolean;
  onCheckout: (slug: string) => void;
  busy: boolean;
}) {
  const isWhiteHeader = plan.headerClass === "bg-emerald-50";

  return (
    <section
      className={clsx(
        "flex flex-col rounded-[28px] border-2 bg-white overflow-hidden shadow-[0_18px_50px_-30px_rgba(15,23,42,0.3)] transition-all duration-200",
        isCurrent ? "border-primary-400 ring-4 ring-primary-50" : plan.accentClass,
      )}
    >
      {/* Header coloré */}
      <div className={clsx("px-5 pt-5 pb-6", plan.headerClass)}>
        <div className="flex items-start justify-between gap-2 mb-3">
          <div>
            {plan.badge && (
              <span className={clsx(
                "mb-2 inline-block rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.16em]",
                isWhiteHeader ? "bg-emerald-100 text-emerald-700" : "bg-white/20 text-white"
              )}>
                {plan.badge}
              </span>
            )}
            <h2 className={clsx("text-xl font-bold", isWhiteHeader ? "text-slate-900" : "text-white")}>
              {plan.name}
            </h2>
            <p className={clsx("mt-0.5 text-xs", isWhiteHeader ? "text-slate-500" : "text-white/70")}>
              {plan.target}
            </p>
          </div>
          {isCurrent && (
            <span className="flex-shrink-0 rounded-full bg-white/20 px-2.5 py-1 text-xs font-semibold text-white backdrop-blur-sm">
              Plan actuel
            </span>
          )}
        </div>

        <div className={clsx("mt-2", isWhiteHeader ? "text-slate-900" : "text-white")}>
          <span className="text-3xl font-bold">{plan.price === 0 ? "Gratuit" : `${plan.price} €`}</span>
          {plan.price !== 0 && (
            <span className={clsx("ml-1 text-sm", isWhiteHeader ? "text-slate-500" : "text-white/60")}>/mois</span>
          )}
        </div>
        <p className={clsx("mt-1 text-xs leading-5", isWhiteHeader ? "text-slate-500" : "text-white/70")}>
          {plan.tagline}
        </p>
      </div>

      {/* Contenu */}
      <div className="flex flex-1 flex-col px-5 py-5">
        <div className="space-y-2.5 flex-1">
          {plan.features.map((f) => (
            <FeatureRow key={f.label} label={f.label} included={f.included} />
          ))}
        </div>

        {/* Limites */}
        {plan.limits.length > 0 && (
          <div className="mt-4 rounded-2xl bg-slate-50 px-3 py-3 space-y-1.5 border border-slate-100">
            {plan.limits.map((l) => (
              <div key={l.label} className="flex items-center justify-between text-xs">
                <span className="text-slate-500">{l.label}</span>
                <span className="font-semibold text-slate-800">{l.value}</span>
              </div>
            ))}
          </div>
        )}

        {/* CTA */}
        <div className="mt-5">
          <button
            type="button"
            onClick={() => onCheckout(plan.slug)}
            disabled={isCurrent || busy}
            className={clsx(
              "flex w-full items-center justify-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-60",
              isCurrent ? "border border-slate-200 bg-slate-50 text-slate-400 cursor-default" : plan.ctaClass,
            )}
          >
            {busy
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : isCurrent
                ? <Check className="h-4 w-4" />
                : <Sparkles className="h-4 w-4" />
            }
            {isCurrent ? "Votre plan actuel" : plan.ctaLabel}
          </button>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const LIMIT_LABELS: Record<string, string> = {
  users: "Utilisateurs",
  alerts: "Alertes",
  saved_searches: "Recherches sauvegardees",
  pipeline_projects: "Projets suivis",
};

export default function BillingPage() {
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyPlan, setBusyPlan] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([billing.plans(), billing.subscription()])
      .then(([, subscriptionData]) => {
        setSubscription(subscriptionData || null);
      })
      .catch((error) => setFeedback(error.message || "Impossible de charger l'abonnement."))
      .finally(() => setLoading(false));
  }, []);

  const currentPlanSlug = subscription?.plan?.slug || "free";

  const reachedLimits = useMemo(() => {
    if (!subscription) return [];
    return Object.entries(subscription.limits || {}).filter(([metric, limit]) => {
      if (typeof limit !== "number" || limit < 0) return false;
      return (subscription.usage?.[metric] || 0) >= limit;
    });
  }, [subscription]);

  const handleCheckout = async (planSlug: string) => {
    setBusyPlan(planSlug);
    setFeedback(null);
    try {
      const response = await billing.checkout(planSlug);
      if (response.checkout_url?.startsWith("http")) {
        window.location.href = response.checkout_url;
        return;
      }
      setFeedback(response.message || "Checkout prêt.");
    } catch (error: any) {
      setFeedback(error.message || "Impossible de lancer le paiement.");
    } finally {
      setBusyPlan(null);
    }
  };

  const handlePortal = async () => {
    setBusyPlan("portal");
    setFeedback(null);
    try {
      const response = await billing.portal();
      if (response.portal_url?.startsWith("http")) {
        window.location.href = response.portal_url;
        return;
      }
      setFeedback(response.message || "Portail billing prêt.");
    } catch (error: any) {
      setFeedback(error.message || "Impossible d'ouvrir le portail billing.");
    } finally {
      setBusyPlan(null);
    }
  };

  return (
    <AppLayout>
      {/* ── En-tête ── */}
      <div className="mb-8 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-primary-600">Abonnement</p>
          <h1 className="mt-1 text-3xl font-bold text-slate-950">Choisissez votre offre</h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
            De la découverte à l'accompagnement expert — une offre adaptée à chaque étape de votre stratégie de financement.
          </p>
        </div>
        <button
          type="button"
          onClick={handlePortal}
          className="btn-secondary text-xs self-start lg:self-auto"
          disabled={busyPlan === "portal"}
        >
          {busyPlan === "portal" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CreditCard className="h-3.5 w-3.5" />}
          Gérer la facturation
        </button>
      </div>

      {feedback && (
        <div className="mb-6 rounded-2xl border border-primary-100 bg-primary-50 px-4 py-3 text-sm text-primary-800">
          {feedback}
        </div>
      )}

      {reachedLimits.length > 0 && (
        <div className="mb-6">
          <LimitNotice
            title="Une limite de votre plan est atteinte"
            message={`Limite concernée : ${reachedLimits.map(([metric]) => LIMIT_LABELS[metric] || metric).join(", ")}.`}
          />
        </div>
      )}

      {/* ── Bandeau ROI ── */}
      <div className="mb-8 grid grid-cols-1 gap-4 rounded-[24px] bg-gradient-to-r from-slate-900 to-primary-900 px-6 py-5 text-white sm:grid-cols-3">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl bg-white/10">
            <Zap className="h-4 w-4 text-amber-300" />
          </div>
          <div>
            <p className="text-xl font-bold">+320%</p>
            <p className="text-xs text-white/60 mt-0.5">ROI annuel moyen sur les aides obtenues</p>
          </div>
        </div>
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl bg-white/10">
            <BarChart3 className="h-4 w-4 text-emerald-300" />
          </div>
          <div>
            <p className="text-xl font-bold">x8</p>
            <p className="text-xs text-white/60 mt-0.5">de gain de temps vs veille manuelle</p>
          </div>
        </div>
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl bg-white/10">
            <Globe className="h-4 w-4 text-blue-300" />
          </div>
          <div>
            <p className="text-xl font-bold">2 500+</p>
            <p className="text-xs text-white/60 mt-0.5">dispositifs analysés chaque semaine</p>
          </div>
        </div>
      </div>

      {/* ── Grille 4 plans ── */}
      {loading ? (
        <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Chargement des offres…
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
            {PLANS.map((plan) => (
              <PlanCard
                key={plan.slug}
                plan={plan}
                isCurrent={plan.slug === currentPlanSlug}
                onCheckout={handleCheckout}
                busy={busyPlan === plan.slug}
              />
            ))}
          </div>

          {/* ── Section Accompagnement (plein largeur) ── */}
          <div className="mt-6 overflow-hidden rounded-[28px] border-2 border-amber-200 bg-white shadow-[0_24px_60px_-30px_rgba(245,158,11,0.35)]">
            {/* Header */}
            <div className="bg-gradient-to-r from-amber-500 to-orange-500 px-6 py-6 sm:px-8">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-white/20 px-3 py-1 text-xs font-bold uppercase tracking-[0.16em] text-white">
                    <Star className="h-3 w-3" />
                    Premium · Sur devis
                  </div>
                  <h2 className="text-2xl font-bold text-white">{ACCOMPAGNEMENT.name}</h2>
                  <p className="mt-1 text-sm text-white/80">{ACCOMPAGNEMENT.tagline}</p>
                </div>
                <Link
                  href="mailto:contact@kafundo.com"
                  className="flex flex-shrink-0 items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-amber-700 transition-colors hover:bg-amber-50"
                >
                  <PhoneCall className="h-4 w-4" />
                  Nous contacter
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </div>

            {/* Features 3-colonnes */}
            <div className="px-6 py-6 sm:px-8">
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {ACCOMPAGNEMENT_FEATURES.map((f) => (
                  <div key={f.label} className="flex gap-3">
                    <div className="mt-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-amber-50">
                      <f.icon className="h-4 w-4 text-amber-600" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{f.label}</p>
                      <p className="mt-0.5 text-xs leading-5 text-slate-500">{f.detail}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-6 flex flex-col gap-3 rounded-2xl bg-amber-50/60 border border-amber-100 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-slate-700">
                  <strong>Un projet de financement complexe ?</strong> Nos experts vous accompagnent de l'audit jusqu'à l'obtention des fonds.
                </p>
                <Link
                  href="mailto:contact@kafundo.com"
                  className="flex flex-shrink-0 items-center gap-2 rounded-xl bg-amber-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-amber-600"
                >
                  Demander un audit gratuit
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
          </div>

          {/* ── Note de bas de page ── */}
          <p className="mt-6 text-center text-xs text-slate-400">
            Tous les plans sont sans engagement. Annulation à tout moment depuis le portail de facturation.{" "}
            <Link href="mailto:contact@kafundo.com" className="text-primary-600 hover:underline">Contacter notre équipe</Link>
            {" "}pour toute question.
          </p>
        </>
      )}
    </AppLayout>
  );
}
