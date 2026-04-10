import Link from "next/link";
import { Calendar, MapPin, Building2, ExternalLink, TrendingUp } from "lucide-react";
import { Device, DEVICE_TYPE_LABELS, DEVICE_TYPE_COLORS, STATUS_LABELS, STATUS_COLORS } from "@/lib/types";
import { formatAmount, formatDate, daysUntil, getDeviceNatureBanner, sanitizeDisplayText } from "@/lib/utils";
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
    <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-600">{label}</p>
      <p className="mt-1 whitespace-pre-line text-xs leading-relaxed text-slate-700 line-clamp-3">{cleaned}</p>
    </div>
  );
}

function HighlightPill({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "accent";
}) {
  return (
    <div
      className={clsx(
        "rounded-2xl border px-3 py-2",
        tone === "accent" ? "border-primary-200 bg-primary-50/70" : "border-slate-200 bg-white/80",
      )}
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</p>
      <p className={clsx("mt-1 text-xs font-semibold", tone === "accent" ? "text-primary-700" : "text-slate-800")}>{value}</p>
    </div>
  );
}

export default function DeviceCard({ device, selected = false, onSelect }: Props) {
  const daysLeft = device.close_date ? daysUntil(device.close_date) : null;
  const isClosingSoon = daysLeft !== null && daysLeft <= 30 && daysLeft >= 0;
  const natureBanner = getDeviceNatureBanner(device);
  const presentation = device.short_description || device.auto_summary;
  const conditions = device.eligibility_criteria;
  const project = device.eligible_expenses || device.specific_conditions;
  const practicalInfo = device.required_documents;
  const bannerTone =
    natureBanner?.kind === "open_call"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : natureBanner?.kind === "recurring"
        ? "border-blue-200 bg-blue-50 text-blue-800"
        : natureBanner?.kind === "institutional_project"
          ? "border-violet-200 bg-violet-50 text-violet-800"
          : "border-amber-200 bg-amber-50 text-amber-800";

  return (
    <div
      className={clsx(
        "card overflow-hidden p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg",
        selected ? "ring-2 ring-primary-400 bg-primary-50/40" : onSelect && "hover:ring-1 hover:ring-primary-200",
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
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <span className={clsx("badge flex items-center gap-1 text-xs", DEVICE_TYPE_COLORS[device.device_type] || "bg-gray-100 text-gray-600")}>
              {device.device_type === "investissement" && <TrendingUp className="h-3 w-3" />}
              {DEVICE_TYPE_LABELS[device.device_type] || device.device_type}
            </span>
            <span className={clsx("badge text-xs", STATUS_COLORS[device.status])}>
              {STATUS_LABELS[device.status] || device.status}
            </span>
            {isClosingSoon && daysLeft !== null && (
              <span className="badge bg-orange-100 text-xs text-orange-700">J-{daysLeft}</span>
            )}
          </div>

          <Link href={`/devices/${device.id}`} className="group block">
            <h3 className="line-clamp-2 text-base font-semibold leading-snug text-slate-900 group-hover:text-primary-700">
              {device.title}
            </h3>
          </Link>

          {natureBanner && (
            <div className={clsx("mt-3 rounded-2xl border px-3 py-2.5", bannerTone)}>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em]">{natureBanner.label}</p>
              <p className="mt-1 text-xs leading-relaxed opacity-90">{natureBanner.detail}</p>
            </div>
          )}

          <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
            <HighlightPill label="Type" value={DEVICE_TYPE_LABELS[device.device_type] || device.device_type} />
            <HighlightPill
              label="Clôture"
              value={device.close_date ? formatDate(device.close_date) : "Non communiquée"}
              tone={device.close_date ? "accent" : "default"}
            />
            <HighlightPill
              label="Portée"
              value={[device.country, device.region].filter(Boolean).join(" · ") || "Non renseignée"}
            />
            <HighlightPill
              label="Montant"
              value={device.amount_max ? formatAmount(device.amount_max, device.currency) : "À confirmer"}
              tone={device.amount_max ? "accent" : "default"}
            />
          </div>

          <div className="mt-3 grid gap-2">
            <EditorialSnippet label="Présentation" content={presentation} />
            <EditorialSnippet label="Conditions" content={conditions} />
            <EditorialSnippet label="Projet" content={project} />
            <EditorialSnippet label="Infos pratiques" content={practicalInfo} />
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
            <span className="flex items-center gap-1">
              <Building2 className="h-3 w-3" />
              {device.organism}
            </span>
            <span className="flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {device.country}
              {device.region && ` · ${device.region}`}
            </span>
            <span
              className={clsx(
                "flex items-center gap-1",
                device.close_date ? isClosingSoon && "font-medium text-orange-600" : "italic text-slate-400",
              )}
            >
              <Calendar className="h-3 w-3" />
              {device.close_date ? formatDate(device.close_date) : "Clôture non renseignée"}
            </span>
            {device.is_recurring && (
              <span className="rounded-full bg-blue-50 px-2 py-0.5 text-blue-700">Récurrent</span>
            )}
          </div>
        </div>

        {device.amount_max && (
          <div className="flex-shrink-0 rounded-2xl border border-primary-100 bg-primary-50/70 px-3 py-2 text-right shadow-sm">
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-500">Montant</div>
            <div className="mt-1 text-sm font-bold text-slate-900">
              {formatAmount(device.amount_max, device.currency)}
            </div>
            {device.amount_min && device.amount_min !== device.amount_max && (
              <div className="text-xs text-slate-500">min {formatAmount(device.amount_min, device.currency)}</div>
            )}
            {device.funding_rate && <div className="text-xs text-slate-500">{device.funding_rate}%</div>}
          </div>
        )}
      </div>

      <div className={clsx("mt-4 flex items-center justify-between border-t border-slate-100 pt-3", onSelect && "ml-7")}>
        <div className="flex flex-wrap gap-1">
          {(device.sectors || []).slice(0, 3).map((sector) => (
            <span key={sector} className="badge bg-gray-100 text-xs capitalize text-gray-600">
              {sector}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <div className="flex items-center gap-1">
            <div
              className={clsx(
                "h-1.5 w-1.5 rounded-full",
                device.confidence_score >= 70 ? "bg-green-400" : device.confidence_score >= 40 ? "bg-yellow-400" : "bg-red-400",
              )}
            />
            {device.confidence_score}%
          </div>
          <a href={device.source_url} target="_blank" rel="noopener noreferrer" className="hover:text-primary-600">
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>
    </div>
  );
}
