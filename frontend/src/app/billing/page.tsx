"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Check, CreditCard, ExternalLink, Loader2, Lock, Sparkles } from "lucide-react";
import clsx from "clsx";

import AppLayout from "@/components/AppLayout";
import LimitNotice from "@/components/LimitNotice";
import { billing } from "@/lib/api";

interface Plan {
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
  plan: Plan;
  subscription_status: string;
  usage: Record<string, number>;
  limits: Record<string, number>;
  features: Record<string, boolean>;
}

const LIMIT_LABELS: Record<string, string> = {
  users: "Utilisateurs",
  alerts: "Veilles actives",
  saved_searches: "Recherches sauvegardees",
  pipeline_projects: "Opportunités suivies",
};

const FEATURE_LABELS: Record<string, string> = {
  matching_ai: "Recommandations",
  smart_scoring: "Scoring intelligent",
  custom_alerts: "Alertes personnalisees",
  collaboration: "Collaboration d'equipe",
  advanced_analysis: "Analyse avancee",
  exports: "Exports CSV/Excel",
  api_access: "API",
  strategic_watch: "Veille strategique",
  private_sources: "Sources privees",
  funding_support: "Accompagnement financement",
};

function formatLimit(value: number | undefined) {
  if (value === undefined) return "Inclus";
  if (value < 0) return "Illimite";
  return value.toLocaleString("fr");
}

export default function BillingPage() {
  // Lire ?plan= côté client pour éviter useSearchParams et son Suspense requis au build
  const planParam = typeof window !== "undefined"
    ? new URLSearchParams(window.location.search).get("plan")
    : null;
  const autoCheckoutDone = useRef(false);

  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyPlan, setBusyPlan] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([billing.plans(), billing.subscription()])
      .then(([plansData, subscriptionData]) => {
        setPlans(plansData || []);
        setSubscription(subscriptionData || null);
      })
      .catch((error) => setFeedback(error.message || "Impossible de charger l'abonnement."))
      .finally(() => setLoading(false));
  }, []);

  const currentPlanSlug = subscription?.plan?.slug || "free";

  // Auto-checkout : si l'utilisateur vient de WordPress avec ?plan=pro, lancer Stripe directement
  useEffect(() => {
    if (loading || !planParam || autoCheckoutDone.current) return;
    const targetPlan = plans.find((p) => p.slug === planParam);
    if (!targetPlan || targetPlan.slug === currentPlanSlug) return;
    autoCheckoutDone.current = true; // évite de déclencher deux fois
    handleCheckout(planParam);
  }, [loading, plans, planParam, currentPlanSlug]); // eslint-disable-line react-hooks/exhaustive-deps

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
      setFeedback(response.message || "Checkout pret.");
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
      setFeedback(response.message || "Portail billing pret.");
    } catch (error: any) {
      setFeedback(error.message || "Impossible d'ouvrir le portail billing.");
    } finally {
      setBusyPlan(null);
    }
  };

  return (
    <AppLayout>
      <div className="mb-8 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-medium text-primary-600">Abonnement SaaS</p>
          <h1 className="mt-1 text-2xl font-bold text-slate-950">Plans et limites</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Controlez l'usage de Kafundo par organisation : veilles, recommandations, exports, sources privees et suivi des opportunités.
          </p>
        </div>
        <button type="button" onClick={handlePortal} className="btn-secondary text-xs" disabled={busyPlan === "portal"}>
          {busyPlan === "portal" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CreditCard className="h-3.5 w-3.5" />}
          Gerer la facturation
        </button>
      </div>

      {/* Bandeau auto-checkout depuis WordPress */}
      {planParam && planParam !== "free" && busyPlan === planParam && (
        <div className="mb-6 flex items-center gap-3 rounded-2xl border border-primary-100 bg-primary-50 px-4 py-3 text-sm text-primary-800">
          <Loader2 className="h-4 w-4 animate-spin flex-shrink-0 text-primary-600" />
          <span>Redirection vers le paiement sécurisé pour le plan <strong className="capitalize">{planParam}</strong>…</span>
        </div>
      )}

      {feedback && (
        <div className="mb-6 rounded-2xl border border-primary-100 bg-primary-50 px-4 py-3 text-sm text-primary-800">
          {feedback}
        </div>
      )}

      {reachedLimits.length > 0 && (
        <div className="mb-6">
          <LimitNotice
            title="Une limite de votre plan est atteinte"
            message={`Limite concernee : ${reachedLimits.map(([metric]) => LIMIT_LABELS[metric] || metric).join(", ")}.`}
          />
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Chargement des plans...
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-4">
          {plans.map((plan) => {
            const isCurrent = plan.slug === currentPlanSlug;
            const isEnterprise = plan.slug === "enterprise";
            return (
              <section
                key={plan.slug}
                className={clsx(
                  "flex flex-col rounded-[28px] border bg-white p-5 shadow-[0_18px_50px_-34px_rgba(15,23,42,0.4)]",
                  isCurrent ? "border-primary-300 ring-2 ring-primary-100" : "border-slate-200",
                )}
              >
                <div className="mb-5">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <h2 className="text-lg font-semibold text-slate-950">{plan.name}</h2>
                    {isCurrent && <span className="rounded-full bg-primary-50 px-2.5 py-1 text-xs font-medium text-primary-700">Plan actuel</span>}
                  </div>
                  <p className="min-h-[48px] text-sm leading-6 text-slate-500">{plan.description}</p>
                  <div className="mt-4">
                    {isEnterprise ? (
                      <p className="text-2xl font-bold text-slate-950">Sur devis</p>
                    ) : (
                      <p className="text-3xl font-bold text-slate-950">
                        {plan.price_monthly_eur} EUR
                        <span className="text-sm font-medium text-slate-400"> / mois</span>
                      </p>
                    )}
                  </div>
                </div>

                <div className="space-y-3 border-t border-slate-100 pt-4">
                  {Object.entries(LIMIT_LABELS).map(([key, label]) => (
                    <div key={key} className="flex items-center justify-between gap-3 text-sm">
                      <span className="text-slate-500">{label}</span>
                      <span className="font-semibold text-slate-900">{formatLimit(plan.limits?.[key])}</span>
                    </div>
                  ))}
                </div>

                <div className="mt-4 space-y-2 border-t border-slate-100 pt-4">
                  {Object.entries(FEATURE_LABELS).map(([key, label]) => {
                    const enabled = !!plan.features?.[key];
                    return (
                      <div key={key} className="flex items-center gap-2 text-sm">
                        {enabled ? <Check className="h-4 w-4 text-emerald-500" /> : <Lock className="h-4 w-4 text-slate-300" />}
                        <span className={enabled ? "text-slate-700" : "text-slate-400"}>{label}</span>
                      </div>
                    );
                  })}
                </div>

                <div className="mt-auto pt-5">
                  {isEnterprise ? (
                    <a
                      href="mailto:contact@kafundo.com"
                      className="btn-secondary w-full justify-center text-xs"
                    >
                      Contacter l'équipe
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  ) : isCurrent ? (
                    <button
                      type="button"
                      disabled
                      className="btn-secondary w-full justify-center text-xs opacity-60"
                    >
                      Offre active
                    </button>
                  ) : plan.slug === "free" ? (
                    <button
                      type="button"
                      onClick={() => handleCheckout(plan.slug)}
                      disabled={busyPlan === plan.slug}
                      className="btn-secondary w-full justify-center text-xs"
                    >
                      {busyPlan === plan.slug ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                      Commencer gratuitement
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleCheckout(plan.slug)}
                      disabled={busyPlan === plan.slug}
                      className="btn-primary w-full justify-center text-xs"
                    >
                      {busyPlan === plan.slug ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                      Essayer 14 jours
                    </button>
                  )}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </AppLayout>
  );
}
