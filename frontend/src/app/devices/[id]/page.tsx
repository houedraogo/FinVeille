"use client";

import { useEffect, useState, type ElementType, type ReactNode } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import AppLayout from "@/components/AppLayout";
import DeviceCard from "@/components/DeviceCard";
import { devices } from "@/lib/api";
import { canModerateDevices, getCurrentRole, type AppRole } from "@/lib/auth";
import { Device, DEVICE_TYPE_LABELS, STATUS_LABELS } from "@/lib/types";
import { formatAmount, formatDate, formatDateRelative, daysUntil, getDeviceNatureBanner, sanitizeDisplayText } from "@/lib/utils";
import {
  getPipelineDevice,
  isFavoriteDevice,
  removePipelineDevice,
  savePipelineDevice,
  toggleFavoriteDevice,
  type DevicePipelineStatus,
} from "@/lib/workspace";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Banknote,
  Building2,
  Calendar,
  CheckCircle,
  Clock,
  ExternalLink,
  FileText,
  History,
  Info,
  MapPin,
  Percent,
  RefreshCw,
  Share2,
  ShieldCheck,
  Sparkles,
  Tag,
  Trash2,
  Users,
  Heart,
  Flag,
  StickyNote,
  XCircle,
} from "lucide-react";
import clsx from "clsx";

const TYPE_HERO: Record<string, { from: string; to: string }> = {
  subvention: { from: "from-emerald-700", to: "to-emerald-500" },
  pret: { from: "from-blue-700", to: "to-blue-500" },
  avance_remboursable: { from: "from-cyan-700", to: "to-cyan-500" },
  garantie: { from: "from-violet-700", to: "to-violet-500" },
  credit_impot: { from: "from-orange-600", to: "to-amber-500" },
  exoneration: { from: "from-yellow-600", to: "to-yellow-400" },
  aap: { from: "from-rose-700", to: "to-rose-500" },
  ami: { from: "from-pink-700", to: "to-pink-500" },
  accompagnement: { from: "from-teal-700", to: "to-teal-500" },
  concours: { from: "from-amber-700", to: "to-amber-500" },
  investissement: { from: "from-indigo-700", to: "to-indigo-500" },
  autre: { from: "from-slate-700", to: "to-slate-500" },
};

function MarkdownSection({ text }: { text: string }) {
  const lines = sanitizeDisplayText(text)
    .replace(/([^\n])\s*(##\s+)/g, "$1\n\n$2")
    .replace(/\n{3,}/g, "\n\n")
    .split("\n");
  const elements: ReactNode[] = [];
  let paragraphBuffer: string[] = [];
  let listBuffer: string[] = [];

  const flushParagraph = (key: string) => {
    if (!paragraphBuffer.length) {
      return;
    }

    elements.push(
      <p key={key} className="text-sm leading-7 text-slate-600">
        {paragraphBuffer.join(" ")}
      </p>,
    );
    paragraphBuffer = [];
  };

  const flushList = (key: string) => {
    if (!listBuffer.length) {
      return;
    }

    elements.push(
      <ul key={key} className="ml-5 list-disc space-y-2 text-sm leading-7 text-slate-600">
        {listBuffer.map((item, index) => (
          <li key={`${key}-${index}`}>{item}</li>
        ))}
      </ul>,
    );
    listBuffer = [];
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i].trim();

    if (!line) {
      flushParagraph(`paragraph-${i}`);
      flushList(`list-${i}`);
      continue;
    }

    if (line.startsWith("## ")) {
      flushParagraph(`paragraph-${i}`);
      flushList(`list-${i}`);
      elements.push(
        <h3 key={i} className="mt-4 text-sm font-semibold text-slate-800">
          {line.slice(3)}
        </h3>,
      );
      continue;
    }

    if (line.startsWith("- ") || line.startsWith("• ")) {
      elements.push(
        <li key={i} className="ml-4 list-disc text-sm leading-relaxed text-slate-600">
          {line.slice(2)}
        </li>,
      );
      continue;
    }

    elements.push(
      <p key={i} className="text-sm leading-relaxed text-slate-600">
        {line}
      </p>,
    );
  }

  return <div className="space-y-2">{elements}</div>;
}

function RichTextSection({ text, tone = "default" }: { text: string; tone?: "default" | "primary" }) {
  const lines = sanitizeDisplayText(text)
    .replace(/([^\n])\s*(##\s+)/g, "$1\n\n$2")
    .replace(/([^\n])\n-\s/g, "$1\n\n- ")
    .replace(/\n{3,}/g, "\n\n")
    .split("\n");
  const elements: ReactNode[] = [];
  const textClass = tone === "primary" ? "text-primary-700" : "text-slate-600";
  const headingClass = tone === "primary" ? "text-primary-800" : "text-slate-800";
  let paragraphBuffer: string[] = [];
  let listBuffer: string[] = [];

  const flushParagraph = (key: string) => {
    if (!paragraphBuffer.length) {
      return;
    }

    elements.push(
      <p key={key} className={clsx("text-sm leading-7", textClass)}>
        {paragraphBuffer.join(" ")}
      </p>,
    );
    paragraphBuffer = [];
  };

  const flushList = (key: string) => {
    if (!listBuffer.length) {
      return;
    }

    elements.push(
      <ul key={key} className={clsx("ml-5 list-disc space-y-2 text-sm leading-7", textClass)}>
        {listBuffer.map((item, index) => (
          <li key={`${key}-${index}`}>{item}</li>
        ))}
      </ul>,
    );
    listBuffer = [];
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i].trim();

    if (!line) {
      flushParagraph(`paragraph-${i}`);
      flushList(`list-${i}`);
      continue;
    }

    if (line.startsWith("## ")) {
      flushParagraph(`paragraph-${i}`);
      flushList(`list-${i}`);
      elements.push(
        <h3 key={i} className={clsx("mt-4 text-sm font-semibold", headingClass)}>
          {line.slice(3)}
        </h3>,
      );
      continue;
    }

    if (/^(-|•)\s+/.test(line)) {
      flushParagraph(`paragraph-${i}`);
      listBuffer.push(line.replace(/^(-|•)\s+/, "").trim());
      continue;
    }

    if (line.length <= 90 && /:$/.test(line)) {
      flushParagraph(`paragraph-${i}`);
      flushList(`list-${i}`);
      elements.push(
        <h4 key={`subheading-${i}`} className={clsx("text-sm font-semibold", headingClass)}>
          {line.slice(0, -1)}
        </h4>,
      );
      continue;
    }

    flushList(`list-${i}`);
    paragraphBuffer.push(line);
  }

  flushParagraph("paragraph-end");
  flushList("list-end");

  return <div className="space-y-3">{elements}</div>;
}

function stripLeadingSectionHeading(text: string, headings: string[]): string {
  let cleaned = sanitizeDisplayText(text);

  for (const heading of headings) {
    const escaped = heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    cleaned = cleaned
      .replace(new RegExp(`^##\\s*${escaped}\\s*\\n+`, "i"), "")
      .replace(new RegExp(`^${escaped}\\s*\\n+`, "i"), "");
  }

  return cleaned.trim();
}

function normalizeForComparison(text: string): string {
  return sanitizeDisplayText(text)
    .toLowerCase()
    .replace(/[^a-z0-9À-ÿ\s]/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function looksTruncated(text: string): boolean {
  const cleaned = sanitizeDisplayText(text);
  if (!cleaned) return false;
  if (/[.!?:»"”)]$/.test(cleaned)) return false;
  const lastWord = cleaned.split(/\s+/).pop() || "";
  return lastWord.length <= 4 || cleaned.length >= 240;
}

function shouldDisplaySummary(shortText?: string | null, longText?: string | null): boolean {
  const shortClean = sanitizeDisplayText(shortText);
  if (!shortClean) return false;

  const longClean = sanitizeDisplayText(longText);
  if (!longClean) return true;

  const shortNormalized = normalizeForComparison(shortClean);
  const longNormalized = normalizeForComparison(longClean);

  if (!shortNormalized) return false;
  if (longNormalized.includes(shortNormalized.slice(0, Math.min(shortNormalized.length, 120)))) {
    return false;
  }

  return !looksTruncated(shortClean);
}

function SectionCard({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: ElementType;
  children: ReactNode;
}) {
  return (
    <section className="card overflow-hidden border border-slate-200/80 bg-white shadow-sm">
      <div className="border-b border-slate-100 bg-slate-50/80 px-5 py-4">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-100 text-primary-700">
            <Icon className="h-4 w-4" />
          </span>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-500">Fiche dispositif</p>
            <h2 className="text-base font-semibold text-slate-900">{title}</h2>
          </div>
        </div>
      </div>
      <div className="space-y-5 px-5 py-5">{children}</div>
    </section>
  );
}

function SectionField({
  eyebrow,
  title,
  content,
}: {
  eyebrow?: string;
  title?: string;
  content: string;
}) {
  const cleaned = sanitizeDisplayText(content);

  if (!cleaned) {
    return null;
  }

  return (
    <div className="space-y-2 border-t border-slate-100 pt-4 first:border-t-0 first:pt-0">
      {eyebrow && <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-500">{eyebrow}</p>}
      {title && <h3 className="text-sm font-semibold text-slate-900">{title}</h3>}
      <RichTextSection text={cleaned} />
    </div>
  );
}

function DateTimeline({ openDate, closeDate }: { openDate: string | null; closeDate: string | null }) {
  if (!openDate && !closeDate) return null;

  const now = new Date();
  const open = openDate ? new Date(openDate) : null;
  const close = closeDate ? new Date(closeDate) : null;
  let progress = 0;

  if (open && close) {
    const total = close.getTime() - open.getTime();
    const elapsed = now.getTime() - open.getTime();
    progress = total > 0 ? Math.max(0, Math.min(100, (elapsed / total) * 100)) : 100;
  } else if (open) {
    progress = now >= open ? 50 : 0;
  }

  const daysLeft = closeDate ? daysUntil(closeDate) : null;
  const isExpired = daysLeft !== null && daysLeft < 0;

  return (
    <div className="mt-5 border-t border-white/20 pt-4">
      <div className="mb-2 flex items-center justify-between text-xs text-white/80">
        <span>{openDate ? formatDate(openDate) : "Ouverture"}</span>
        {closeDate && (
          <span className={clsx("font-semibold", isExpired || (daysLeft !== null && daysLeft <= 7) ? "text-red-200" : "text-white/80")}>
            {isExpired ? "Clôturé" : daysLeft !== null ? `J-${daysLeft}` : formatDate(closeDate)}
          </span>
        )}
        <span>{closeDate ? formatDate(closeDate) : "Clôture non définie"}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/20">
        <div
          className={clsx(
            "h-full rounded-full transition-all duration-500",
            isExpired ? "bg-red-400" : daysLeft !== null && daysLeft <= 7 ? "bg-orange-300" : "bg-white/70",
          )}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

function FundingCard({ device }: { device: Device }) {
  const hasAny = device.amount_max || device.amount_min || device.funding_rate || (device as any).funding_details;

  if (!hasAny) {
    return null;
  }

  return (
    <div className="card border border-primary-100/80 bg-gradient-to-br from-primary-50/80 to-blue-50/70 p-5">
      <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-primary-700">
        <Banknote className="h-4 w-4" />
        Montant de l&apos;aide
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {device.amount_max && (
          <div>
            <div className="mb-0.5 text-xs text-primary-400">Montant maximum</div>
            <div className="text-2xl font-bold text-primary-700">{formatAmount(device.amount_max, device.currency)}</div>
          </div>
        )}
        {device.amount_min && device.amount_min !== device.amount_max && (
          <div>
            <div className="mb-0.5 text-xs text-primary-400">Montant minimum</div>
            <div className="text-lg font-semibold text-primary-600">{formatAmount(device.amount_min, device.currency)}</div>
          </div>
        )}
        {device.funding_rate && (
          <div>
            <div className="mb-0.5 flex items-center gap-1 text-xs text-primary-400">
              <Percent className="h-3 w-3" />
              Taux
            </div>
            <div className="text-lg font-semibold text-primary-600">{device.funding_rate}%</div>
          </div>
        )}
      </div>
      {(device as any).funding_details && (
        <div className="mt-4 border-t border-primary-100 pt-4">
          <RichTextSection text={sanitizeDisplayText((device as any).funding_details)} tone="primary" />
        </div>
      )}
    </div>
  );
}

function InsightCard({
  label,
  value,
  icon: Icon,
  accent = false,
}: {
  label: string;
  value: string;
  icon: ElementType;
  accent?: boolean;
}) {
  return (
    <div className={clsx("rounded-2xl border p-4", accent ? "border-primary-200 bg-primary-50/70" : "border-slate-200 bg-white")}>
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
        <Icon className={clsx("h-3.5 w-3.5", accent && "text-primary-600")} />
        {label}
      </div>
      <div className={clsx("mt-2 text-sm font-semibold leading-6", accent ? "text-primary-800" : "text-slate-900")}>{value}</div>
    </div>
  );
}

export default function DeviceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [device, setDevice] = useState<Device | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [similar, setSimilar] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [showHistory, setShowHistory] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [scraping, setScraping] = useState(false);
  const [scrapeMsg, setScrapeMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [favorite, setFavorite] = useState(false);
  const [role, setRole] = useState<AppRole>("reader");
  const [pipelineStatus, setPipelineStatus] = useState<DevicePipelineStatus | "">("");
  const [pipelineNote, setPipelineNote] = useState("");
  const [pipelineFeedback, setPipelineFeedback] = useState<string | null>(null);
  const cameFromMatch = searchParams.get("from") === "match";
  const canModerate = canModerateDevices(role);
  const PIPELINE_LABELS: Record<DevicePipelineStatus, string> = {
    a_etudier: "A etudier",
    candidature_en_cours: "Candidature en cours",
    non_pertinent: "Non pertinent",
  };

  useEffect(() => {
    const currentRole = getCurrentRole();
    setRole(currentRole);

    devices.get(id)
      .then((deviceResult) => {
        const loadedDevice = deviceResult as Device;
        setDevice(loadedDevice);

        if (canModerateDevices(currentRole)) {
          devices.history(id)
            .then((historyResult) => setHistory(historyResult as any[]))
            .catch(() => setHistory([]));
        }

        return devices.list({
          device_types: [loadedDevice.device_type],
          countries: [loadedDevice.country],
          page_size: 4,
          status: "open",
        });
      })
      .then((res: any) => {
        setSimilar((res?.items || []).filter((item: Device) => item.id !== id).slice(0, 3));
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    setFavorite(isFavoriteDevice(id));
    const tracked = getPipelineDevice(id);
    setPipelineStatus(tracked?.pipelineStatus || "");
    setPipelineNote(tracked?.note || "");
  }, [id]);

  const handleValidate = async () => {
    setActionLoading(true);
    try {
      const updated = await devices.validate(id);
      setDevice(updated as Device);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!confirm("Rejeter ce dispositif ?")) return;
    setActionLoading(true);
    try {
      const updated = await devices.reject(id);
      setDevice(updated as Device);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) {
      setDeleteConfirm(true);
      setDeleteError(null);
      return;
    }

    setDeleteLoading(true);
    setDeleteError(null);

    try {
      await devices.delete(id);
      router.push("/devices");
    } catch (e: any) {
      setDeleteError(e.message || "Impossible de supprimer.");
      setDeleteLoading(false);
      setDeleteConfirm(false);
    }
  };

  const handleScrape = async () => {
    setScraping(true);
    setScrapeMsg(null);

    try {
      const updated = await devices.scrape(id);
      setDevice(updated as Device);
      setScrapeMsg({ type: "success", text: "Fiche enrichie avec succès depuis la source officielle." });
    } catch (e: any) {
      setScrapeMsg({ type: "error", text: e.message || "Impossible d'enrichir cette fiche." });
    } finally {
      setScraping(false);
    }
  };

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleToggleFavorite = () => {
    if (!device) return;

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

  const handleSavePipeline = () => {
    if (!device) return;

    if (!pipelineStatus && !pipelineNote.trim()) {
      removePipelineDevice(device.id);
      setPipelineFeedback("Le suivi personnel a été effacé pour cette fiche.");
      return;
    }

    if (!pipelineStatus) {
      setPipelineFeedback("Choisis d'abord un statut personnel pour enregistrer ce suivi.");
      return;
    }

    savePipelineDevice({
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
      pipelineStatus,
      note: pipelineNote.trim(),
    });
    setPipelineFeedback("Suivi personnel enregistré dans Mon espace.");
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="max-w-4xl animate-pulse space-y-4">
          <div className="h-8 w-48 rounded bg-gray-200" />
          <div className="h-48 rounded-2xl bg-gradient-to-br from-gray-200 to-gray-300" />
        </div>
      </AppLayout>
    );
  }

  if (!device) {
    return (
      <AppLayout>
        <div className="py-20 text-center text-gray-400">Dispositif introuvable</div>
      </AppLayout>
    );
  }

  const daysLeft = device.close_date ? daysUntil(device.close_date) : null;
  const isClosingSoon = daysLeft !== null && daysLeft >= 0 && daysLeft <= 30;
  const hasRichContent = !!(device.full_description || device.eligibility_criteria || device.eligible_expenses);
  const hasEnrichedContent = !!(device.auto_summary || device.full_description || device.eligibility_criteria || device.eligible_expenses);
  const hero = TYPE_HERO[device.device_type] || TYPE_HERO.autre;
  const natureBanner = getDeviceNatureBanner(device);
  const beneficiarySummary = device.beneficiaries?.length
    ? device.beneficiaries.map((item) => item.replace(/_/g, " ")).join(", ")
    : null;
  const showShortDescription = shouldDisplaySummary(device.short_description, device.full_description);
  const showEligibleExpenses = shouldDisplaySummary(device.eligible_expenses, device.full_description);
  const natureBannerTone =
    natureBanner?.kind === "open_call"
      ? "border-emerald-200/70 bg-emerald-50/15 text-emerald-50"
      : natureBanner?.kind === "recurring"
        ? "border-blue-200/70 bg-blue-50/15 text-blue-50"
        : natureBanner?.kind === "institutional_project"
        ? "border-violet-200/70 bg-violet-50/15 text-violet-50"
        : "border-amber-200/70 bg-amber-50/15 text-amber-50";
  const presentationContent = sanitizeDisplayText(
    stripLeadingSectionHeading(device.full_description || "", ["PrÃ©sentation", "PrÃ©sentation du dispositif"]),
  );
  const eligibilityContent = sanitizeDisplayText(
    stripLeadingSectionHeading(device.eligibility_criteria || "", ["CritÃ¨res d'Ã©ligibilitÃ©", "Conditions d'attribution"]),
  );
  const projectContent = sanitizeDisplayText(
    stripLeadingSectionHeading(device.eligible_expenses || "", ["DÃ©penses concernÃ©es", "Montants & Financement"]),
  );
  const fundingContent = sanitizeDisplayText((device as any).funding_details || "");
  const hasDistinctFundingText =
    fundingContent && normalizeForComparison(fundingContent) !== normalizeForComparison(presentationContent);

  return (
    <AppLayout>
      <div className="max-w-5xl">
        <div className="mb-4 flex items-center justify-between">
          <button
            onClick={() => (cameFromMatch ? router.push("/match") : router.back())}
            className="btn-secondary flex items-center gap-1.5 text-xs"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Retour
          </button>
          <div className="flex flex-wrap items-center gap-2">
            {canModerate && device.validation_status === "pending_review" && (
              <>
                <button onClick={handleValidate} disabled={actionLoading} className="btn-primary bg-green-600 text-xs hover:bg-green-700">
                  <ShieldCheck className="h-3 w-3" />
                  Valider
                </button>
                <button onClick={handleReject} disabled={actionLoading} className="btn-secondary border-red-300 text-xs text-red-600 hover:bg-red-50">
                  <XCircle className="h-3 w-3" />
                  Rejeter
                </button>
              </>
            )}
            {canModerate && (
              <>
                <button
                  onClick={handleScrape}
                  disabled={scraping}
                  className="btn-secondary flex items-center gap-1.5 border-violet-300 text-xs text-violet-700 hover:bg-violet-50"
                >
                  {scraping ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
                  {scraping ? "Enrichissement..." : "Enrichir"}
                </button>
                <button onClick={() => setShowHistory(!showHistory)} className="btn-secondary text-xs">
                  <History className="h-3 w-3" />
                  Historique
                </button>
              </>
            )}
            <button onClick={handleCopyLink} className="btn-secondary flex items-center gap-1.5 text-xs">
              <Share2 className="h-3 w-3" />
              {copied ? "Copié" : "Partager"}
            </button>
            <button
              onClick={handleToggleFavorite}
              className={clsx(
                "btn-secondary flex items-center gap-1.5 text-xs",
                favorite && "border-rose-300 text-rose-600 hover:bg-rose-50"
              )}
            >
              <Heart className={clsx("h-3 w-3", favorite && "fill-current")} />
              {favorite ? "Favori" : "Ajouter aux favoris"}
            </button>
            {canModerate &&
              (deleteConfirm ? (
                <div className="flex items-center gap-1">
                  <button
                    onClick={handleDelete}
                    disabled={deleteLoading}
                    className="btn-secondary border-red-600 bg-red-600 text-xs text-white hover:bg-red-700 disabled:opacity-60"
                  >
                    {deleteLoading ? "Suppression..." : "Confirmer"}
                  </button>
                  <button onClick={() => { setDeleteConfirm(false); setDeleteError(null); }} className="btn-secondary text-xs">
                    Annuler
                  </button>
                </div>
              ) : (
                <button onClick={handleDelete} className="btn-secondary text-xs text-red-600 hover:bg-red-50" title="Supprimer">
                  <Trash2 className="h-3 w-3" />
                </button>
              ))}
          </div>
        </div>

        {deleteError && (
          <div className="mb-4 flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>{deleteError}</span>
          </div>
        )}

        {scrapeMsg && (
          <div
            className={clsx(
              "mb-4 flex items-start gap-2 rounded-xl border px-4 py-3 text-sm",
              scrapeMsg.type === "success" ? "border-green-200 bg-green-50 text-green-700" : "border-red-200 bg-red-50 text-red-700",
            )}
          >
            {scrapeMsg.type === "success" ? (
              <CheckCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            ) : (
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            )}
            <span>{scrapeMsg.text}</span>
          </div>
        )}

        <div className={clsx("mb-4 rounded-[28px] bg-gradient-to-br p-6 text-white shadow-md", hero.from, hero.to)}>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/20 px-2.5 py-1 text-xs font-medium text-white backdrop-blur-sm">
              {DEVICE_TYPE_LABELS[device.device_type] || device.device_type}
            </span>
            <span className="rounded-full bg-white/25 px-2.5 py-1 text-xs font-medium text-white">
              {STATUS_LABELS[device.status]}
            </span>
            {device.is_recurring && (
              <span className="rounded-full bg-white/20 px-2.5 py-1 text-xs font-medium text-white">Récurrent</span>
            )}
          </div>

          {natureBanner && (
            <div className={clsx("mb-4 rounded-2xl border px-4 py-3 backdrop-blur-sm", natureBannerTone)}>
              <div className="flex items-start gap-3">
                <Info className="mt-0.5 h-4 w-4 flex-shrink-0" />
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em]">{natureBanner.label}</p>
                  <p className="mt-1 text-sm leading-relaxed text-white/90">{natureBanner.detail}</p>
                </div>
              </div>
            </div>
          )}

          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-white/70">Dispositif de financement</p>
              <h1 className="mb-2 text-2xl font-bold leading-snug text-white">{device.title}</h1>
              {device.auto_summary && (
                <p className="line-clamp-3 text-sm italic leading-relaxed text-white/80">
                  {sanitizeDisplayText(device.auto_summary)}
                </p>
              )}
            </div>

            {device.amount_max && (
              <div className="flex-shrink-0 rounded-2xl bg-white/20 px-4 py-3 text-right backdrop-blur-sm">
                <div className="mb-0.5 text-xs font-medium text-white/70">Jusqu&apos;à</div>
                <div className="text-2xl font-bold text-white">{formatAmount(device.amount_max, device.currency)}</div>
              </div>
            )}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-white/20 pt-4 text-sm text-white/80">
            <span className="flex items-center gap-1.5">
              <Building2 className="h-3.5 w-3.5 flex-shrink-0" />
              {device.organism}
            </span>
            <span className="flex items-center gap-1.5">
              <MapPin className="h-3.5 w-3.5 flex-shrink-0" />
              {device.country}
              {device.region ? ` · ${device.region}` : ""}
              {(device as any).zone ? ` · ${(device as any).zone}` : ""}
            </span>
            {device.first_seen_at && (
              <span className="ml-auto flex items-center gap-1.5 text-xs text-white/60">
                <Clock className="h-3 w-3" />
                Ajouté le {formatDate(device.first_seen_at)}
              </span>
            )}
          </div>

          <DateTimeline openDate={device.open_date} closeDate={device.close_date} />
        </div>

        {isClosingSoon && daysLeft !== null && (
          <div
            className={clsx(
              "mb-4 flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium",
              daysLeft <= 7 ? "border border-red-200 bg-red-50 text-red-700" : "border border-orange-200 bg-orange-50 text-orange-700",
            )}
          >
            <Clock className="h-4 w-4 flex-shrink-0" />
            Clôture dans <strong>{daysLeft} jour{daysLeft > 1 ? "s" : ""}</strong>
            {device.close_date && ` - ${formatDate(device.close_date)}`}
          </div>
        )}

        <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <InsightCard
            label="Date limite"
            value={device.close_date ? formatDate(device.close_date) : device.status === "recurring" ? "Dispositif récurrent" : "Non communiquée"}
            icon={Calendar}
            accent={!!device.close_date}
          />
          <InsightCard
            label="Montant"
            value={device.amount_max ? formatAmount(device.amount_max, device.currency) : "Montant à confirmer"}
            icon={Banknote}
            accent={!!device.amount_max}
          />
          <InsightCard
            label="Portée géographique"
            value={[device.country, device.region, device.zone].filter(Boolean).join(" · ") || "Non renseignée"}
            icon={MapPin}
          />
          <InsightCard
            label="Type réel"
            value={DEVICE_TYPE_LABELS[device.device_type] || device.device_type}
            icon={Tag}
          />
        </div>

        <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="space-y-4 md:col-span-2">
            {canModerate && !hasRichContent && (
              <div className="card border-2 border-dashed border-violet-200 bg-violet-50/30 p-6 text-center">
                <Sparkles className="mx-auto mb-2 h-8 w-8 text-violet-400" />
                <p className="mb-1 text-sm font-medium text-violet-700">Fiche incomplète</p>
                <p className="mb-4 text-xs text-violet-500">
                  Cliquez sur &quot;Enrichir&quot; pour récupérer plus d&apos;informations depuis la source officielle.
                </p>
                <button onClick={handleScrape} disabled={scraping} className="btn-primary border-violet-600 bg-violet-600 text-xs hover:bg-violet-700">
                  {scraping ? "Enrichissement..." : "Enrichir maintenant"}
                </button>
              </div>
            )}

            <FundingCard device={device} />

            {(device.short_description || presentationContent) && (
              <SectionCard title="Présentation du dispositif" icon={FileText}>
                {showShortDescription && device.short_description && <SectionField content={device.short_description} />}
                {presentationContent && <SectionField content={presentationContent} />}
              </SectionCard>
            )}

            {(beneficiarySummary || eligibilityContent) && (
              <SectionCard title="Conditions d'attribution" icon={CheckCircle}>
                {beneficiarySummary && (
                  <SectionField
                    eyebrow="À qui s'adresse le dispositif ?"
                    title="Entreprises éligibles"
                    content={beneficiarySummary}
                  />
                )}
                {eligibilityContent && (
                  <SectionField
                    title="Critères d'éligibilité"
                    content={eligibilityContent}
                  />
                )}
              </SectionCard>
            )}

            {(projectContent || device.specific_conditions || hasDistinctFundingText) && (
              <SectionCard title="Pour quel projet ?" icon={Tag}>
                {showEligibleExpenses && projectContent && (
                  <SectionField
                    title="Dépenses concernées"
                    content={projectContent}
                  />
                )}
                {hasDistinctFundingText && <SectionField title="Montant / avantages" content={fundingContent} />}
                {device.specific_conditions && <SectionField title="Quelles sont les particularités ?" content={device.specific_conditions} />}
              </SectionCard>
            )}

            {(device.required_documents || device.source_url || (device as any).recurrence_notes) && (
              <SectionCard title="Informations pratiques" icon={Info}>
                {device.required_documents && (
                  <SectionField
                    title="Pièces et documents utiles"
                    content={stripLeadingSectionHeading(device.required_documents, [
                      "Pièces et documents utiles",
                      "Informations pratiques",
                    ])}
                  />
                )}
                {device.is_recurring && (device as any).recurrence_notes && (
                  <SectionField
                    title="Rythme et récurrence"
                    content={stripLeadingSectionHeading((device as any).recurrence_notes, [
                      "Rythme et récurrence",
                      "Informations pratiques",
                    ])}
                  />
                )}
                {device.source_url && (
                  <div className="rounded-2xl border border-primary-100 bg-primary-50/60 p-4">
                    <p className="mb-2 text-sm font-semibold text-slate-900">Quelle démarche suivre ?</p>
                    <p className="mb-3 text-sm text-slate-600">
                      La demande ou la consultation détaillée se fait auprès de l&apos;organisme source.
                    </p>
                    <a
                      href={device.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 text-sm font-medium text-primary-700 hover:text-primary-800"
                    >
                      <ExternalLink className="h-4 w-4" />
                      Ouvrir la source officielle
                    </a>
                  </div>
                )}
              </SectionCard>
            )}
          </div>

          <div className="space-y-4">
            {device.source_url && (
              <a
                href={device.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-primary-700"
              >
                <ExternalLink className="h-4 w-4" />
                Accéder au dispositif
                <ArrowRight className="ml-auto h-4 w-4" />
              </a>
            )}

            {(device.sectors?.length || device.beneficiaries?.length) && (
              <div className="card p-4 space-y-3">
                {device.sectors?.length ? (
                  <div>
                    <div className="mb-1.5 flex items-center gap-1 text-xs font-medium text-gray-400">
                      <Tag className="h-3 w-3" />
                      Secteurs
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {device.sectors.map((sector) => (
                        <span key={sector} className="badge bg-emerald-50 text-xs capitalize text-emerald-700">
                          {sector}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}

                {device.beneficiaries?.length ? (
                  <div>
                    <div className="mb-1.5 flex items-center gap-1 text-xs font-medium text-gray-400">
                      <Users className="h-3 w-3" />
                      Bénéficiaires
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {device.beneficiaries.map((beneficiary) => (
                        <span key={beneficiary} className="badge bg-purple-50 text-xs capitalize text-purple-700">
                          {beneficiary}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            )}

            <div className="card p-4">
              <h2 className="mb-3 flex items-center gap-1.5 text-sm font-semibold text-gray-700">
                <Info className="h-3.5 w-3.5 text-gray-400" />
                Qualité
              </h2>
              <div className="space-y-2.5">
                {[
                  { label: "Fiabilité", value: device.confidence_score },
                  { label: "Complétude", value: device.completeness_score },
                  { label: "Pertinence", value: device.relevance_score },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <div className="mb-0.5 flex justify-between text-xs text-gray-500">
                      <span>{label}</span>
                      <span className="font-semibold">{value}%</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-gray-100">
                      <div
                        className={clsx(
                          "h-full rounded-full transition-all",
                          value >= 70 ? "bg-green-500" : value >= 40 ? "bg-yellow-400" : "bg-red-400",
                        )}
                        style={{ width: `${value}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {device.keywords?.length ? (
              <div className="card p-4">
                <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">Mots clés</h2>
                <div className="flex flex-wrap gap-1">
                  {device.keywords.map((keyword) => (
                    <span key={keyword} className="badge bg-gray-100 text-xs text-gray-600">
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="card p-4">
              <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                <div className="mb-3 flex items-center gap-2">
                  <Flag className="h-4 w-4 text-primary-600" />
                  <h2 className="text-sm font-semibold text-slate-900">Suivi personnel</h2>
                </div>
                <div className="space-y-3">
                  <div>
                    <label className="mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                      Statut du pipeline
                    </label>
                    <select
                      value={pipelineStatus}
                      onChange={(e) => {
                        setPipelineStatus(e.target.value as DevicePipelineStatus | "");
                        setPipelineFeedback(null);
                      }}
                      className="input text-sm"
                    >
                      <option value="">Aucun suivi</option>
                      <option value="a_etudier">A étudier</option>
                      <option value="candidature_en_cours">Candidature en cours</option>
                      <option value="non_pertinent">Non pertinent</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                      <StickyNote className="h-3.5 w-3.5" />
                      Note
                    </label>
                    <textarea
                      value={pipelineNote}
                      onChange={(e) => {
                        setPipelineNote(e.target.value);
                        setPipelineFeedback(null);
                      }}
                      rows={4}
                      placeholder="Ex. à revoir avec l'équipe, manque un document, intéressant pour Q3..."
                      className="input min-h-[110px] resize-y py-3 text-sm"
                    />
                  </div>
                  {pipelineFeedback && (
                    <p className="text-xs text-primary-700">{pipelineFeedback}</p>
                  )}
                  <div className="flex items-center gap-2">
                    <button type="button" onClick={handleSavePipeline} className="btn-secondary text-xs">
                      Enregistrer le suivi
                    </button>
                    {(pipelineStatus || pipelineNote.trim()) && (
                      <button
                        type="button"
                        onClick={() => {
                          setPipelineStatus("");
                          setPipelineNote("");
                          removePipelineDevice(id);
                          setPipelineFeedback("Le suivi personnel a été retiré.");
                        }}
                        className="text-xs font-medium text-slate-500 hover:text-red-500"
                      >
                        Réinitialiser
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {hasEnrichedContent && (
                <div className="mb-4 rounded-2xl border border-primary-100 bg-primary-50/60 p-4">
                  <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-primary-800">
                    <CheckCircle className="h-4 w-4" />
                    Source de vérité
                  </h2>
                  <div className="space-y-2 text-sm text-slate-700">
                    <p className="font-medium text-primary-700">Texte enrichi automatiquement</p>
                    {device.last_verified_at && (
                      <p>
                        Dernière vérification : <span className="font-medium">{formatDate(device.last_verified_at)}</span>{" "}
                        <span className="text-slate-500">({formatDateRelative(device.last_verified_at)})</span>
                      </p>
                    )}
                    <p className="text-slate-600">
                      Certaines conditions doivent être confirmées sur le site officiel.
                    </p>
                  </div>
                </div>
              )}

              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-400">Source</h2>
              <div className="space-y-1.5 text-xs text-gray-500">
                {device.last_verified_at && (
                  <div className="flex items-center gap-1.5">
                    <RefreshCw className="h-3 w-3 text-gray-300" />
                    Vérifié le {formatDate(device.last_verified_at)}
                  </div>
                )}
                {device.first_seen_at && (
                  <div className="flex items-center gap-1.5">
                    <Clock className="h-3 w-3 text-gray-300" />
                    Ajouté le {formatDate(device.first_seen_at)}
                  </div>
                )}
                {device.open_date && (
                  <div className="flex items-center gap-1.5">
                    <Calendar className="h-3 w-3 text-gray-300" />
                    Ouverture : {formatDate(device.open_date)}
                  </div>
                )}
                {!device.close_date && (
                  <div className="flex items-center gap-1.5 italic text-gray-400">
                    <Calendar className="h-3 w-3 text-gray-300" />
                    Clôture non renseignée
                  </div>
                )}
                {device.close_date && (
                  <div
                    className={clsx(
                      "flex items-center gap-1.5 font-medium",
                      daysLeft !== null && daysLeft <= 7 ? "text-red-500" : daysLeft !== null && daysLeft <= 30 ? "text-orange-500" : "",
                    )}
                  >
                    <Calendar className="h-3 w-3" />
                    Clôture : {formatDate(device.close_date)}
                    {daysLeft !== null && daysLeft >= 0 && ` (J-${daysLeft})`}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {similar.length > 0 && (
          <div className="mb-6">
            <h2 className="mb-3 flex items-center gap-2 text-base font-semibold text-gray-700">
              <ArrowRight className="h-4 w-4 text-primary-400" />
              Dispositifs similaires
            </h2>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              {similar.map((item) => (
                <DeviceCard key={item.id} device={item} />
              ))}
            </div>
          </div>
        )}

        {showHistory && (
          <div className="card p-4">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-700">
              <History className="h-4 w-4 text-gray-400" />
              Historique des modifications
            </h2>
            {history.length === 0 ? (
              <p className="py-4 text-center text-sm text-gray-400">Aucune modification enregistrée</p>
            ) : (
              <div className="space-y-2">
                {history.map((item: any) => (
                  <div key={item.id} className="flex items-start gap-3 border-b border-gray-50 py-2 text-xs last:border-0">
                    <div className="w-28 flex-shrink-0 pt-0.5 text-gray-400">{formatDate(item.changed_at)}</div>
                    <div className="min-w-0 flex-1">
                      <div className="mb-0.5 flex items-center gap-2">
                        <span className="badge bg-gray-100 capitalize text-gray-600">{item.change_type}</span>
                        {item.field_name && (
                          <span className="rounded bg-blue-50 px-1.5 py-0.5 font-mono text-xs text-blue-600">{item.field_name}</span>
                        )}
                        <span className="text-gray-400">par {item.changed_by}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
