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

export function hasReliableCloseDate(
  device: Pick<Device, "close_date" | "status" | "is_recurring" | "tags">,
): boolean {
  if (!device.close_date) return false;

  const tags = new Set((device.tags || []).map((tag) => String(tag).toLowerCase()));
  const nonClassicDeadline =
    device.is_recurring ||
    device.status === "recurring" ||
    device.status === "standby" ||
    tags.has("deadline:permanent") ||
    tags.has("deadline:institutional_project") ||
    tags.has("deadline:not_communicated");

  if (nonClassicDeadline) return false;

  return (
    device.status === "open" ||
    device.status === "expired" ||
    device.status === "closed" ||
    tags.has("deadline:verified_from_raw") ||
    tags.has("deadline:known") ||
    tags.has("deadline:expired")
  );
}

export function getDeadlineDisplay(
  device: Pick<Device, "title" | "organism" | "source_url" | "status" | "is_recurring" | "close_date" | "device_type" | "tags">,
) {
  const nature = getDeviceNatureBanner(device);
  const hasDeadline = hasReliableCloseDate(device);
  const daysLeft = hasDeadline && device.close_date ? daysUntil(device.close_date) : null;
  const isClosingSoon = device.status === "open" && daysLeft !== null && daysLeft >= 0 && daysLeft <= 30;

  if (hasDeadline && device.close_date) {
    const label = formatDate(device.close_date);
    return {
      hasDeadline,
      date: device.close_date,
      label,
      shortLabel: label,
      daysLeft,
      isClosingSoon,
      accent: true,
    };
  }

  const label =
    nature?.label ||
    (device.is_recurring || device.status === "recurring"
      ? "Financement récurrent"
      : "Date non communiquée");

  return {
    hasDeadline: false,
    date: null,
    label,
    shortLabel: label,
    daysLeft: null,
    isClosingSoon: false,
    accent: false,
  };
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
    .replace(/([A-Za-zÀ-ž0-9,;:])\n{1,2}(?=[a-zà-ž])/g, "$1 ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// Jours de montage estimés par type de dispositif (heuristique)
const EFFORT_DAYS: Record<string, number> = {
  aap: 4,
  concours: 4,
  investissement: 3,
  ami: 2.5,
  pret: 2,
  avance_remboursable: 2,
  subvention: 1.5,
  garantie: 1.5,
  accompagnement: 1,
  credit_impot: 0.5,
  exoneration: 0.5,
  autre: 2,
};

export function estimateEffort(deviceType: string): string {
  const days = EFFORT_DAYS[deviceType] ?? 2;
  if (days <= 0.5) return "< 1 jour";
  if (days <= 1) return "~1 jour";
  if (days <= 1.5) return "~1-2 jours";
  if (days <= 2.5) return "~2 jours";
  if (days <= 3) return "~2-3 jours";
  return "~3-5 jours";
}

// ---------------------------------------------------------------------------
// Score intelligence
// ---------------------------------------------------------------------------

export interface ScoreLabel {
  label: string;
  sublabel: string;
  color: string;
  bg: string;
}

export function scoreLabel(score: number): ScoreLabel {
  if (score >= 80) return { label: "Excellent fit", sublabel: "Fiabilité très élevée", color: "text-emerald-700", bg: "bg-emerald-50" };
  if (score >= 65) return { label: "Très bon fit avec votre profil", sublabel: "Fiabilité élevée", color: "text-green-700", bg: "bg-green-50" };
  if (score >= 50) return { label: "Bonne pertinence — à explorer", sublabel: "Quelques points à vérifier", color: "text-blue-700", bg: "bg-blue-50" };
  if (score >= 35) return { label: "Pertinence moyenne — à analyser", sublabel: "Vérifiez les critères", color: "text-yellow-700", bg: "bg-yellow-50" };
  if (score >= 20) return { label: "Faible probabilité de succès", sublabel: "Données partielles", color: "text-orange-700", bg: "bg-orange-50" };
  return { label: "Peu adapté à ce stade", sublabel: "Données insuffisantes", color: "text-red-700", bg: "bg-red-50" };
}

export interface ScorePoint {
  ok: boolean;
  label: string;
}

export function buildScoreExplanation(device: {
  status?: string;
  confidence_score?: number;
  sectors?: string[] | null;
  amount_max?: number | null;
  eligibility_criteria?: string | null;
  close_date?: string | null;
  required_documents?: string | null;
}): ScorePoint[] {
  return [
    { ok: device.status === "open", label: "Dispositif actuellement ouvert" },
    { ok: (device.confidence_score ?? 0) >= 70, label: "Fiabilité des données élevée" },
    { ok: Boolean(device.sectors?.length), label: "Secteurs identifiés" },
    { ok: Boolean(device.amount_max), label: "Montant d'aide précisé" },
    { ok: Boolean(device.eligibility_criteria), label: "Critères d'éligibilité détaillés" },
    { ok: Boolean(device.close_date), label: "Date de clôture connue" },
    { ok: Boolean(device.required_documents), label: "Documents requis précisés" },
  ];
}

const AI_RECO: Record<string, string> = {
  aap: "Recommandé si vous avez un projet mature prêt à déposer. Les AAP sont compétitifs — préparez votre dossier complet en amont.",
  ami: "Intéressant pour tester l'intérêt d'un partenaire public avant de s'engager dans un dossier lourd.",
  subvention: "Idéal pour financer des dépenses immédiates. Vérifiez l'adéquation avec vos critères d'éligibilité.",
  pret: "Adapté si vous avez besoin de liquidités à moyen terme. Comparez les conditions avec votre banque habituelle.",
  avance_remboursable: "Solution intermédiaire entre subvention et prêt — à privilégier si votre projet génère du CA rapidement.",
  garantie: "Utile pour sécuriser un emprunt bancaire. Combinable avec d'autres dispositifs de financement.",
  credit_impot: "À anticiper avec votre expert-comptable. L'assiette de dépenses éligibles doit être documentée avec précision.",
  exoneration: "Avantage fiscal automatique si vous êtes éligible — vérifiez votre statut avec un conseiller fiscal.",
  accompagnement: "Valeur ajoutée non financière : réseau, expertise, visibilité. Idéal en complément d'une aide financière.",
  concours: "Fort ROI en cas de victoire. Investissement en temps limité si candidature bien préparée.",
  investissement: "Convient aux entreprises en forte croissance cherchant un partenaire actionnaire ou co-investisseur.",
  autre: "Analysez les conditions spécifiques avec votre conseiller en financement.",
};

export function aiRecommendation(deviceType: string, daysLeft?: number | null): string {
  const base = AI_RECO[deviceType] ?? AI_RECO["autre"];
  if (daysLeft != null && daysLeft <= 14) {
    return `⚠️ Clôture dans ${daysLeft} jour${daysLeft > 1 ? "s" : ""} — agissez rapidement. ${base}`;
  }
  return base;
}

export function avgEffortFromTypes(byType: { type: string; count: number }[]): string {
  let totalDays = 0;
  let totalCount = 0;
  for (const { type, count } of byType) {
    totalDays += (EFFORT_DAYS[type] ?? 2) * count;
    totalCount += count;
  }
  if (totalCount === 0) return "~2 jours";
  const avg = totalDays / totalCount;
  if (avg <= 0.75) return "< 1 jour";
  if (avg <= 1.75) return "~1-2 jours";
  if (avg <= 2.75) return "~2-3 jours";
  return "~3-5 jours";
}

export interface DeviceNatureBanner {
  kind: "open_call" | "recurring" | "institutional_project" | "missing_close_date" | "investor";
  label: string;
  detail: string;
}

export interface AiReadinessMeta {
  label: string;
  detail: string;
  className: string;
}

export function getAiReadinessMeta(device: Pick<Device, "ai_readiness_label" | "ai_readiness_score">): AiReadinessMeta {
  const score = device.ai_readiness_score ?? 0;
  const metas: Record<string, AiReadinessMeta> = {
    pret_pour_recommandation_ia: {
      label: "Très recommandé",
      detail: `Très bonne opportunité pour ton profil. Pertinence : ${score}%.`,
      className: "border-emerald-200 bg-emerald-50 text-emerald-700",
    },
    utilisable_avec_prudence: {
      label: "À confirmer",
      detail: `Opportunité intéressante, mais certaines informations doivent être confirmées. Pertinence : ${score}%.`,
      className: "border-amber-200 bg-amber-50 text-amber-800",
    },
    a_verifier: {
      label: "À vérifier",
      detail: `À vérifier avant de la considérer comme prioritaire. Pertinence : ${score}%.`,
      className: "border-orange-200 bg-orange-50 text-orange-800",
    },
    non_exploitable: {
      label: "Non recommandé",
      detail: `Informations insuffisantes pour recommander cette opportunité. Pertinence : ${score}%.`,
      className: "border-red-200 bg-red-50 text-red-700",
    },
  };

  return metas[device.ai_readiness_label || ""] || {
    label: "Pertinence à calculer",
    detail: "La pertinence de cette opportunité n'a pas encore été calculée.",
    className: "border-slate-200 bg-slate-50 text-slate-600",
  };
}

export function getDeviceNatureBanner(
  device: Pick<Device, "title" | "organism" | "source_url" | "status" | "is_recurring" | "close_date" | "device_type" | "tags">,
): DeviceNatureBanner | null {
  const sourceContext = `${device.organism} ${device.title} ${device.source_url}`.toLowerCase();
  const tags = new Set((device.tags || []).map((tag) => String(tag).toLowerCase()));
  const looksInstitutionalProject =
    /(world bank|banque mondiale|ifc|african development bank|banque africaine|european investment bank|commission européenne|commission europeenne|cordis)/i.test(
      sourceContext,
    ) && /\b(project|projet|programme|program|operation|facility|initiative)\b/i.test(sourceContext);

  if (device.device_type === "investissement") {
    return {
      kind: "investor",
      label: "Investisseur / fonds",
      detail: "Il s'agit d'un financeur à contacter ou à qualifier, pas d'un appel avec date limite unique.",
    };
  }

  if (device.is_recurring || device.status === "recurring" || tags.has("deadline:permanent")) {
    return {
      kind: "recurring",
      label: "Financement permanent",
      detail: "Cette opportunité fonctionne sans date limite unique ou selon un rythme récurrent.",
    };
  }

  if (looksInstitutionalProject || tags.has("deadline:institutional_project")) {
    return {
      kind: "institutional_project",
      label: "Projet institutionnel",
      detail: "Il s'agit d'un programme porté par une institution, et non d'un appel à candidatures classique.",
    };
  }

  if (device.status === "open" && hasReliableCloseDate(device)) {
    return {
      kind: "open_call",
      label: "Appel en cours",
      detail: `La source indique une clôture au ${formatDate(device.close_date as string)}.`,
    };
  }

  if (!device.close_date && (device.status === "open" || device.status === "standby" || tags.has("deadline:not_communicated"))) {
    return {
      kind: "missing_close_date",
      label: "Date limite non communiquée",
      detail: "La source officielle ne publie pas de date limite exploitable. À confirmer avant de prioriser cette opportunité.",
    };
  }

  return null;
}
