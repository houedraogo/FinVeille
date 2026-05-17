"use client";

import { useEffect, useState, type ElementType, type ReactNode } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import AppLayout from "@/components/AppLayout";
import DeviceCard from "@/components/DeviceCard";
import { devices } from "@/lib/api";
import { canModerateDevices, getCurrentRole, type AppRole } from "@/lib/auth";
import { Device, STATUS_LABELS } from "@/lib/types";
import { getUserDeviceTypeMeta } from "@/lib/deviceTypes";
import { formatAmount, formatDate, formatDateRelative, daysUntil, getAiReadinessMeta, getDeviceNatureBanner, sanitizeDisplayText } from "@/lib/utils";
import {
  addPipelineDocument,
  getPipelineDevice,
  isFavoriteDevice,
  readLatestMatchSnapshot,
  removePipelineDevice,
  removePipelineDocument,
  savePipelineDevice,
  toggleFavoriteDevice,
  type DevicePipelinePriority,
  type DevicePipelineStatus,
  type MatchWorkspaceSnapshot,
  type PipelineDocument,
} from "@/lib/workspace";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Banknote,
  Bell,
  Brain,
  Building2,
  Calendar,
  CheckCircle,
  CheckSquare,
  Clock,
  ExternalLink,
  FileText,
  History,
  Info,
  LinkIcon,
  Loader2,
  MapPin,
  Paperclip,
  Percent,
  Plus,
  RefreshCw,
  Share2,
  ShieldCheck,
  Sparkles,
  Tag,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  TrendingUp,
  Users,
  Heart,
  Flag,
  StickyNote,
  X,
  XCircle,
  Zap,
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

function getContentSection(device: Device, key: string): string {
  const sections =
    device.ai_rewrite_status === "done" && Array.isArray(device.ai_rewritten_sections_json)
      ? device.ai_rewritten_sections_json
      : Array.isArray(device.content_sections_json)
        ? device.content_sections_json
        : [];
  const section = sections.find((item) => item?.key === key);
  return sanitizeDisplayText(section?.content || "");
}

function extractMarkdownSection(text: string, headings: string[]): string {
  const cleaned = sanitizeDisplayText(text);
  if (!cleaned.includes("## ")) {
    return stripLeadingSectionHeading(cleaned, headings);
  }

  const normalizedHeadings = headings.map((heading) => sanitizeDisplayText(heading).toLowerCase());
  const blocks = cleaned.split(/\n(?=##\s+)/);
  const block = blocks.find((item) => {
    const firstLine = item.split("\n", 1)[0]?.replace(/^##\s*/, "").trim().toLowerCase();
    return normalizedHeadings.includes(firstLine);
  });

  if (!block) {
    return "";
  }

  return block.replace(/^##\s*[^\n]+\n?/, "").trim();
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
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-500">Opportunité</p>
            <h2 className="text-base font-semibold text-slate-900">{title}</h2>
          </div>
        </div>
      </div>
      <div className="space-y-5 px-5 py-5">{children}</div>
    </section>
  );
}

function CollapsibleSection({
  title,
  icon: Icon,
  children,
  defaultOpen = false,
}: {
  title: string;
  icon: ElementType;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details
      open={defaultOpen}
      className="group rounded-2xl border border-slate-200 bg-white shadow-sm transition-colors open:border-primary-100"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4">
        <span className="flex min-w-0 items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600 group-open:bg-primary-100 group-open:text-primary-700">
            <Icon className="h-4 w-4" />
          </span>
          <span className="min-w-0">
            <span className="block text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400 group-open:text-primary-500">
              Details
            </span>
            <span className="block truncate text-base font-semibold text-slate-900">{title}</span>
          </span>
        </span>
        <ArrowRight className="h-4 w-4 shrink-0 text-slate-400 transition-transform group-open:rotate-90" />
      </summary>
      <div className="space-y-5 border-t border-slate-100 px-5 py-5">{children}</div>
    </details>
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

function getDecisionBanner(device: Device, daysLeft: number | null) {
  const nature = getDeviceNatureBanner(device);
  if (device.validation_status === "pending_review") {
    return {
      label: "A verifier",
      detail: "Cette fiche contient des informations utiles, mais certaines donnees doivent encore etre confirmees.",
      className: "border-amber-200 bg-amber-50 text-amber-800",
    };
  }
  if (nature?.kind === "investor") {
    return {
      label: nature.label,
      detail: nature.detail,
      className: "border-sky-200 bg-sky-50 text-sky-800",
    };
  }
  if (nature?.kind === "institutional_project") {
    return {
      label: nature.label,
      detail: nature.detail,
      className: "border-violet-200 bg-violet-50 text-violet-800",
    };
  }
  if (nature?.kind === "recurring") {
    return {
      label: nature.label,
      detail: nature.detail,
      className: "border-blue-200 bg-blue-50 text-blue-800",
    };
  }
  if (device.is_recurring || device.status === "recurring") {
    return {
      label: "Financement permanent",
      detail: "Cette opportunité fonctionne sans fenêtre de clôture unique ou selon un rythme récurrent.",
      className: "border-blue-200 bg-blue-50 text-blue-800",
    };
  }
  if (device.status === "expired" || device.status === "closed") {
    return {
      label: "Cloture",
      detail: "La date limite est passée ou cette opportunité est indiquée comme fermée.",
      className: "border-slate-200 bg-slate-100 text-slate-700",
    };
  }
  if (!device.close_date) {
    return {
      label: nature?.label || "Date limite non communiquee",
      detail: nature?.detail || "La source ne fournit pas encore de date limite exploitable. Verifie la page officielle avant de candidater.",
      className: "border-orange-200 bg-orange-50 text-orange-800",
    };
  }
  if (daysLeft !== null && daysLeft >= 0 && daysLeft <= 30) {
    return {
      label: "Appel en cours",
      detail: `La cloture approche : ${daysLeft} jour${daysLeft > 1 ? "s" : ""} restant${daysLeft > 1 ? "s" : ""}.`,
      className: daysLeft <= 7 ? "border-red-200 bg-red-50 text-red-700" : "border-orange-200 bg-orange-50 text-orange-800",
    };
  }
  return {
    label: "Appel en cours",
    detail: "Cette opportunité est ouverte et dispose d'une date limite identifiee.",
    className: "border-emerald-200 bg-emerald-50 text-emerald-800",
  };
}

function buildDecisionSummary(device: Device, presentationContent: string, fundingContent: string, daysLeft: number | null) {
  const parts = [];
  const deviceType = getUserDeviceTypeMeta(device.device_type).label;
  const presentation = sanitizeDisplayText(presentationContent)
    .replace(/^##\s*[^\n]+\n+/i, "")
    .replace(/^\s*(Presentation|Présentation)\s+/i, "")
    .trim();
  parts.push(`Cette opportunité correspond à un financement de type ${deviceType.toLowerCase()} porté par ${device.organism}.`);
  if (device.amount_max) {
    parts.push(`Le montant peut atteindre ${formatAmount(device.amount_max, device.currency)}.`);
  } else if (fundingContent) {
    parts.push("Les avantages financiers ou l'accompagnement sont decrits dans cette opportunité.");
  }
  if (device.close_date && daysLeft !== null && daysLeft >= 0) {
    parts.push(`La date limite est le ${formatDate(device.close_date)}.`);
  } else if (device.is_recurring || device.status === "recurring") {
    parts.push("Cette opportunité semble récurrente ou permanente.");
  } else {
    parts.push("La date limite doit etre confirmee sur la source officielle.");
  }
  if (presentation && presentation.length > 120) {
    parts.push(presentation.slice(0, 180).replace(/\s+\S*$/, "") + ".");
  }
  return parts.join(" ");
}

function buildUserDecisionSummary(device: Device, presentationContent: string, fundingContent: string, daysLeft: number | null) {
  if (!isInstitutionalProjectDevice(device)) {
    return buildDecisionSummary(device, presentationContent, fundingContent, daysLeft);
  }

  const parts = [
    `Cette fiche correspond a un projet institutionnel porte par ${device.organism}.`,
    "Elle sert de signal de veille pour comprendre les priorites financees dans ce pays ou ce secteur.",
  ];

  if (device.close_date && daysLeft !== null && daysLeft >= 0) {
    parts.push(`La date indiquee dans la source est le ${formatDate(device.close_date)} : elle correspond au calendrier du projet, pas a une date limite de candidature.`);
  } else {
    parts.push("Aucune date de candidature directe n'est publiee pour cette fiche.");
  }

  const presentation = sanitizeDisplayText(presentationContent).replace(/^##\s*[^\n]+\n+/i, "").trim();
  if (presentation && presentation.length > 120) {
    parts.push(presentation.slice(0, 180).replace(/\s+\S*$/, "") + ".");
  }

  return parts.join(" ");
}

function getDecisionPriority(device: Device, daysLeft: number | null): { label: string; className: string } {
  if (device.status === "expired" || device.status === "closed") {
    return { label: "Non prioritaire", className: "border-slate-200 bg-slate-100 text-slate-700" };
  }
  if (daysLeft !== null && daysLeft >= 0 && daysLeft <= 7) {
    return { label: "Priorite haute", className: "border-red-200 bg-red-50 text-red-700" };
  }
  if (daysLeft !== null && daysLeft >= 0 && daysLeft <= 30) {
    return { label: "A traiter bientot", className: "border-orange-200 bg-orange-50 text-orange-800" };
  }
  if (device.relevance_label || device.amount_max || device.is_recurring) {
    return { label: "A etudier", className: "border-emerald-200 bg-emerald-50 text-emerald-800" };
  }
  return { label: "A confirmer", className: "border-amber-200 bg-amber-50 text-amber-800" };
}

function getEffortLabel(device: Device): string {
  const text = normalizeForComparison(
    [
      device.required_documents,
      device.eligibility_criteria,
      device.specific_conditions,
      device.full_description,
    ]
      .filter(Boolean)
      .join(" "),
  );

  if (/business plan|plan d affaires|pitch|dossier|cofinancement|partenaire|incubateur|documents?/.test(text)) {
    return "Effort moyen";
  }
  if (device.status === "recurring" || device.is_recurring) {
    return "Effort a confirmer";
  }
  return "Effort leger";
}

function getShortPreview(text: string, fallback: string): string {
  const cleaned = sanitizeDisplayText(text).replace(/^##\s*[^\n]+\n?/i, "").trim();
  if (!cleaned) return fallback;
  const firstSentence = cleaned.split(/(?<=[.!?])\s+/)[0] || cleaned;
  return firstSentence.length > 180 ? `${firstSentence.slice(0, 176).replace(/\s+\S*$/, "")}...` : firstSentence;
}

function isInstitutionalProjectDevice(device: Device): boolean {
  const context = `${device.device_type || ""} ${device.organism || ""} ${device.source_url || ""}`.toLowerCase();
  return (
    device.device_type === "institutional_project" ||
    context.includes("world bank") ||
    context.includes("banque mondiale") ||
    context.includes("projects.worldbank.org")
  );
}

// ─── Score helpers ────────────────────────────────────────────────────────────

function ScoreBar({ score, colorClass }: { score: number; colorClass: string }) {
  return (
    <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
      <div className={clsx("h-full rounded-full transition-all", colorClass)} style={{ width: `${Math.min(100, Math.max(0, score))}%` }} />
    </div>
  );
}

function ScoreChip({ label, score }: { label: string; score: number }) {
  const color = score >= 70 ? "text-emerald-700 bg-emerald-50 border-emerald-200" : score >= 40 ? "text-amber-700 bg-amber-50 border-amber-200" : "text-red-700 bg-red-50 border-red-200";
  const barColor = score >= 70 ? "bg-emerald-500" : score >= 40 ? "bg-amber-500" : "bg-red-400";
  return (
    <div className={clsx("rounded-xl border px-3 py-2.5", color)}>
      <p className="text-[9px] font-semibold uppercase tracking-[0.16em] opacity-70">{label}</p>
      <p className="mt-0.5 text-sm font-bold">{score}%</p>
      <ScoreBar score={score} colorClass={barColor} />
    </div>
  );
}

function LevelChip({ label, level }: { label: string; level: string }) {
  const cfg: Record<string, { cls: string; icon: string }> = {
    faible: { cls: "text-emerald-700 bg-emerald-50 border-emerald-200", icon: "↓" },
    moyenne: { cls: "text-amber-700 bg-amber-50 border-amber-200", icon: "→" },
    haute: { cls: "text-orange-700 bg-orange-50 border-orange-200", icon: "↑" },
    critique: { cls: "text-red-700 bg-red-50 border-red-200", icon: "⚡" },
  };
  const c = cfg[level] || cfg.moyenne;
  return (
    <div className={clsx("rounded-xl border px-3 py-2.5", c.cls)}>
      <p className="text-[9px] font-semibold uppercase tracking-[0.16em] opacity-70">{label}</p>
      <p className="mt-0.5 text-sm font-bold capitalize">{c.icon} {level}</p>
    </div>
  );
}

function GoNoGoCard({ goNoGo, priority, action }: { goNoGo: string; priority: string; action?: string }) {
  const cfgs: Record<string, { label: string; detail: string; cls: string; badgeCls: string; Icon: ElementType }> = {
    go: {
      label: "Bonne opportunité pour votre profil",
      detail: "Les signaux disponibles indiquent une opportunité accessible et potentiellement pertinente.",
      cls: "border-emerald-300 bg-gradient-to-br from-emerald-50 to-emerald-100/60",
      badgeCls: "bg-emerald-600 text-white",
      Icon: ThumbsUp,
    },
    no_go: {
      label: "Peu recommandé à ce stade",
      detail: "Les critères ou conditions identifiés rendent la candidature difficile sans préparation avancée.",
      cls: "border-red-200 bg-gradient-to-br from-red-50 to-red-100/40",
      badgeCls: "bg-red-600 text-white",
      Icon: ThumbsDown,
    },
    a_verifier: {
      label: "Décision à prendre — informations à confirmer",
      detail: "Des points restent flous. Vérifiez les critères sur la source officielle avant de décider.",
      cls: "border-amber-200 bg-gradient-to-br from-amber-50 to-amber-100/50",
      badgeCls: "bg-amber-500 text-white",
      Icon: AlertCircle,
    },
  };
  const cfg = cfgs[goNoGo] || cfgs.a_verifier;
  const priorityLabel: Record<string, string> = { haute: "Priorité haute", moyenne: "Priorité moyenne", faible: "Priorité faible" };
  const { Icon } = cfg;
  return (
    <div className={clsx("rounded-2xl border px-4 py-4", cfg.cls)}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-current opacity-80" />
          <p className="text-sm font-bold text-slate-900">{cfg.label}</p>
        </div>
        <span className={clsx("shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold", cfg.badgeCls)}>
          {priorityLabel[priority] || "Priorité moyenne"}
        </span>
      </div>
      <p className="text-xs leading-5 text-slate-600 mb-1">{cfg.detail}</p>
      {action && <p className="text-xs leading-5 font-medium text-slate-800 mt-2 border-t border-slate-200/70 pt-2">{action}</p>}
    </div>
  );
}

function DecisionPanel({
  device,
  onAnalyze,
  analyzing,
  analysisError,
}: {
  device: Device;
  onAnalyze: () => void;
  analyzing: boolean;
  analysisError: string | null;
}) {
  const analysis = (device as any).decision_analysis as Record<string, any> | null;
  const analyzedAt = (device as any).decision_analyzed_at as string | null;

  if (!analysis) {
    return (
      <div className="rounded-[24px] border border-violet-200 bg-gradient-to-br from-violet-50 to-purple-50 p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-violet-100 text-violet-700">
            <Brain className="h-4 w-4" />
          </span>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-violet-500">Analyse décisionnelle IA</p>
            <p className="text-sm font-semibold text-violet-900">Aider à décider vite</p>
          </div>
        </div>
        <p className="text-xs leading-5 text-violet-700 mb-1">
          Go / No-go · Pourquoi intéressant · Points de vigilance · Effort estimé · Action conseillée.
        </p>
        <p className="text-[11px] text-violet-500 mb-4">Généré par IA en quelques secondes à partir de la fiche.</p>
        {analysisError && (
          <div className="mb-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{analysisError}</div>
        )}
        <button
          type="button"
          onClick={onAnalyze}
          disabled={analyzing}
          className="w-full flex items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-violet-700 disabled:opacity-60"
        >
          {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
          {analyzing ? "Analyse en cours…" : "Analyser cette opportunité"}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <Brain className="h-4 w-4 text-violet-500" />
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-violet-500">Analyse IA</p>
        </div>
        {analyzedAt && (
          <p className="text-[10px] text-slate-400">{formatDateRelative(analyzedAt)}</p>
        )}
      </div>

      <GoNoGoCard
        goNoGo={analysis.go_no_go}
        priority={analysis.recommended_priority}
        action={analysis.recommended_action}
      />

      {/* Scores */}
      <div className="grid grid-cols-3 gap-2">
        <ScoreChip label="Éligibilité" score={analysis.eligibility_score ?? 50} />
        <ScoreChip label="Intérêt strat." score={analysis.strategic_interest ?? 50} />
        <LevelChip label="Urgence" level={analysis.urgency_level ?? "moyenne"} />
        <LevelChip label="Difficulté" level={analysis.difficulty_level ?? "moyenne"} />
        <LevelChip label="Effort dossier" level={analysis.effort_level ?? "moyenne"} />
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
          <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-400">Confiance source</p>
          <p className="mt-0.5 text-sm font-bold text-slate-700">{device.confidence_score ?? 0}%</p>
          <ScoreBar score={device.confidence_score ?? 0} colorClass="bg-slate-400" />
        </div>
      </div>

      {/* Text sections */}
      {analysis.why_interesting && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3">
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-600 flex items-center gap-1">
            <TrendingUp className="h-3 w-3" /> Pourquoi c'est intéressant
          </p>
          <p className="text-xs leading-5 text-emerald-800">{analysis.why_interesting}</p>
        </div>
      )}

      {analysis.why_cautious && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-700 flex items-center gap-1">
            <AlertCircle className="h-3 w-3" /> Pourquoi être prudent
          </p>
          <p className="text-xs leading-5 text-amber-800">{analysis.why_cautious}</p>
        </div>
      )}

      {analysis.points_to_confirm && (
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500 flex items-center gap-1">
            <CheckSquare className="h-3 w-3" /> Points à confirmer
          </p>
          <p className="text-xs leading-5 text-slate-700">{analysis.points_to_confirm}</p>
        </div>
      )}

      {analysisError && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{analysisError}</div>
      )}

      <button
        type="button"
        onClick={onAnalyze}
        disabled={analyzing}
        className="w-full flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500 transition-colors hover:bg-slate-50 disabled:opacity-60"
      >
        {analyzing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
        {analyzing ? "Mise à jour…" : "Mettre à jour l'analyse"}
      </button>
    </div>
  );
}

// ─── Document manager ─────────────────────────────────────────────────────────

function DocumentManager({
  deviceId,
  documents,
  onDocumentsChange,
}: {
  deviceId: string;
  documents: PipelineDocument[];
  onDocumentsChange: (docs: PipelineDocument[]) => void;
}) {
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [note, setNote] = useState("");
  const [docType, setDocType] = useState<"url" | "note" | "brouillon">("url");
  const [saving, setSaving] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);

  const handleAdd = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const doc = await addPipelineDocument(deviceId, {
        name: name.trim(),
        url: url.trim() || null,
        doc_type: docType,
        note: note.trim() || null,
      });
      onDocumentsChange([...documents, doc]);
      setName(""); setUrl(""); setNote(""); setDocType("url");
      setShowForm(false);
    } catch {
      // silent
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (docId: string) => {
    setRemovingId(docId);
    try {
      await removePipelineDocument(deviceId, docId);
      onDocumentsChange(documents.filter((d) => d.id !== docId));
    } catch {
      // silent
    } finally {
      setRemovingId(null);
    }
  };

  const DOC_TYPE_LABELS: Record<string, string> = { url: "Lien", note: "Note", brouillon: "Brouillon" };
  const DOC_TYPE_COLORS: Record<string, string> = {
    url: "bg-blue-50 text-blue-700",
    note: "bg-amber-50 text-amber-700",
    brouillon: "bg-violet-50 text-violet-700",
  };

  return (
    <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800">
          <Paperclip className="h-3.5 w-3.5 text-slate-400" />
          Documents attachés
          {documents.length > 0 && (
            <span className="ml-1 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500">
              {documents.length}
            </span>
          )}
        </h3>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-primary-600 hover:bg-primary-50"
        >
          <Plus className="h-3 w-3" /> Ajouter
        </button>
      </div>

      {showForm && (
        <div className="mb-3 rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2">
          <div className="flex gap-2">
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value as "url" | "note" | "brouillon")}
              className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
            >
              <option value="url">Lien</option>
              <option value="note">Note</option>
              <option value="brouillon">Brouillon</option>
            </select>
            <input
              type="text"
              placeholder="Nom du document *"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="flex-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs placeholder:text-slate-400"
            />
          </div>
          {docType === "url" && (
            <input
              type="url"
              placeholder="URL (Drive, Dropbox…)"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs placeholder:text-slate-400"
            />
          )}
          {(docType === "note" || docType === "brouillon") && (
            <textarea
              placeholder="Contenu / note…"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs placeholder:text-slate-400 resize-none"
            />
          )}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleAdd}
              disabled={saving || !name.trim()}
              className="rounded-lg bg-primary-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
            >
              {saving ? "…" : "Enregistrer"}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="text-xs text-slate-500 hover:text-slate-700">
              Annuler
            </button>
          </div>
        </div>
      )}

      {documents.length === 0 && !showForm && (
        <p className="text-xs text-slate-400 italic">Aucun document attaché à cette candidature.</p>
      )}

      {documents.length > 0 && (
        <ul className="space-y-1.5">
          {documents.map((doc) => (
            <li key={doc.id} className="flex items-center gap-2 rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-1.5">
              <span className={clsx("shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold", DOC_TYPE_COLORS[doc.doc_type] || "bg-slate-100 text-slate-600")}>
                {DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}
              </span>
              <div className="flex-1 min-w-0">
                {doc.url ? (
                  <a href={doc.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 truncate text-xs font-medium text-primary-700 hover:underline">
                    <LinkIcon className="h-3 w-3 shrink-0" />
                    {doc.name}
                  </a>
                ) : (
                  <span className="truncate text-xs font-medium text-slate-700">{doc.name}</span>
                )}
                {doc.note && <p className="truncate text-[10px] text-slate-400">{doc.note}</p>}
              </div>
              <button
                type="button"
                onClick={() => handleRemove(doc.id)}
                disabled={removingId === doc.id}
                className="shrink-0 rounded p-0.5 text-slate-300 hover:text-red-400 disabled:opacity-40"
              >
                <X className="h-3 w-3" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

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
  const [rewriting, setRewriting] = useState(false);
  const [rewriteMsg, setRewriteMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [favorite, setFavorite] = useState(false);
  const [role, setRole] = useState<AppRole>("reader");
  const [pipelineStatus, setPipelineStatus] = useState<DevicePipelineStatus | "">("");
  const [pipelinePriority, setPipelinePriority] = useState<DevicePipelinePriority>("moyenne");
  const [pipelineReminderDate, setPipelineReminderDate] = useState("");
  const [pipelineMatchProjectId, setPipelineMatchProjectId] = useState("");
  const [pipelineNote, setPipelineNote] = useState("");
  const [pipelineFeedback, setPipelineFeedback] = useState<string | null>(null);
  const [pipelineDocuments, setPipelineDocuments] = useState<PipelineDocument[]>([]);
  const [matchSnapshot, setMatchSnapshot] = useState<MatchWorkspaceSnapshot | null>(null);
  const sourceView = searchParams.get("from");
  const cameFromMatch = sourceView === "match";
  const cameFromRecommendations = sourceView === "recommendations";
  const canModerate = canModerateDevices(role);
  const PIPELINE_LABELS: Record<DevicePipelineStatus, string> = {
    a_etudier: "A etudier",
    interessant: "Interessant",
    candidature_en_cours: "Candidature en cours",
    soumis: "Soumis",
    refuse: "Refuse",
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
          page_size: 5,
          status: "open",
          sort_by: "relevance",
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
    setPipelinePriority(tracked?.priority || "moyenne");
    setPipelineReminderDate(tracked?.reminderDate || "");
    setPipelineMatchProjectId(tracked?.matchProjectId || "");
    setPipelineNote(tracked?.note || "");
    setPipelineDocuments(tracked?.documents || []);
    setMatchSnapshot(readLatestMatchSnapshot());
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
    if (!confirm("Rejeter cette opportunité ?")) return;
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

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setAnalysisError(null);
    try {
      const updated = await devices.analyze(id);
      setDevice(updated as Device);
    } catch (e: any) {
      setAnalysisError(e.message || "L'analyse IA a échoué. Réessayez.");
    } finally {
      setAnalyzing(false);
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

  const handleRewrite = async () => {
    setRewriting(true);
    setRewriteMsg(null);
    try {
      const updated = await devices.rewrite(id);
      setDevice(updated as Device);
      const status = (updated as Device).ai_rewrite_status;
      setRewriteMsg({
        type: status === "done" || status === "needs_review" ? "success" : "error",
        text: status === "done"
          ? "Fiche reformulée avec succès par l'IA."
          : status === "needs_review"
          ? "Reformulation effectuée — à relire (certains points à vérifier)."
          : "La reformulation a échoué. Vérifie que la fiche a des sections source.",
      });
    } catch (e: any) {
      setRewriteMsg({ type: "error", text: e.message || "Impossible de reformuler cette fiche." });
    } finally {
      setRewriting(false);
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
      setPipelineFeedback("Le suivi personnel a été effacé pour cette opportunité.");
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
      priority: pipelinePriority,
      reminderDate: pipelineReminderDate || null,
      matchProjectId: pipelineMatchProjectId || null,
      note: pipelineNote.trim(),
      documents: pipelineDocuments,
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
        <div className="py-20 text-center text-gray-400">Opportunité introuvable</div>
      </AppLayout>
    );
  }

  const daysLeft = device.close_date ? daysUntil(device.close_date) : null;
  const isClosingSoon = daysLeft !== null && daysLeft >= 0 && daysLeft <= 30;
  const hasRichContent = !!(device.full_description || device.eligibility_criteria || device.eligible_expenses);
  const hasEnrichedContent = !!(device.auto_summary || device.full_description || device.eligibility_criteria || device.eligible_expenses);
  const hero = TYPE_HERO[device.device_type] || TYPE_HERO.autre;
  const typeMeta = getUserDeviceTypeMeta(device.device_type);
  const natureBanner = getDeviceNatureBanner(device);
  const beneficiarySummary = device.beneficiaries?.length
    ? device.beneficiaries.map((item) => item.replace(/_/g, " ")).join(", ")
    : null;
  const structuredPresentation = getContentSection(device, "presentation");
  const structuredEligibility = getContentSection(device, "eligibility");
  const structuredFunding = getContentSection(device, "funding");
  const showShortDescription = !structuredPresentation && shouldDisplaySummary(device.short_description, device.full_description);
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
  const displayPresentationContent = sanitizeDisplayText(
    structuredPresentation || extractMarkdownSection(device.full_description || "", ["Presentation"]) || presentationContent,
  );
  const displayEligibilityContent = sanitizeDisplayText(structuredEligibility || eligibilityContent);
  const displayFundingContent = sanitizeDisplayText(structuredFunding || fundingContent);
  const hasDistinctFundingText =
    displayFundingContent && normalizeForComparison(displayFundingContent) !== normalizeForComparison(displayPresentationContent);
  const isInstitutionalSignal = isInstitutionalProjectDevice(device);
  const decisionBanner = getDecisionBanner(device, daysLeft);
  const decisionSummary = buildUserDecisionSummary(device, displayPresentationContent, displayFundingContent, daysLeft);
  const decisionPriority = getDecisionPriority(device, daysLeft);
  const effortLabel = getEffortLabel(device);
  const quickEligibility = isInstitutionalSignal
    ? "Non candidatable directement"
    : beneficiarySummary || getShortPreview(displayEligibilityContent, "Profil a confirmer sur la source officielle");
  const quickFunding = device.amount_max
    ? formatAmount(device.amount_max, device.currency)
    : isInstitutionalSignal
      ? "Financement institutionnel"
      : getShortPreview(displayFundingContent, "Montant a confirmer");
  const quickDeadline = device.close_date
    ? `${formatDate(device.close_date)}${daysLeft !== null && daysLeft >= 0 && !isInstitutionalSignal ? `, J-${daysLeft}` : ""}`
    : natureBanner?.label || (device.is_recurring || device.status === "recurring" ? "Permanent" : "Date non communiquee");
  const quickReason =
    device.relevance_label ||
    getShortPreview(displayPresentationContent || device.short_description || "", "Opportunite a examiner selon votre profil et votre calendrier.");
  const aiReadiness = getAiReadinessMeta(device);
  const smartActionHint =
    isInstitutionalSignal
      ? "Signal de veille : consulte la fiche projet pour comprendre le financement, mais ne la traite pas comme une candidature directe."
      : daysLeft !== null && daysLeft >= 0 && daysLeft <= 7
      ? `Attention : deadline proche, il reste ${daysLeft} jour${daysLeft > 1 ? "s" : ""}. Priorise cette aide si elle correspond à ton projet.`
      : device.ai_readiness_label === "pret_pour_recommandation_ia"
        ? "Bonne opportunité pour ton profil : ajoute-la à ton suivi pour décider plus vite."
        : device.amount_max
          ? "Conseil : le montant est indiqué. Compare-le à ton besoin réel avant de candidater."
          : "Astuce : ajoute cette opportunité à ton suivi pour la comparer avec d'autres financements.";
  const sourceActionLabel = isInstitutionalSignal ? "Consulter la fiche projet" : "Verifier la source";
  const sourceDetailActionLabel = isInstitutionalSignal ? "Ouvrir la fiche projet officielle" : "Ouvrir la source officielle";
  const sourceContextText = isInstitutionalSignal
    ? "Cette source presente le projet institutionnel. Elle ne contient pas forcement de formulaire de candidature."
    : "La demande ou la consultation detaillee se fait aupres de l'organisme source.";
  const primaryActionLabel = device.source_url
    ? "Consulter la source officielle"
    : pipelineStatus
      ? "Mettre a jour mon suivi"
      : "Ajouter à mon suivi";
  const recommendationNarrative = device.relevance_label || aiReadiness.detail;
  const showOperationalSidebar = canModerate || Boolean(pipelineStatus);
  const addToStudyPipeline = () => {
    setPipelineStatus("a_etudier");
    setPipelinePriority(pipelinePriority || "moyenne");
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
      pipelineStatus: "a_etudier",
      priority: pipelinePriority || "moyenne",
      reminderDate: pipelineReminderDate || null,
      matchProjectId: pipelineMatchProjectId || null,
      note: pipelineNote.trim(),
      documents: pipelineDocuments,
    });
    setPipelineFeedback("Ajouté au suivi de tes opportunités dans le statut À étudier.");
  };

  return (
    <AppLayout>
      <div className="max-w-5xl">
        <div className="mb-4 flex items-center justify-between">
          <button
            onClick={() => (cameFromRecommendations ? router.push("/recommendations") : cameFromMatch ? router.push("/match") : router.back())}
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
                <button
                  onClick={handleRewrite}
                  disabled={rewriting}
                  className="btn-secondary flex items-center gap-1.5 border-indigo-300 text-xs text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
                  title="Reformuler les sections avec l'IA"
                >
                  {rewriting ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Brain className="h-3 w-3" />}
                  {rewriting ? "Reformulation…" : "Reformuler IA"}
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

        {rewriteMsg && (
          <div
            className={clsx(
              "mb-4 flex items-start gap-2 rounded-xl border px-4 py-3 text-sm",
              rewriteMsg.type === "success" ? "border-indigo-200 bg-indigo-50 text-indigo-700" : "border-red-200 bg-red-50 text-red-700",
            )}
          >
            {rewriteMsg.type === "success" ? (
              <Brain className="mt-0.5 h-4 w-4 flex-shrink-0" />
            ) : (
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            )}
            <span>{rewriteMsg.text}</span>
          </div>
        )}

        <div className={clsx("mb-4 rounded-2xl bg-gradient-to-br p-5 text-white shadow-md", hero.from, hero.to)}>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/20 px-2.5 py-1 text-xs font-medium text-white backdrop-blur-sm">
              {typeMeta.label}
            </span>
            <span className="rounded-full bg-white/25 px-2.5 py-1 text-xs font-medium text-white">
              {STATUS_LABELS[device.status]}
            </span>
            <span className="hidden rounded-full bg-white/25 px-2.5 py-1 text-xs font-medium text-white" title={aiReadiness.detail}>
              {aiReadiness.label}
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
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-white/70">Opportunité de financement</p>
              <h1 className="mb-2 text-2xl font-bold leading-snug text-white">{device.title}</h1>
              <p className="mb-3 max-w-2xl text-sm leading-relaxed text-white/80">{typeMeta.short}</p>
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

        <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
          <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className={clsx("rounded-full border px-3 py-1 text-xs font-semibold", decisionPriority.className)}>
                  {decisionPriority.label}
                </span>
                <span className={clsx("rounded-full border px-3 py-1 text-xs font-semibold", decisionBanner.className)}>
                  {decisionBanner.label}
                </span>
              </div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-500">Decision rapide</p>
              <p className="mt-2 max-w-3xl text-base font-semibold leading-7 text-slate-900">{quickReason}</p>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">{decisionBanner.detail}</p>
            </div>

            <div className="flex shrink-0 flex-col gap-2 sm:flex-row lg:w-64 lg:flex-col">
              {device.source_url ? (
                <a
                  href={device.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-primary-700"
                >
                  <ExternalLink className="h-4 w-4" />
                  {sourceActionLabel}
                </a>
              ) : (
                <button
                  type="button"
                  onClick={addToStudyPipeline}
                  className="flex items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-primary-700"
                >
                  <Flag className="h-4 w-4" />
                  Ajouter au suivi
                </button>
              )}
              <button type="button" onClick={addToStudyPipeline} className="btn-secondary justify-center text-xs">
                <Flag className="h-3.5 w-3.5" />
                Ajouter au suivi
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Eligibilite</p>
              <p className="mt-1 line-clamp-2 text-sm font-semibold leading-5 text-slate-900">{quickEligibility}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Montant</p>
              <p className="mt-1 line-clamp-2 text-sm font-semibold leading-5 text-slate-900">{quickFunding}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Echeance</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">{quickDeadline}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Effort</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">{effortLabel}</p>
            </div>
          </div>

          {(device.relevance_reasons?.length || device.decision_analysis?.points_to_confirm || hasDistinctFundingText) && (
            <div className="mt-5 grid gap-3 lg:grid-cols-3">
              {device.relevance_reasons?.slice(0, 2).map((reason) => (
                <div key={reason} className="rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm leading-6 text-emerald-900">
                  {reason}
                </div>
              ))}
              {device.decision_analysis?.points_to_confirm && (
                <div className="rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
                  {device.decision_analysis.points_to_confirm}
                </div>
              )}
              {hasDistinctFundingText && (
                <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-600">
                  {getShortPreview(displayFundingContent, "Les avantages doivent etre confirmes sur la source officielle.")}
                </div>
              )}
            </div>
          )}
        </section>

        <section className="hidden">
          <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr] lg:items-start">
            <div className="space-y-4">
              <div className={clsx("inline-flex items-start gap-2 rounded-2xl border px-4 py-3", decisionBanner.className)}>
                <Info className="mt-0.5 h-4 w-4 shrink-0" />
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em]">{decisionBanner.label}</p>
                  <p className="mt-1 text-sm leading-6">{decisionBanner.detail}</p>
                </div>
              </div>

              {device.relevance_label ? (
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-900">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-700">Pourquoi cette opportunité ressort</p>
                  <p className="mt-1 text-sm font-semibold leading-6">{device.relevance_label}</p>
                  {device.relevance_reasons?.length ? (
                    <ul className="mt-2 space-y-1.5 text-sm leading-6">
                      {device.relevance_reasons.slice(0, 3).map((reason) => (
                        <li key={reason} className="flex items-start gap-2">
                          <span className="mt-2 h-1.5 w-1.5 rounded-full bg-emerald-500" />
                          <span>{reason}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}

              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-500">Lecture rapide</p>
                <p className="mt-2 text-sm leading-7 text-slate-600">{decisionSummary}</p>
              </div>

              <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Statut</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">{STATUS_LABELS[device.status] || device.status}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Date limite</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">
                    {device.close_date ? formatDate(device.close_date) : natureBanner?.label || (device.is_recurring ? "Permanent" : "Date non communiquee")}
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Montant</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">{device.amount_max ? formatAmount(device.amount_max, device.currency) : "A confirmer"}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Pays</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">{device.country}</p>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Type</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">{typeMeta.label}</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">{typeMeta.short}</p>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              {/* ── Panneau décisionnel IA ── */}
              {(canModerate || device.decision_analysis) && (
                <DecisionPanel
                  device={device}
                  onAnalyze={handleAnalyze}
                  analyzing={analyzing}
                  analysisError={analysisError}
                />
              )}

              {/* ── Actions rapides ── */}
              <div className="rounded-[24px] border border-primary-100 bg-primary-50/60 p-4">
                <p className="text-sm font-semibold text-slate-950 mb-1">Actions rapides</p>
                <div className={clsx("mb-3 rounded-2xl border px-3 py-3 text-xs leading-5", daysLeft !== null && daysLeft >= 0 && daysLeft <= 7 ? "border-orange-200 bg-orange-50 text-orange-800" : "border-primary-100 bg-white text-primary-800")}>
                  {smartActionHint}
                </div>
                {device.source_url ? (
                  <a
                    href={device.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-primary-700"
                  >
                    <ExternalLink className="h-4 w-4" />
                    {isInstitutionalSignal ? "Consulter la fiche projet" : "Accéder au dispositif officiel"}
                  </a>
                ) : (
                  <button
                    type="button"
                    onClick={addToStudyPipeline}
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-primary-700"
                  >
                    <Flag className="h-4 w-4" />
                    Ajouter à mon suivi
                  </button>
                )}
                <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-1">
                  <button type="button" onClick={addToStudyPipeline} className="btn-secondary justify-center text-xs">
                    <Flag className="h-3.5 w-3.5" />
                    Ajouter à mon suivi
                  </button>
                  <Link href={`/alerts?device=${device.id}`} className="btn-secondary justify-center text-xs">
                    <Bell className="h-3.5 w-3.5" />
                    Créer une alerte similaire
                  </Link>
                </div>
              </div>

              {/* ── Accompagnement premium ── */}
              <div className="rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 to-orange-50 px-4 py-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-amber-600 mb-1">Service premium</p>
                <p className="text-sm font-semibold text-slate-800 mb-0.5">{isInstitutionalSignal ? "Besoin d'analyser ce signal ?" : "Besoin d'aide pour candidater ?"}</p>
                <p className="text-xs leading-5 text-slate-500 mb-3">
                  Un expert vous accompagne de la constitution du dossier jusqu'à l'obtention du financement.
                </p>
                <a
                  href="mailto:contact@kafundo.com"
                  className="flex w-full items-center justify-center gap-2 rounded-xl bg-amber-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-amber-600"
                >
                  <Sparkles className="h-4 w-4" />
                  Se faire accompagner
                </a>
              </div>
            </div>
          </div>
        </section>

        <div className="hidden">
          <InsightCard
            label="Date limite"
            value={device.close_date ? formatDate(device.close_date) : natureBanner?.label || (device.status === "recurring" ? "Financement recurrent" : "Date non communiquee")}
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
            value={typeMeta.label}
            icon={Tag}
          />
        </div>

        <div className={clsx("mb-6 grid grid-cols-1 gap-4", showOperationalSidebar && "md:grid-cols-3")}>
          <div className={clsx("space-y-4", showOperationalSidebar && "md:col-span-2")}>
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

            {(device.short_description || displayPresentationContent) && (
              <CollapsibleSection title="Presentation" icon={FileText} defaultOpen>
                {showShortDescription && device.short_description && <SectionField content={device.short_description} />}
                {displayPresentationContent && <SectionField content={displayPresentationContent} />}
              </CollapsibleSection>
            )}

            {(beneficiarySummary || displayEligibilityContent) && (
              <CollapsibleSection title="Conditions" icon={CheckCircle} defaultOpen>
                {beneficiarySummary && (
                  <SectionField
                    eyebrow="À qui s'adresse cette opportunité ?"
                    title="Entreprises éligibles"
                    content={beneficiarySummary}
                  />
                )}
                {displayEligibilityContent && (
                  <SectionField
                    title="Critères d'éligibilité"
                    content={displayEligibilityContent}
                  />
                )}
              </CollapsibleSection>
            )}

            {(projectContent || device.specific_conditions || hasDistinctFundingText) && (
              <CollapsibleSection title="Projet, montant et avantages" icon={Tag}>
                {showEligibleExpenses && projectContent && (
                  <SectionField
                    title="Dépenses concernées"
                    content={projectContent}
                  />
                )}
                {hasDistinctFundingText && <SectionField title="Montant / avantages" content={displayFundingContent} />}
                {device.specific_conditions && <SectionField title="Quelles sont les particularités ?" content={device.specific_conditions} />}
              </CollapsibleSection>
            )}

            {(device.required_documents || device.source_url || (device as any).recurrence_notes) && (
              <CollapsibleSection title="Demarche et source officielle" icon={Info}>
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
                      {sourceContextText}
                    </p>
                    <a
                      href={device.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 text-sm font-medium text-primary-700 hover:text-primary-800"
                    >
                      <ExternalLink className="h-4 w-4" />
                      {sourceDetailActionLabel}
                    </a>
                  </div>
                )}
              </CollapsibleSection>
            )}
          </div>

          {showOperationalSidebar && (
          <div className="space-y-4">
            {device.source_url && (
              <a
                href={device.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-primary-700"
              >
                <ExternalLink className="h-4 w-4" />
                {isInstitutionalSignal ? "Consulter le projet" : "Accéder au financement"}
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

            {canModerate && (
            <div className="card p-4">
              <h2 className="mb-3 flex items-center gap-1.5 text-sm font-semibold text-gray-700">
                <Info className="h-3.5 w-3.5 text-gray-400" />
                Qualité
              </h2>
              <div className="space-y-2.5">
                {[
                  { label: "Fiabilité", value: device.confidence_score },
                  { label: "Complétude", value: device.completeness_score },
                  { label: "Ciblage", value: device.relevance_score },
                  { label: "Lisibilite", value: device.ai_readiness_score ?? 0 },
                ].map(({ label, value }, index) => (
                  <div key={`${label}-${index}`}>
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
            )}

            {canModerate && device.keywords?.length ? (
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
              {(pipelineStatus || canModerate) && (
              <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                <div className="mb-3 flex items-center gap-2">
                  <Flag className="h-4 w-4 text-primary-600" />
                  <h2 className="text-sm font-semibold text-slate-900">Suivi personnel</h2>
                </div>
                <div className="space-y-3">
                  <div>
                    <label className="mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                      Statut de suivi
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
                      <option value="interessant">Intéressant</option>
                      <option value="candidature_en_cours">Candidature en cours</option>
                      <option value="soumis">Soumis</option>
                      <option value="refuse">Refusé</option>
                      <option value="non_pertinent">Non pertinent</option>
                    </select>
                  </div>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div>
                      <label className="mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                        Priorité
                      </label>
                      <select
                        value={pipelinePriority}
                        onChange={(e) => {
                          setPipelinePriority(e.target.value as DevicePipelinePriority);
                          setPipelineFeedback(null);
                        }}
                        className="input text-sm"
                      >
                        <option value="faible">Faible</option>
                        <option value="moyenne">Moyenne</option>
                        <option value="haute">Haute</option>
                      </select>
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                        Date de rappel
                      </label>
                      <input
                        type="date"
                        value={pipelineReminderDate}
                        onChange={(e) => {
                          setPipelineReminderDate(e.target.value);
                          setPipelineFeedback(null);
                        }}
                        className="input text-sm"
                      />
                    </div>
                  </div>
                  {matchSnapshot?.id && (
                    <div>
                      <label className="mb-1 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                        Projet lié
                      </label>
                      <select
                        value={pipelineMatchProjectId}
                        onChange={(e) => {
                          setPipelineMatchProjectId(e.target.value);
                          setPipelineFeedback(null);
                        }}
                        className="input text-sm"
                      >
                        <option value="">Aucun projet lié</option>
                        <option value={matchSnapshot.id}>{matchSnapshot.fileName || "Dernière analyse de projet"}</option>
                      </select>
                    </div>
                  )}
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
                          setPipelinePriority("moyenne");
                          setPipelineReminderDate("");
                          setPipelineMatchProjectId("");
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
              )}

              {/* ── Documents attachés (visible si le device est dans le pipeline) ── */}
              {pipelineStatus && (
                <DocumentManager
                  deviceId={id}
                  documents={pipelineDocuments}
                  onDocumentsChange={setPipelineDocuments}
                />
              )}

              {canModerate && hasEnrichedContent && (
                <div className="mb-4 rounded-2xl border border-primary-100 bg-primary-50/60 p-4">
                  <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-primary-800">
                    <CheckCircle className="h-4 w-4" />
                    Source de vérité
                  </h2>
                  <div className="space-y-2 text-sm text-slate-700">
                    <p className="font-medium text-primary-700">
                      {device.ai_rewrite_status === "done" ? "Texte reformule automatiquement" : "Texte enrichi automatiquement"}
                    </p>
                    {device.last_verified_at && (
                      <p>
                        Dernière vérification : <span className="font-medium">{formatDate(device.last_verified_at)}</span>{" "}
                        <span className="text-slate-500">({formatDateRelative(device.last_verified_at)})</span>
                      </p>
                    )}
                    {device.ai_rewrite_checked_at && (
                      <p>
                        DerniÃ¨re reformulation : <span className="font-medium">{formatDate(device.ai_rewrite_checked_at)}</span>
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
          )}
        </div>

        {similar.length > 0 && (
          <div className="mb-6">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h2 className="flex items-center gap-2 text-base font-semibold text-gray-700">
                <ArrowRight className="h-4 w-4 text-primary-400" />
                Opportunités similaires
              </h2>
              {similar.some((item) => item.relevance_label) && (
                <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                  Triées par pertinence pour ton profil
                </span>
              )}
            </div>
            {similar.some((item) => item.relevance_score > 0) && (
              <p className="mb-3 text-sm text-slate-500">
                {similar.filter((item) => item.relevance_score > device.relevance_score).length > 0
                  ? `${similar.filter((item) => item.relevance_score > device.relevance_score).length} dispositif(s) proche(s) ont un meilleur score de pertinence que cette fiche pour ton profil.`
                  : "Ces opportunités sont proches de celle-ci par type et pays."}
              </p>
            )}
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
