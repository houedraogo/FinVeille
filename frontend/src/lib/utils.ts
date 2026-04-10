import { format, formatDistanceToNow, differenceInDays, parseISO } from "date-fns";
import { fr } from "date-fns/locale";
import type { Device } from "@/lib/types";

export function formatDate(dateStr: string): string {
  try {
    return format(parseISO(dateStr), "dd MMM yyyy", { locale: fr });
  } catch {
    return dateStr;
  }
}

export function formatDateRelative(dateStr: string): string {
  try {
    return formatDistanceToNow(parseISO(dateStr), { addSuffix: true, locale: fr });
  } catch {
    return dateStr;
  }
}

export function daysUntil(dateStr: string): number {
  try {
    return differenceInDays(parseISO(dateStr), new Date());
  } catch {
    return -1;
  }
}

export function formatAmount(amount: number | string | null | undefined, currency = "EUR"): string {
  if (amount === null || amount === undefined || amount === "") return "";
  const n = typeof amount === "string" ? parseFloat(amount) : amount;
  if (isNaN(n) || n === 0) return "";
  const symbols: Record<string, string> = { EUR: "\u20ac", XOF: " FCFA", MAD: " MAD", TND: " TND" };
  const symbol = symbols[currency] || ` ${currency}`;

  if (n >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(1).replace(".0", "")} M${symbol}`;
  }
  if (n >= 1_000) {
    return `${(n / 1_000).toFixed(0)} k${symbol}`;
  }
  return `${n.toFixed(0)}${symbol}`;
}

export function clsx(...classes: (string | undefined | null | boolean)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function sanitizeDisplayText(text: string | null | undefined): string {
  if (!text) return "";

  let value = String(text).trim();

  for (let i = 0; i < 3; i += 1) {
    const next = value
      .replace(/^\{?\s*['"]cdata!?['"]\s*:\s*(['"])([\s\S]*?)\1\s*\}?$/i, "$2")
      .replace(/['"]cdata!?['"]\s*:\s*(['"])([\s\S]*?)\1/i, "$2")
      .replace(/^\{?\s*['"]cdata!?['"]\s*:\s*['"]?/i, "")
      .replace(/['"}\s]+$/g, "")
      .trim();
    if (next === value) break;
    value = next;
  }

  value = value
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/p>\s*<p[^>]*>/gi, "\n\n")
    .replace(/<\/li>\s*<li[^>]*>/gi, "\n- ")
    .replace(/<li[^>]*>/gi, "- ")
    .replace(/<\/?(p|div|section|article|ul|ol|h1|h2|h3|h4|h5|h6)[^>]*>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/\\r\\n/g, "\n")
    .replace(/\\n/g, "\n")
    .replace(/\\t/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&eacute;/gi, "é")
    .replace(/&egrave;/gi, "è")
    .replace(/&ecirc;/gi, "ê")
    .replace(/&agrave;/gi, "à")
    .replace(/&ccedil;/gi, "ç")
    .replace(/&rsquo;/gi, "'")
    .replace(/&lsquo;/gi, "'")
    .replace(/&laquo;/gi, '"')
    .replace(/&raquo;/gi, '"');

  value = value
    .replace(/([^\n])\s*(##\s+)/g, "$1\n\n$2")
    .replace(/(:)\s*[-•]\s*/g, "$1\n- ")
    .replace(/([a-zàâçéèêëîïôûùüÿñæœ0-9])\s+(?=(?:Présentation|Conditions d'attribution|Critères d'éligibilité|Dépenses concernées|Informations pratiques|Quelle démarche à suivre|Auprès de quel organisme)\b)/gi, "$1\n\n")
    .replace(/([.!?])\s+(?=[A-ZÀÂÇÉÈÊËÎÏÔÛÙÜŸ][a-zàâçéèêëîïôûùüÿñæœ]{2,})/g, "$1\n")
    .replace(/\n-\s*/g, "\n- ");

  const sectionLabels = [
    "Description complémentaire",
    "Présentation du dispositif",
    "Présentation",
    "Conditions d'attribution",
    "Critères d'éligibilité",
    "Montants & Financement",
    "Dépenses concernées",
    "Informations pratiques",
    "Quelle démarche à suivre",
    "Auprès de quel organisme",
  ];

  for (const label of sectionLabels) {
    const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    value = value
      .replace(new RegExp(`(^|\\n)${escaped}\\s+(?=[A-ZÀÂÇÉÈÊËÎÏÔÛÙÜŸ0-9])`, "g"), `$1${label}\n\n`)
      .replace(new RegExp(`##\\s*${escaped}\\s+(?=[A-ZÀÂÇÉÈÊËÎÏÔÛÙÜŸ0-9])`, "g"), `## ${label}\n`);
  }

  return value
    .split("\n")
    .map((line) => line.replace(/[ \t]+/g, " ").trim())
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export interface DeviceNatureBanner {
  kind: "open_call" | "recurring" | "institutional_project" | "missing_close_date";
  label: string;
  detail: string;
}

export function getDeviceNatureBanner(device: Pick<Device, "title" | "organism" | "source_url" | "status" | "is_recurring" | "close_date">): DeviceNatureBanner | null {
  const sourceContext = `${device.organism} ${device.title} ${device.source_url}`.toLowerCase();
  const looksInstitutionalProject =
    /(world bank|banque mondiale|ifc|african development bank|banque africaine|european investment bank|commission européenne|commission europeenne|cordis)/i.test(
      sourceContext,
    ) && /\b(project|projet|programme|program|operation|facility|initiative)\b/i.test(sourceContext);

  if (device.is_recurring || device.status === "recurring") {
    return {
      kind: "recurring",
      label: "Dispositif permanent",
      detail: "Ce dispositif fonctionne sans fenêtre de clôture unique ou selon un rythme récurrent.",
    };
  }

  if (looksInstitutionalProject) {
    return {
      kind: "institutional_project",
      label: "Projet institutionnel",
      detail: "Il s'agit d'un programme porté par une institution, et non d'un appel à candidatures classique.",
    };
  }

  if (device.status === "open" && device.close_date) {
    return {
      kind: "open_call",
      label: "Appel en cours",
      detail: `La source indique une clôture au ${formatDate(device.close_date)}.`,
    };
  }

  if (device.status === "open" && !device.close_date) {
    return {
      kind: "missing_close_date",
      label: "Clôture non communiquée par la source",
      detail: "La source officielle ne précise pas de date limite exploitable à ce stade.",
    };
  }

  return null;
}
