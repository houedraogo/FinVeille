"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import {
  TrendingUp, Clock, AlertTriangle, CheckCircle, Database,
  RefreshCw, Flame, ArrowRight, Globe, Sparkles, Building2,
  Users, LayoutGrid, ExternalLink, Zap, Target, Bot,
  ChevronRight, DollarSign, Timer, Star, Plus,
} from "lucide-react";

import AppLayout from "@/components/AppLayout";
import { dashboard, relevance } from "@/lib/api";
import { DEVICE_TYPE_LABELS, RecommendationItem } from "@/lib/types";
import { formatDateRelative } from "@/lib/utils";
import {
  listPipelineDevices, syncWorkspace,
  type DevicePipelineEntry, type DevicePipelineStatus,
} from "@/lib/workspace";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatEuro(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M€`;
  if (n >= 1_000)     return `${Math.round(n / 1_000)}k€`;
  return `${n}€`;
}

const TIME_ESTIMATES: Record<string, string> = {
  subvention:      "1-3 jours",
  aap:             "2-4 semaines",
  concours:        "1-2 semaines",
  pret:            "2-6 semaines",
  accompagnement:  "3-5 jours",
  garantie:        "1-3 semaines",
  investissement:  "4-8 semaines",
};

const PIPELINE_STATUS_ORDER: Record<DevicePipelineStatus, number> = {
  candidature_en_cours: 0, interessant: 1, a_etudier: 2,
  soumis: 3, refuse: 4, non_pertinent: 5,
};
const PIPELINE_STATUS_LABELS: Record<DevicePipelineStatus, string> = {
  a_etudier: "À étudier", interessant: "Prioritaire",
  candidature_en_cours: "En cours", soumis: "Soumis",
  refuse: "Refusé", non_pertinent: "Non pertinent",
};
const PIPELINE_STATUS_COLORS: Record<DevicePipelineStatus, string> = {
  a_etudier: "bg-amber-100 text-amber-700",
  interessant: "bg-violet-100 text-violet-700",
  candidature_en_cours: "bg-blue-100 text-blue-700",
  soumis: "bg-indigo-100 text-indigo-700",
  refuse: "bg-red-100 text-red-700",
  non_pertinent: "bg-slate-100 text-slate-600",
};
const PRIORITY_ORDER: Record<string, number> = { haute: 0, moyenne: 1, faible: 2 };

// ── Types ─────────────────────────────────────────────────────────────────────

interface ActionItem {
  id: string;
  icon: React.ElementType;
  iconBg: string;
  label: string;
  detail: string;
  href: string;
  badge: string;
  badgeColor: string;
}

// ── Scope config ──────────────────────────────────────────────────────────────

type FinancingScope = "public" | "private" | "both" | null;

const SCOPE_CONFIG = {
  private: {
    heroGradient: "from-violet-950 via-violet-900 to-indigo-700",
    heroBadgeBg: "bg-violet-500/20",
    heroBadgeText: "text-violet-200",
    badgeLabel: "Financement Privé",
    heroTitle: "Prospection Investisseurs",
    heroSubtitle: "Suivez les fonds d'investissement, business angels et investisseurs actifs dans vos zones prioritaires.",
    catalogHref: "/devices/private",
    catalogLabel: "Explorer les fonds",
    kpis: (s: any, pipeline: DevicePipelineEntry[]) => [
      { label: "Fonds & investisseurs actifs", value: s.total_active.toLocaleString("fr"), sub: `${s.total} au total`, icon: TrendingUp, color: "text-violet-600", bg: "bg-violet-50" },
      { label: "Nouveaux cette semaine",        value: s.new_last_7_days.toLocaleString("fr"), sub: "détectés récemment", icon: Sparkles, color: "text-indigo-600", bg: "bg-indigo-50" },
      { label: "Pays couverts",                 value: s.countries_count.toLocaleString("fr"), sub: "géographies actives", icon: Globe, color: "text-emerald-600", bg: "bg-emerald-50" },
      {
        label: "Dans mon pipeline",
        value: pipeline.filter((d) => !["refuse", "non_pertinent"].includes(d.pipelineStatus)).length.toLocaleString("fr"),
        sub: "fonds suivis activement", icon: LayoutGrid, color: "text-amber-600", bg: "bg-amber-50",
      },
    ],
    marketSignals: (s: any) => [
      { label: "Géographies les plus actives",  value: s.by_country.slice(0, 3).map((i: any) => i.country).join(" · ") || "À préciser",                helper: "Pays où le plus de fonds et investisseurs sont référencés." },
      { label: "Nouveaux fonds (7 jours)",       value: s.new_last_7_days > 0 ? `${s.new_last_7_days} nouveau${s.new_last_7_days > 1 ? "x" : ""} fonds` : "Aucune nouveauté récente", helper: "Rythme de détection — un bon indicateur de la vitalité de la veille." },
      { label: "Couverture géographique",        value: `${s.countries_count} pays référencés`,                                                           helper: "Étends ta recherche à de nouvelles zones pour diversifier les pistes." },
      { label: "Confiance des fiches",           value: s.avg_confidence > 0 ? `${s.avg_confidence}% de confiance moyenne` : "À enrichir",               helper: "Les fiches avec un score élevé sont plus fiables pour la prise de décision." },
    ],
  },
  public: {
    heroGradient: "from-primary-950 via-primary-900 to-blue-700",
    heroBadgeBg: "bg-white/10",
    heroBadgeText: "text-white/85",
    badgeLabel: "Financement Public",
    heroTitle: "Veille Financement Public",
    heroSubtitle: "Subventions, appels à projets, concours et prêts correspondant à votre profil et vos zones prioritaires.",
    catalogHref: "/devices",
    catalogLabel: "Explorer les opportunités",
    kpis: (s: any, _pipeline: DevicePipelineEntry[]) => [
      { label: "Opportunités actives",      value: s.total_active.toLocaleString("fr"), sub: `${s.total} au total`,                   icon: CheckCircle, color: "text-green-600",  bg: "bg-green-50" },
      { label: "Nouvelles (7 jours)",       value: s.new_last_7_days.toLocaleString("fr"), sub: "ajoutées récemment",                 icon: TrendingUp,  color: "text-blue-600",  bg: "bg-blue-50" },
      { label: "Clôturent dans 30j",        value: s.closing_soon_30d.toLocaleString("fr"), sub: `dont ${s.closing_soon_7d} dans 7j`, icon: Clock,       color: "text-orange-600", bg: "bg-orange-50" },
      { label: "En attente validation",     value: s.pending_validation.toLocaleString("fr"), sub: `confiance moy. ${s.avg_confidence}%`, icon: AlertTriangle, color: "text-yellow-600", bg: "bg-yellow-50" },
    ],
    marketSignals: (s: any) => [
      { label: "Pays les plus actifs",    value: s.by_country.slice(0, 3).map((i: any) => i.country).join(" · ") || "À préciser",                                                         helper: "Zones où le volume d'opportunités est actuellement le plus fort." },
      { label: "Formats les plus présents", value: s.by_type.slice(0, 3).map((i: any) => DEVICE_TYPE_LABELS[i.type] || i.type).join(" · ") || "À préciser",                              helper: "Types de financement les plus visibles dans la veille récente." },
      { label: "Rythme de détection",     value: s.new_last_7_days > 0 ? `${s.new_last_7_days} nouvelle${s.new_last_7_days > 1 ? "s" : ""} opportunité${s.new_last_7_days > 1 ? "s" : ""} en 7 jours` : "Aucune nouveauté récente", helper: "Pour savoir si la veille accélère ou si elle mérite d'être élargie." },
      { label: "Pression calendrier",     value: s.closing_soon_30d > 0 ? `${s.closing_soon_30d} clôture${s.closing_soon_30d > 1 ? "s" : ""} dans 30 jours` : "Aucune échéance proche", helper: "Un bon repère pour arbitrer entre exploration et exécution." },
    ],
  },
} as const;

const getScopeConfig = (scope: FinancingScope) =>
  scope === "private" ? SCOPE_CONFIG.private : SCOPE_CONFIG.public;

// ── Composant ─────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [stats,           setStats]           = useState<any | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [loading,         setLoading]         = useState(true);
  const [pipelineDevices, setPipelineDevices] = useState<DevicePipelineEntry[]>([]);
  const [scope,           setScope]           = useState<FinancingScope>(null);

  useEffect(() => {
    const savedScope = (localStorage.getItem("kafundo_financing_scope") || null) as FinancingScope;
    setScope(savedScope);

    dashboard.get(savedScope ?? undefined)
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));

    relevance.recommendations({ page_size: 6 })
      .then((data) => setRecommendations(Array.isArray(data?.items) ? data.items : []))
      .catch(() => setRecommendations([]));

    syncWorkspace()
      .catch(() => false)
      .finally(() => setPipelineDevices(listPipelineDevices()));
  }, []);

  // ── Tous les useMemo AVANT les early returns (règle des hooks React) ─────────

  // Top priorités pipeline
  const topPriorities = useMemo(() => {
    return [...pipelineDevices]
      .filter((d) => !["refuse", "non_pertinent", "soumis"].includes(d.pipelineStatus))
      .sort((a, b) => {
        const sd = (PIPELINE_STATUS_ORDER[a.pipelineStatus] ?? 9) - (PIPELINE_STATUS_ORDER[b.pipelineStatus] ?? 9);
        if (sd !== 0) return sd;
        const pd = (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9);
        if (pd !== 0) return pd;
        const aD = a.closeDate ? new Date(a.closeDate).getTime() : Infinity;
        const bD = b.closeDate ? new Date(b.closeDate).getTime() : Infinity;
        return aD - bD;
      })
      .slice(0, 3);
  }, [pipelineDevices]);

  // Devices avec deadline urgente (stats peut être null → optional chaining)
  const urgentDevices = useMemo(() => {
    return (stats?.recent_devices ?? []).filter((d: any) => {
      if (!d.close_date || d.status !== "open") return false;
      const days = Math.ceil((new Date(d.close_date).getTime() - Date.now()) / 86_400_000);
      return days >= 0 && days <= 14;
    });
  }, [stats]);

  // Recommandations à fort potentiel
  const highPotentialRecs = useMemo(() => {
    return recommendations.filter(
      (r) => r.relevance.priority_level === "haute" || r.relevance.priority_level === "élevée",
    );
  }, [recommendations]);

  // Actions recommandées
  const actionItems = useMemo((): ActionItem[] => {
    if (!stats) return [];
    const actions: ActionItem[] = [];

    // 1. Deadline urgente
    if (urgentDevices.length > 0) {
      const d = urgentDevices[0];
      const daysLeft = Math.ceil((new Date(d.close_date).getTime() - Date.now()) / 86_400_000);
      actions.push({
        id: `deadline-${d.id}`,
        icon: Flame,
        iconBg: "bg-orange-100 text-orange-600",
        label: `Candidater à : ${d.title.length > 45 ? d.title.slice(0, 45) + "…" : d.title}`,
        detail: `Deadline dans ${daysLeft} jour${daysLeft > 1 ? "s" : ""} — ne pas attendre`,
        href: `/devices/${d.id}`,
        badge: `J-${daysLeft}`,
        badgeColor: "bg-orange-100 text-orange-700",
      });
    }

    // 2. Top recommandation
    if (recommendations.length > 0) {
      const top = recommendations[0];
      actions.push({
        id: `rec-${top.device.id}`,
        icon: Target,
        iconBg: "bg-emerald-100 text-emerald-600",
        label: `Vérifier éligibilité : ${top.device.title.length > 45 ? top.device.title.slice(0, 45) + "…" : top.device.title}`,
        detail: top.relevance.relevance_label || `Score ${top.relevance.relevance_score}% de compatibilité`,
        href: `/devices/${top.device.id}?from=dashboard`,
        badge: `${top.relevance.relevance_score}%`,
        badgeColor: "bg-emerald-100 text-emerald-700",
      });
    }

    // 3. Deuxième recommandation fort potentiel
    if (highPotentialRecs.length > 1) {
      const r = highPotentialRecs[1];
      actions.push({
        id: `hp-${r.device.id}`,
        icon: Star,
        iconBg: "bg-amber-100 text-amber-600",
        label: `Opportunité à fort potentiel : ${r.device.title.length > 40 ? r.device.title.slice(0, 40) + "…" : r.device.title}`,
        detail: `${r.device.country} · ${r.device.organism}`,
        href: `/devices/${r.device.id}`,
        badge: "Fort potentiel",
        badgeColor: "bg-amber-100 text-amber-700",
      });
    }

    // 4. Compléter profil si peu de résultats
    if (recommendations.length < 3) {
      const extra = Math.max(10, stats.total - recommendations.length);
      actions.push({
        id: "complete-profile",
        icon: Plus,
        iconBg: "bg-primary-100 text-primary-600",
        label: `Débloquer +${extra} opportunités supplémentaires`,
        detail: "Complétez votre profil (secteurs, zones) pour affiner votre veille",
        href: "/profile",
        badge: `+${extra}`,
        badgeColor: "bg-primary-100 text-primary-700",
      });
    }

    return actions.slice(0, 4);
  }, [stats, recommendations, urgentDevices, highPotentialRecs]); // eslint-disable-line

  // ── Early returns (APRÈS tous les hooks) ──────────────────────────────────

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-6 h-6 text-gray-400 animate-spin" />
        </div>
      </AppLayout>
    );
  }

  if (!stats) {
    return (
      <AppLayout>
        <div className="text-center py-20 text-gray-400">Impossible de charger le dashboard</div>
      </AppLayout>
    );
  }

  // ── Calculs non-hook (stats garanti non-null ici) ─────────────────────────

  const cfg           = getScopeConfig(scope);
  const kpis          = cfg.kpis(stats, pipelineDevices);
  const marketSignals = cfg.marketSignals(stats);
  const isPrivate     = scope === "private";

  const devicesWithAmount = stats.recent_devices.filter((d: any) => d.amount_max && d.amount_max > 0);
  const totalPotentialMax = devicesWithAmount.reduce((sum: number, d: any) => sum + d.amount_max, 0);
  const totalPotentialMin = devicesWithAmount.reduce((sum: number, d: any) => sum + (d.amount_max * 0.2), 0);
  const hasPotential = totalPotentialMax > 0;

  // ── Rendu ─────────────────────────────────────────────────────────────────

  return (
    <AppLayout>

      {/* ── Hero banner ──────────────────────────────────────────────────────── */}
      <section className={clsx(
        "mb-6 overflow-hidden rounded-[28px] border border-white/10 px-6 py-6 text-white",
        "bg-gradient-to-br shadow-[0_20px_60px_-30px_rgba(37,99,235,0.45)]",
        cfg.heroGradient,
      )}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <span className={clsx(
              "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-widest",
              cfg.heroBadgeBg, cfg.heroBadgeText,
            )}>
              {isPrivate ? <TrendingUp className="h-3.5 w-3.5" /> : <Building2 className="h-3.5 w-3.5" />}
              {cfg.badgeLabel}
            </span>
            <h1 className="mt-3 text-2xl font-bold tracking-tight text-white md:text-3xl">
              {cfg.heroTitle}
            </h1>
            <p className="mt-2 text-sm leading-6 text-white/75">{cfg.heroSubtitle}</p>
          </div>

          <div className="flex flex-wrap gap-4 lg:shrink-0">
            <div className="rounded-2xl border border-white/15 bg-white/10 px-5 py-3 text-center backdrop-blur-sm">
              <p className="text-2xl font-bold">{stats.total_active.toLocaleString("fr")}</p>
              <p className="mt-0.5 text-[11px] text-white/70">{isPrivate ? "Fonds actifs" : "Opportunités actives"}</p>
            </div>
            <div className="rounded-2xl border border-white/15 bg-white/10 px-5 py-3 text-center backdrop-blur-sm">
              <p className="text-2xl font-bold">{stats.new_last_7_days.toLocaleString("fr")}</p>
              <p className="mt-0.5 text-[11px] text-white/70">Nouveaux (7j)</p>
            </div>
            <div className="rounded-2xl border border-white/15 bg-white/10 px-5 py-3 text-center backdrop-blur-sm">
              <p className="text-2xl font-bold">{stats.countries_count.toLocaleString("fr")}</p>
              <p className="mt-0.5 text-[11px] text-white/70">Pays couverts</p>
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-end">
          <Link
            href={cfg.catalogHref}
            className="inline-flex items-center gap-1.5 rounded-xl border border-white/20 bg-white/10 px-4 py-2 text-xs font-semibold text-white transition hover:bg-white/20"
          >
            {cfg.catalogLabel}
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* BLOC 1 — Opportunités pour vous + À faire maintenant                  */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">

        {/* 💰 Opportunités financières détectées */}
        <div className={clsx(
          "rounded-3xl border p-6",
          isPrivate
            ? "border-violet-200 bg-gradient-to-br from-violet-50 to-indigo-50/50"
            : "border-primary-200 bg-gradient-to-br from-primary-50 to-blue-50/50",
        )}>
          <div className="flex items-center gap-3 mb-5">
            <div className={clsx(
              "flex h-11 w-11 items-center justify-center rounded-2xl",
              isPrivate ? "bg-violet-600" : "bg-primary-600",
            )}>
              <DollarSign className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className={clsx("text-xs font-semibold uppercase tracking-widest", isPrivate ? "text-violet-600" : "text-primary-600")}>
                💰 Opportunités détectées pour vous
              </p>
              <p className="text-xl font-bold text-slate-950">
                {hasPotential
                  ? `${formatEuro(totalPotentialMin)} – ${formatEuro(totalPotentialMax)}`
                  : `${stats.total_active} dispositif${stats.total_active > 1 ? "s" : ""} disponible${stats.total_active > 1 ? "s" : ""}`}
              </p>
              {hasPotential && (
                <p className="text-xs text-slate-500">Potentiel estimé</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            {/* Prioritaires */}
            <div className="rounded-2xl border border-white/70 bg-white/80 px-3 py-3 text-center">
              <Target className={clsx("mx-auto mb-1 h-4 w-4", isPrivate ? "text-violet-500" : "text-primary-500")} />
              <p className="text-xl font-bold text-slate-900">{Math.min(recommendations.length, stats.total_active)}</p>
              <p className="text-[11px] text-slate-500">financements<br />prioritaires</p>
            </div>
            {/* Deadlines */}
            <div className="rounded-2xl border border-white/70 bg-white/80 px-3 py-3 text-center">
              <Clock className="mx-auto mb-1 h-4 w-4 text-orange-500" />
              <p className="text-xl font-bold text-slate-900">{stats.closing_soon_7d || urgentDevices.length}</p>
              <p className="text-[11px] text-slate-500">deadline<br />proche (&lt;7j)</p>
            </div>
            {/* Fort potentiel */}
            <div className="rounded-2xl border border-white/70 bg-white/80 px-3 py-3 text-center">
              <Zap className="mx-auto mb-1 h-4 w-4 text-amber-500" />
              <p className="text-xl font-bold text-slate-900">{highPotentialRecs.length || Math.max(0, Math.floor(stats.total_active * 0.4))}</p>
              <p className="text-[11px] text-slate-500">fort<br />potentiel</p>
            </div>
          </div>

          {/* Lien catalogue */}
          <Link
            href={cfg.catalogHref}
            className={clsx(
              "mt-4 flex w-full items-center justify-center gap-2 rounded-2xl border py-2.5 text-sm font-semibold transition-all hover:opacity-80",
              isPrivate ? "border-violet-300 bg-violet-600 text-white" : "border-primary-300 bg-primary-600 text-white",
            )}
          >
            <Zap className="h-4 w-4" />
            Voir toutes mes opportunités
            <ChevronRight className="h-4 w-4" />
          </Link>
        </div>

        {/* 🚀 À faire maintenant */}
        <div className="card p-5">
          <div className="mb-4 flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white">
              <Zap className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">🚀 Actions recommandées</h2>
              <p className="text-xs text-slate-400">Ce que vous pouvez faire maintenant</p>
            </div>
          </div>

          {actionItems.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-8 text-center">
              <CheckCircle className="mx-auto mb-2 h-6 w-6 text-slate-300" />
              <p className="text-sm font-medium text-slate-600">Tout est à jour</p>
              <p className="mt-1 text-xs text-slate-400">Revenez après la prochaine collecte pour de nouvelles opportunités.</p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {actionItems.map((action) => {
                const Icon = action.icon;
                return (
                  <Link
                    key={action.id}
                    href={action.href}
                    className="flex items-start gap-3 rounded-2xl border border-slate-100 bg-slate-50/60 px-3 py-3 transition-all hover:border-primary-200 hover:bg-primary-50/40 group"
                  >
                    <div className={clsx("flex h-8 w-8 shrink-0 items-center justify-center rounded-xl", action.iconBg)}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-slate-900 group-hover:text-primary-700 line-clamp-1">{action.label}</p>
                      <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">{action.detail}</p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1.5">
                      <span className={clsx("rounded-full px-2 py-0.5 text-[10px] font-bold", action.badgeColor)}>
                        {action.badge}
                      </span>
                      <ArrowRight className="h-3.5 w-3.5 text-slate-300 group-hover:text-primary-400 transition-colors" />
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── KPIs ─────────────────────────────────────────────────────────────── */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {kpis.map(({ label, value, sub, icon: Icon, color, bg }) => (
          <div key={label} className="card p-4">
            <div className="flex items-center gap-3">
              <div className={clsx("rounded-xl p-2.5", bg)}>
                <Icon className={clsx("h-5 w-5", color)} />
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900">{value}</div>
                <div className="text-xs font-medium text-gray-500">{label}</div>
                <div className="text-xs text-gray-400">{sub}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Pipeline priorités ───────────────────────────────────────────────── */}
      {topPriorities.length > 0 && (
        <div className="mb-6">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Flame className="h-4 w-4 text-orange-500" />
              <h2 className="text-sm font-semibold text-gray-900">Tes 3 priorités du moment</h2>
            </div>
            <Link href="/workspace" className="text-xs text-primary-600 hover:underline">
              Voir tout le pipeline
            </Link>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {topPriorities.map((device, idx) => {
              const deadline = device.closeDate ? new Date(device.closeDate).getTime() : null;
              const daysLeft = deadline ? Math.ceil((deadline - Date.now()) / 86_400_000) : null;
              const urgent = daysLeft !== null && daysLeft <= 14;
              return (
                <Link
                  key={device.id}
                  href={`/devices/${device.id}`}
                  className={clsx(
                    "group block rounded-2xl border px-4 py-4 transition-colors hover:border-primary-200 hover:bg-primary-50/40",
                    urgent ? "border-orange-200 bg-orange-50/50" : "border-slate-200 bg-white",
                  )}
                >
                  <div className="mb-2 flex items-center gap-2">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-bold text-primary-700">{idx + 1}</span>
                    <span className={clsx("rounded-full px-2 py-0.5 text-[10px] font-semibold", PIPELINE_STATUS_COLORS[device.pipelineStatus])}>
                      {PIPELINE_STATUS_LABELS[device.pipelineStatus]}
                    </span>
                    {urgent && daysLeft !== null && (
                      <span className="ml-auto shrink-0 rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-semibold text-orange-700">⚡ J-{daysLeft}</span>
                    )}
                  </div>
                  <p className="line-clamp-2 text-sm font-semibold text-slate-900 group-hover:text-primary-700">{device.title}</p>
                  <p className="mt-1 line-clamp-1 text-xs text-slate-500">{device.organism} · {device.country}</p>
                  {device.note && <p className="mt-2 line-clamp-1 text-xs italic text-slate-400">"{device.note}"</p>}
                  <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
                    {device.closeDate && !urgent ? <span>{formatDateRelative(device.closeDate)}</span> : <span />}
                    <ArrowRight className="h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* BLOC 2 — Recommandations (enhanced) + Dernières opportunités           */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">

        {/* Recommandées — version enrichie */}
        <div className="card p-4">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-gray-700">Recommandées pour vous</h2>
              <p className="mt-0.5 text-xs text-gray-400">
                {isPrivate ? "Fonds sélectionnés selon votre profil investisseur." : "Opportunités triées par pertinence."}
              </p>
            </div>
            <Link href="/recommendations" className="text-xs text-primary-600 hover:underline">Voir plus</Link>
          </div>

          {recommendations.length === 0 ? (
            /* Empty state amélioré */
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-8 text-center">
              <Sparkles className="mx-auto mb-2 h-6 w-6 text-slate-300" />
              <p className="text-sm font-medium text-slate-600">Complète ton profil</p>
              <p className="mt-1 text-xs text-slate-400">
                {isPrivate ? "Renseigne tes secteurs et zones cibles pour voir les fonds recommandés." : "Renseigne tes secteurs et pays pour voir des opportunités ciblées."}
              </p>
              {stats.total > 0 && (
                <div className="mt-4 rounded-xl border border-primary-200 bg-primary-50 px-4 py-3">
                  <p className="text-sm font-semibold text-primary-800">
                    🔍 {stats.total} opportunités disponibles dans votre zone
                  </p>
                  <p className="mt-1 text-xs text-primary-600">
                    → Débloquez-les en affinant votre profil
                  </p>
                </div>
              )}
              <Link href="/profile" className="mt-3 inline-block text-xs font-semibold text-primary-600 hover:underline">
                Configurer mon profil →
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {recommendations.slice(0, 4).map((item) => {
                const score = item.relevance.relevance_score;
                const amountMax = item.device.amount_max;
                const amountMin = item.device.amount_min;
                const hasAmount = amountMax && amountMax > 0;
                const timeEst = TIME_ESTIMATES[item.device.device_type] || "Voir fiche";

                return (
                  <Link
                    key={item.device.id}
                    href={`/devices/${item.device.id}`}
                    className="block rounded-2xl border border-slate-200 px-4 py-4 transition-colors hover:border-primary-200 hover:bg-primary-50/30 group"
                  >
                    {/* Header */}
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="line-clamp-2 text-sm font-semibold text-slate-900 group-hover:text-primary-700">
                          {item.device.title}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          {item.device.organism} · {item.device.country}
                        </p>
                      </div>
                      <span className={clsx(
                        "shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold",
                        isPrivate ? "bg-violet-100 text-violet-700" : "bg-emerald-100 text-emerald-700",
                      )}>
                        {item.relevance.priority_level || "—"}
                      </span>
                    </div>

                    {/* Métriques IA */}
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px]">
                      {/* Score */}
                      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-700">
                        <Target className="h-3 w-3" />
                        Score : {score}%
                      </span>
                      {/* Montant */}
                      {hasAmount && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2.5 py-1 font-semibold text-green-700">
                          <DollarSign className="h-3 w-3" />
                          {amountMin && amountMin > 0 ? `${formatEuro(amountMin)} – ${formatEuro(amountMax)}` : `Jusqu'à ${formatEuro(amountMax)}`}
                        </span>
                      )}
                      {/* Temps */}
                      <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-1 font-semibold text-blue-700">
                        <Timer className="h-3 w-3" />
                        Dossier : {timeEst}
                      </span>
                    </div>

                    {/* IA Raisons */}
                    {item.relevance.reason_texts?.length > 0 && (
                      <div className="mt-3 rounded-xl border border-slate-100 bg-slate-50/80 px-3 py-2.5">
                        <div className="flex items-center gap-1.5 mb-1.5">
                          <Bot className="h-3.5 w-3.5 text-primary-500 shrink-0" />
                          <p className="text-[11px] font-semibold text-primary-700">Kafundo recommande car :</p>
                        </div>
                        <ul className="space-y-1">
                          {item.relevance.reason_texts.slice(0, 2).map((reason, i) => (
                            <li key={i} className="flex items-start gap-1.5 text-xs text-slate-600">
                              <span className="mt-0.5 text-primary-400 shrink-0">•</span>
                              {reason}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </Link>
                );
              })}

              {/* "Opportunités à explorer" si peu de recs */}
              {recommendations.length < 3 && stats.total > recommendations.length && (
                <Link
                  href={cfg.catalogHref}
                  className="flex items-center justify-between rounded-2xl border border-dashed border-primary-300 bg-primary-50/60 px-4 py-3 transition-colors hover:bg-primary-50"
                >
                  <div>
                    <p className="text-sm font-semibold text-primary-800">
                      🔍 {stats.total} opportunités supplémentaires disponibles
                    </p>
                    <p className="text-xs text-primary-600">→ Élargissez votre profil pour en débloquer davantage</p>
                  </div>
                  <ChevronRight className="h-4 w-4 text-primary-400 shrink-0" />
                </Link>
              )}
            </div>
          )}
        </div>

        {/* Dernières opportunités dans vos pays */}
        <div className="card p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-gray-700">
                {isPrivate ? "Derniers fonds détectés" : "Dernières opportunités"}
              </h2>
              <p className="mt-0.5 text-xs text-gray-400">
                {isPrivate ? "Les fonds les plus récemment ajoutés dans vos zones cibles." : "Les dispositifs les plus récemment détectés dans vos pays."}
              </p>
            </div>
            <Link href={cfg.catalogHref} className="text-xs text-primary-600 hover:underline">Tout voir</Link>
          </div>

          {stats.recent_devices.length === 0 ? (
            <div className="flex h-48 flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-slate-200 bg-slate-50/70">
              <Globe className="h-6 w-6 text-slate-300" />
              <p className="text-sm text-slate-500">Aucune opportunité trouvée</p>
              <p className="text-xs text-slate-400">Essayez d'élargir vos pays dans votre profil.</p>
              <Link href="/profile" className="mt-1 text-xs font-semibold text-primary-600 hover:underline">
                Modifier mon profil →
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {stats.recent_devices.slice(0, 5).map((device: any) => {
                const hasAmt = device.amount_max && device.amount_max > 0;
                return (
                  <Link
                    key={device.id}
                    href={`/devices/${device.id}`}
                    className="flex items-start gap-3 rounded-xl border border-slate-100 bg-slate-50/60 px-3 py-2.5 transition-colors hover:border-primary-200 hover:bg-primary-50/40 group"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="line-clamp-1 text-sm font-medium text-slate-900 group-hover:text-primary-700">{device.title}</p>
                      <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                        <span>{device.country}</span>
                        {hasAmt && (
                          <>
                            <span className="text-slate-300">·</span>
                            <span className="font-medium text-green-700">{formatEuro(device.amount_max)}</span>
                          </>
                        )}
                        {device.close_date && (
                          <>
                            <span className="text-slate-300">·</span>
                            <span className={clsx(
                              "font-medium",
                              new Date(device.close_date) <= new Date(Date.now() + 7 * 86400000) ? "text-orange-600" : "text-slate-400",
                            )}>
                              {new Date(device.close_date).toLocaleDateString("fr-FR", { day: "numeric", month: "short" })}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <span className={clsx(
                        "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                        device.status === "open"
                          ? isPrivate ? "bg-violet-100 text-violet-700" : "bg-emerald-100 text-emerald-700"
                          : "bg-slate-100 text-slate-500",
                      )}>
                        {device.status === "open" ? "Ouvert" : device.status}
                      </span>
                      <ExternalLink className="h-3 w-3 text-slate-300 group-hover:text-primary-400 transition-colors" />
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Signaux marché ──────────────────────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-700">
              {isPrivate ? "Concentrer ta prospection" : "Où concentrer ta veille"}
            </h2>
            <p className="mt-1 text-xs text-gray-400">
              {isPrivate ? "Signaux clés pour orienter ta recherche d'investisseurs." : "Une lecture simple du marché pour décider plus vite."}
            </p>
          </div>
          <Link href={cfg.catalogHref} className="text-xs text-primary-600 hover:underline">{cfg.catalogLabel}</Link>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {marketSignals.map((signal) => (
            <div key={signal.label} className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">{signal.label}</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">{signal.value}</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">{signal.helper}</p>
            </div>
          ))}
        </div>
      </div>

    </AppLayout>
  );
}
