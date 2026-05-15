"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Calendar, MapPin, Building2, ExternalLink, TrendingUp, Heart, Flag, ThumbsUp, ThumbsDown, AlertCircle } from "lucide-react";
import clsx from "clsx";

import { Device, DEVICE_TYPE_COLORS, STATUS_LABELS, STATUS_COLORS } from "@/lib/types";
import { getUserDeviceTypeMeta } from "@/lib/deviceTypes";
import { formatAmount, formatDate, daysUntil, getAiReadinessMeta, getDeviceNatureBanner, sanitizeDisplayText } from "@/lib/utils";
import { getPipelineDevice, isFavoriteDevice, toggleFavoriteDevice, type DevicePipelineStatus } from "@/lib/workspace";

interface Props {
  device: Device;
  selected?: boolean;
  onSelect?: (id: string) => void;
  /** Paramètre ?from= ajouté aux liens vers la fiche (ex: "recommendations", "match") */
  fromParam?: string;
}

function EditorialSnippet({ label, content }: { label: string; content: string | null | undefined }) {
  const cleaned = sanitizeDisplayText(content);
  if (!cleaned) {
    return null;
  }

  return (
    <div className="border-t border-slate-100 pt-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-600">{label}</p>
      <p className="mt-2 line-clamp-3 whitespace-pre-line text-sm leading-6 text-slate-700">{cleaned}</p>
    </div>
  );
}

function MetaLine({ label, value, emphasized = false }: { label: string; value: string; emphasized?: boolean }) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</p>
      <p className={clsx("mt-1 break-words text-sm font-medium leading-5", emphasized ? "text-primary-700" : "text-slate-800")}>
        {value}
      </p>
    </div>
  );
}

const GO_NO_GO_CONFIG = {
  go: {
    label: "Bonne opportunité",
    cls: "bg-emerald-100 text-emerald-700 border-emerald-200",
    Icon: ThumbsUp,
  },
  no_go: {
    label: "Peu recommandé",
    cls: "bg-red-100 text-red-600 border-red-200",
    Icon: ThumbsDown,
  },
  a_verifier: {
    label: "À vérifier",
    cls: "bg-amber-100 text-amber-700 border-amber-200",
    Icon: AlertCircle,
  },
} as const;

export default function DeviceCard({ device, selected = false, onSelect, fromParam }: Props) {
  const [favorite, setFavorite] = useState(false);
  const [pipelineStatus, setPipelineStatus] = useState<DevicePipelineStatus | null>(null);
  const daysLeft = device.close_date ? daysUntil(device.close_date) : null;
  const isClosingSoon = daysLeft !== null && daysLeft <= 30 && daysLeft >= 0;
  const natureBanner = getDeviceNatureBanner(device);
  const aiReadiness = getAiReadinessMeta(device);
  const typeMeta = getUserDeviceTypeMeta(device.device_type);
  const smartHint = isClosingSoon
    ? "Attention : deadline proche. Priorise cette opportunité si elle correspond à ton projet."
    : device.relevance_label
      ? device.decision_hint || "Conseil : regarde pourquoi cette opportunité ressort pour ton profil."
      : device.ai_readiness_label === "pret_pour_recommandation_ia"
        ? "Conseil : très bonne opportunité pour ton profil. Ajoute-la à ton suivi."
        : device.amount_max
          ? "Astuce : financement chiffré. Compare-le avec tes besoins avant de candidater."
          : "Astuce : ajoute-la à ton suivi pour la comparer plus tard.";

  const PIPELINE_LABELS: Record<DevicePipelineStatus, string> = {
    a_etudier: "A étudier",
    interessant: "Intéressant",
    candidature_en_cours: "Candidature en cours",
    soumis: "Soumis",
    refuse: "Refusé",
    non_pertinent: "Non pertinent",
  };

  const PIPELINE_COLORS: Record<DevicePipelineStatus, string> = {
    a_etudier: "bg-amber-100 text-amber-700",
    interessant: "bg-emerald-100 text-emerald-700",
    candidature_en_cours: "bg-blue-100 text-blue-700",
    soumis: "bg-indigo-100 text-indigo-700",
    refuse: "bg-red-100 text-red-700",
    non_pertinent: "bg-slate-200 text-slate-600",
  };

  const snippets = [
    { label: "Présentation", content: device.short_description || device.auto_summary },
    { label: "Conditions", content: device.eligibility_criteria },
    { label: "Montant", content: device.funding_details },
    {
      label: "Calendrier",
      content: device.close_date
        ? `Date limite : ${formatDate(device.close_date)}.`
        : device.is_recurring
          ? "Financement récurrent sans date limite unique."
          : null,
    },
    { label: "Projet", content: device.eligible_expenses || device.specific_conditions },
    { label: "Infos pratiques", content: device.required_documents },
  ]
    .filter((item) => sanitizeDisplayText(item.content))
    .slice(0, 2);

  useEffect(() => {
    setFavorite(isFavoriteDevice(device.id));
    setPipelineStatus(getPipelineDevice(device.id)?.pipelineStatus || null);
  }, [device.id]);

  const handleToggleFavorite = () => {
    const nextFavorite = toggleFavoriteDevice({
      id: device.id,
      title: device.title,
      organism: device.organism,
      country: device.country,
      region: device.region,
      deviceType: device.device_type,
      status: device.status,
      closeDate: device.close_date,
      amountMax: device.amount_max,
      currency: device.currency,
      sourceUrl: device.source_url,
    });
    setFavorite(nextFavorite);
  };

  return (
    <div
      className={clsx(
        "overflow-hidden rounded-[26px] border border-slate-200 bg-white p-4 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.35)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_20px_50px_-26px_rgba(37,99,235,0.24)]",
        selected ? "ring-2 ring-primary-400 bg-primary-50/30" : onSelect && "hover:ring-1 hover:ring-primary-200",
      )}
    >
      <div className="flex items-start gap-3">
        {onSelect && (
          <label className="flex flex-shrink-0 cursor-pointer items-start pt-0.5">
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onSelect(device.id)}
              className="h-4 w-4 cursor-pointer rounded border-gray-300 accent-primary-600"
            />
          </label>
        )}

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={clsx("badge flex items-center gap-1 text-xs", typeMeta.color || DEVICE_TYPE_COLORS[device.device_type] || "bg-gray-100 text-gray-600")} title={typeMeta.short}>
              {device.device_type === "investissement" && <TrendingUp className="h-3 w-3" />}
              {typeMeta.label}
            </span>
            <span className={clsx("badge text-xs", STATUS_COLORS[device.status])}>
              {STATUS_LABELS[device.status] || device.status}
            </span>
            {pipelineStatus && (
              <span className={clsx("badge flex items-center gap-1 text-xs", PIPELINE_COLORS[pipelineStatus])}>
                <Flag className="h-3 w-3" />
                {PIPELINE_LABELS[pipelineStatus]}
              </span>
            )}
            {isClosingSoon && daysLeft !== null && <span className="badge bg-orange-100 text-xs text-orange-700">J-{daysLeft}</span>}
            <span className={clsx("badge border text-xs", aiReadiness.className)} title={aiReadiness.detail}>
              {aiReadiness.label}
            </span>
            {device.decision_analysis && (() => {
              const cfg = GO_NO_GO_CONFIG[device.decision_analysis.go_no_go] ?? GO_NO_GO_CONFIG.a_verifier;
              const { Icon } = cfg;
              return (
                <span
                  className={clsx("badge flex items-center gap-1 border text-xs", cfg.cls)}
                  title={`Analyse IA · ${device.decision_analysis.recommended_action || ""}`}
                >
                  <Icon className="h-3 w-3" />
                  {cfg.label}
                </span>
              );
            })()}
            <button
              type="button"
              onClick={handleToggleFavorite}
              className={clsx(
                "ml-auto inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-colors",
                favorite ? "bg-rose-100 text-rose-700 hover:bg-rose-200" : "bg-slate-100 text-slate-500 hover:bg-slate-200 hover:text-slate-700",
              )}
              title={favorite ? "Retirer des favoris" : "Ajouter aux favoris"}
            >
              <Heart className={clsx("h-3.5 w-3.5", favorite && "fill-current")} />
              Favori
            </button>
          </div>

          <div className="mt-3 flex items-start justify-between gap-4">
            <div className="min-w-0">
              <Link href={`/devices/${device.id}${fromParam ? `?from=${fromParam}` : ""}`} className="group block">
                <h3 className="line-clamp-3 text-[1.45rem] font-semibold leading-[1.22] tracking-[-0.02em] text-slate-950 group-hover:text-primary-700">
                  {device.title}
                </h3>
              </Link>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-500">
                <span className="flex items-center gap-1.5">
                  <Building2 className="h-3.5 w-3.5" />
                  {device.organism}
                </span>
                <span className="flex items-center gap-1.5">
                  <MapPin className="h-3.5 w-3.5" />
                  {[device.country, device.region].filter(Boolean).join(" · ") || "Portée non renseignée"}
                </span>
                <span className={clsx("flex items-center gap-1.5", device.close_date ? isClosingSoon && "font-medium text-orange-600" : "italic text-slate-400")}>
                  <Calendar className="h-3.5 w-3.5" />
                  {device.close_date ? formatDate(device.close_date) : natureBanner?.label || "Date non communiquée"}
                </span>
              </div>
            </div>

            {device.amount_max && (
              <div className="hidden rounded-2xl bg-slate-950 px-4 py-3 text-right text-white shadow-sm sm:block">
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/60">Jusqu'à</div>
                <div className="mt-1 text-lg font-semibold leading-none">{formatAmount(device.amount_max, device.currency)}</div>
                {device.amount_min && device.amount_min !== device.amount_max && (
                  <div className="mt-1 text-xs text-white/70">min {formatAmount(device.amount_min, device.currency)}</div>
                )}
              </div>
            )}
          </div>

          {natureBanner && (
            <div className="mt-4 rounded-2xl border border-primary-100/80 bg-primary-50/50 px-4 py-2.5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-primary-700">{natureBanner.label}</p>
              <p className="mt-1 line-clamp-2 text-sm leading-6 text-primary-800/90">{natureBanner.detail}</p>
            </div>
          )}

          <div className="mt-4 grid grid-cols-2 gap-x-5 gap-y-3 border-t border-slate-100 pt-3 sm:grid-cols-4">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Type</p>
              <p className="mt-1 break-words text-sm font-semibold leading-5 text-slate-900">{typeMeta.label}</p>
              <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{typeMeta.short}</p>
            </div>
            <MetaLine label="Clôture" value={device.close_date ? formatDate(device.close_date) : natureBanner?.label || "Date non communiquée"} emphasized={Boolean(device.close_date)} />
            <MetaLine label="Portée" value={[device.country, device.region].filter(Boolean).join(" · ") || "Non renseignée"} />
            <MetaLine label="Montant" value={device.amount_max ? formatAmount(device.amount_max, device.currency) : "À confirmer"} emphasized={Boolean(device.amount_max)} />
          </div>

          {device.relevance_label && (
            <div className="mt-3 rounded-2xl border border-emerald-200 bg-emerald-50/70 px-4 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-700">Pourquoi elle ressort</p>
              <p className="mt-1 text-sm font-semibold leading-6 text-emerald-900">{device.relevance_label}</p>
              {device.relevance_reasons?.length ? (
                <p className="mt-2 text-sm leading-6 text-emerald-800">{device.relevance_reasons.slice(0, 2).join(" ")}</p>
              ) : null}
            </div>
          )}

          {device.ai_readiness_label && device.ai_readiness_label !== "pret_pour_recommandation_ia" && (
            <div className={clsx("mt-3 rounded-2xl border px-4 py-2.5", aiReadiness.className)}>
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em]">{aiReadiness.label}</p>
              <p className="mt-1 line-clamp-2 text-sm leading-6">{aiReadiness.detail}</p>
            </div>
          )}

          <div className={clsx("mt-3 rounded-2xl border px-4 py-2.5 text-sm leading-6", isClosingSoon ? "border-orange-200 bg-orange-50 text-orange-800" : "border-slate-200 bg-slate-50 text-slate-600")}>
            <p className="font-medium text-slate-800">{typeMeta.decision}</p>
            <p className="mt-1 text-slate-600">{smartHint}</p>
          </div>

          <div className="mt-3 space-y-0">
            {snippets.length ? (
              snippets.map((item) => <EditorialSnippet key={item.label} label={item.label} content={item.content} />)
            ) : (
              <div className="border-t border-slate-100 pt-3">
                <p className="text-sm leading-6 text-slate-500">
                  Cette opportunité contient encore peu d'informations éditoriales. Ouvre la source officielle pour consulter le détail complet.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {device.decision_analysis && (() => {
        const analysis = device.decision_analysis;
        const cfg = GO_NO_GO_CONFIG[analysis.go_no_go] ?? GO_NO_GO_CONFIG.a_verifier;
        const { Icon } = cfg;
        const hint = analysis.recommended_action || analysis.why_interesting;
        return (
          <div className={clsx("mt-3 rounded-2xl border px-4 py-3", cfg.cls)}>
            <div className="flex items-center gap-1.5 mb-1">
              <Icon className="h-3.5 w-3.5 flex-shrink-0" />
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em]">
                Avis IA · {cfg.label}
                {analysis.recommended_priority === "haute" && " · Priorité haute"}
              </p>
            </div>
            {hint && <p className="text-xs leading-5 opacity-90">{hint}</p>}
            {(analysis.eligibility_score !== undefined || analysis.strategic_interest !== undefined) && (
              <div className="mt-2 flex items-center gap-3 text-[10px] opacity-75">
                {analysis.eligibility_score !== undefined && (
                  <span>Éligibilité {analysis.eligibility_score}%</span>
                )}
                {analysis.strategic_interest !== undefined && (
                  <span>Intérêt {analysis.strategic_interest}%</span>
                )}
                {analysis.effort_level && (
                  <span>Effort {analysis.effort_level}</span>
                )}
              </div>
            )}
          </div>
        );
      })()}

      <div className={clsx("mt-4 flex items-center justify-between border-t border-slate-100 pt-3", onSelect && "ml-7")}>
        <div className="flex flex-wrap gap-1.5">
          {(device.sectors || []).slice(0, 3).map((sector) => (
            <span key={sector} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs capitalize text-slate-600">
              {sector}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <div className="flex items-center gap-1.5">
            <div
              className={clsx(
                "h-1.5 w-1.5 rounded-full",
                device.confidence_score >= 70 ? "bg-green-400" : device.confidence_score >= 40 ? "bg-yellow-400" : "bg-red-400",
              )}
            />
            {device.confidence_score}%
          </div>
          <a href={device.source_url} target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-primary-600">
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>
    </div>
  );
}
