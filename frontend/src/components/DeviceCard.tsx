"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Calendar, MapPin, Building2, ExternalLink, TrendingUp, Heart, Flag } from "lucide-react";
import { Device, DEVICE_TYPE_LABELS, DEVICE_TYPE_COLORS, STATUS_LABELS, STATUS_COLORS } from "@/lib/types";
import { formatAmount, formatDate, daysUntil, getDeviceNatureBanner, sanitizeDisplayText } from "@/lib/utils";
import { getPipelineDevice, isFavoriteDevice, toggleFavoriteDevice, type DevicePipelineStatus } from "@/lib/workspace";
import clsx from "clsx";

interface Props {
  device: Device;
  selected?: boolean;
  onSelect?: (id: string) => void;
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

export default function DeviceCard({ device, selected = false, onSelect }: Props) {
  const [favorite, setFavorite] = useState(false);
  const [pipelineStatus, setPipelineStatus] = useState<DevicePipelineStatus | null>(null);
  const daysLeft = device.close_date ? daysUntil(device.close_date) : null;
  const isClosingSoon = daysLeft !== null && daysLeft <= 30 && daysLeft >= 0;
  const natureBanner = getDeviceNatureBanner(device);
  const PIPELINE_LABELS: Record<DevicePipelineStatus, string> = {
    a_etudier: "A etudier",
    candidature_en_cours: "Candidature en cours",
    non_pertinent: "Non pertinent",
  };
  const PIPELINE_COLORS: Record<DevicePipelineStatus, string> = {
    a_etudier: "bg-amber-100 text-amber-700",
    candidature_en_cours: "bg-blue-100 text-blue-700",
    non_pertinent: "bg-slate-200 text-slate-600",
  };
  const snippets = [
    { label: "Présentation", content: device.short_description || device.auto_summary },
    { label: "Conditions", content: device.eligibility_criteria },
    { label: "Montant", content: device.funding_details },
    {
      label: "Calendrier",
      content: device.close_date
        ? `Clôture le ${formatDate(device.close_date)}.`
        : device.is_recurring
          ? "Dispositif récurrent sans date de clôture unique."
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
          <label className="flex flex-shrink-0 items-start cursor-pointer pt-0.5">
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
            <span className={clsx("badge flex items-center gap-1 text-xs", DEVICE_TYPE_COLORS[device.device_type] || "bg-gray-100 text-gray-600")}>
              {device.device_type === "investissement" && <TrendingUp className="h-3 w-3" />}
              {DEVICE_TYPE_LABELS[device.device_type] || device.device_type}
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
            <button
              type="button"
              onClick={handleToggleFavorite}
              className={clsx(
                "ml-auto inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-colors",
                favorite
                  ? "bg-rose-100 text-rose-700 hover:bg-rose-200"
                  : "bg-slate-100 text-slate-500 hover:bg-slate-200 hover:text-slate-700"
              )}
              title={favorite ? "Retirer des favoris" : "Ajouter aux favoris"}
            >
              <Heart className={clsx("h-3.5 w-3.5", favorite && "fill-current")} />
              {favorite ? "Favori" : "Favori"}
            </button>
          </div>

          <div className="mt-3 flex items-start justify-between gap-4">
            <div className="min-w-0">
              <Link href={`/devices/${device.id}`} className="group block">
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
                  {device.close_date ? formatDate(device.close_date) : "Clôture non renseignée"}
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
            <MetaLine label="Type" value={DEVICE_TYPE_LABELS[device.device_type] || device.device_type} />
            <MetaLine label="Clôture" value={device.close_date ? formatDate(device.close_date) : "Non communiquée"} emphasized={Boolean(device.close_date)} />
            <MetaLine label="Portée" value={[device.country, device.region].filter(Boolean).join(" · ") || "Non renseignée"} />
            <MetaLine label="Montant" value={device.amount_max ? formatAmount(device.amount_max, device.currency) : "À confirmer"} emphasized={Boolean(device.amount_max)} />
          </div>

          <div className="mt-3 space-y-0">
            {snippets.length ? (
              snippets.map((item) => <EditorialSnippet key={item.label} label={item.label} content={item.content} />)
            ) : (
              <div className="border-t border-slate-100 pt-3">
                <p className="text-sm leading-6 text-slate-500">
                  La fiche contient encore peu d’informations éditoriales. Ouvre la source officielle pour consulter le détail complet.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

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
