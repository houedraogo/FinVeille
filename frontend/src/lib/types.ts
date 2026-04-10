export interface Device {
  id: string;
  slug: string | null;
  title: string;
  organism: string;
  country: string;
  region: string | null;
  zone: string | null;
  device_type: string;
  aid_nature: string | null;
  sectors: string[] | null;
  beneficiaries: string[] | null;
  short_description: string | null;
  full_description: string | null;
  eligibility_criteria: string | null;
  eligible_expenses: string | null;
  specific_conditions: string | null;
  required_documents: string | null;
  amount_min: number | null;
  amount_max: number | null;
  currency: string;
  funding_rate: number | null;
  open_date: string | null;
  close_date: string | null;
  is_recurring: boolean;
  status: string;
  source_url: string;
  source_id: string | null;
  language: string;
  keywords: string[] | null;
  tags: string[] | null;
  auto_summary: string | null;
  confidence_score: number;
  completeness_score: number;
  relevance_score: number;
  validation_status: string;
  first_seen_at: string;
  last_verified_at: string;
  created_at: string;
  updated_at: string;
}

export interface DeviceListResponse {
  items: Device[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Source {
  id: string;
  name: string;
  organism: string;
  country: string;
  region: string | null;
  source_type: string;
  category: "public" | "private";
  level: number;
  url: string;
  collection_mode: string;
  source_kind: SourceKind;
  check_frequency: string;
  reliability: number;
  is_active: boolean;
  last_checked_at: string | null;
  last_success_at: string | null;
  consecutive_errors: number;
  config: Record<string, unknown> | null;
  notes: string | null;
  last_error?: string | null;
  health_score: number;
  health_label: "excellent" | "bon" | "fragile" | "critique";
  created_at: string;
}

export type SourceKind =
  | "listing"
  | "single_program_page"
  | "pdf_manual"
  | "institutional_project";

export interface CollectionLog {
  id: string;
  source_id: string;
  started_at: string;
  ended_at: string | null;
  status: "running" | "success" | "partial" | "failed";
  items_found: number;
  items_new: number;
  items_updated: number;
  items_skipped: number;
  items_error: number;
  error_message: string | null;
  details: Record<string, unknown> | null;
}

export interface SourceTestResult {
  success: boolean;
  message: string;
  collection_mode: string;
  items_found: number;
  sample_titles: string[];
  sample_urls: string[];
  can_activate: boolean;
  preview?: {
    badge: string;
    source_kind: SourceKind;
    headline: string;
    summary: string;
    examples: string[];
  } | null;
}

export interface Alert {
  id: string;
  user_id: string;
  name: string;
  criteria: Record<string, unknown>;
  frequency: string;
  channels: string[];
  alert_types: string[];
  is_active: boolean;
  last_triggered_at: string | null;
  created_at: string;
}

export interface DashboardStats {
  total: number;
  total_active: number;
  new_last_7_days: number;
  closing_soon_30d: number;
  closing_soon_7d: number;
  pending_validation: number;
  avg_confidence: number;
  by_country: { country: string; count: number }[];
  by_type: { type: string; count: number }[];
  by_status: { status: string; count: number }[];
  recent_devices: Partial<Device>[];
  closing_soon: { id: string; title: string; country: string; close_date: string; days_left: number }[];
  sources: {
    active: number;
    in_error: number;
    errors: {
      id: string;
      name: string;
      country: string;
      is_active: boolean;
      consecutive_errors: number;
      last_checked_at: string | null;
      last_error: string | null;
    }[];
  };
  last_collection: { at: string | null; status: string | null; items_new: number };
}

export const SOURCE_MODE_LABELS: Record<string, string> = {
  api: "API",
  rss: "RSS",
  html: "HTML",
  dynamic: "JS",
  pdf: "PDF",
  manual: "Manuel",
};

export const SOURCE_FREQ_LABELS: Record<string, string> = {
  hourly: "Horaire",
  daily: "Quotidien",
  weekly: "Hebdo",
  monthly: "Mensuel",
};

export const SOURCE_KIND_LABELS: Record<SourceKind, string> = {
  listing: "Liste / portail",
  single_program_page: "Page unique programme",
  pdf_manual: "PDF manuel",
  institutional_project: "Projet institutionnel",
};

export const DEVICE_TYPE_LABELS: Record<string, string> = {
  subvention: "Subvention",
  pret: "Prêt public",
  avance_remboursable: "Avance remboursable",
  garantie: "Garantie",
  credit_impot: "Crédit d'impôt",
  exoneration: "Exonération",
  aap: "Appel à projets",
  ami: "Appel à manifestation",
  accompagnement: "Accompagnement",
  concours: "Concours",
  investissement: "Investissement / Capital",
  autre: "Autre",
};

export const DEVICE_TYPE_COLORS: Record<string, string> = {
  subvention:          "bg-emerald-100 text-emerald-800",
  pret:                "bg-blue-100 text-blue-800",
  avance_remboursable: "bg-cyan-100 text-cyan-800",
  garantie:            "bg-violet-100 text-violet-800",
  credit_impot:        "bg-orange-100 text-orange-800",
  exoneration:         "bg-yellow-100 text-yellow-800",
  aap:                 "bg-rose-100 text-rose-800",
  ami:                 "bg-pink-100 text-pink-800",
  accompagnement:      "bg-teal-100 text-teal-800",
  concours:            "bg-amber-100 text-amber-800",
  investissement:      "bg-purple-100 text-purple-800",
  autre:               "bg-gray-100 text-gray-600",
};

export const STATUS_LABELS: Record<string, string> = {
  open: "Ouvert",
  closed: "Fermé",
  recurring: "Récurrent",
  standby: "En veille",
  expired: "Expiré",
  unknown: "Inconnu",
};

export const STATUS_COLORS: Record<string, string> = {
  open: "bg-green-100 text-green-800",
  closed: "bg-red-100 text-red-800",
  recurring: "bg-blue-100 text-blue-800",
  standby: "bg-yellow-100 text-yellow-800",
  expired: "bg-gray-100 text-gray-500",
  unknown: "bg-gray-100 text-gray-500",
};
