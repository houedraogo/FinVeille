import { DEVICE_TYPE_COLORS } from "@/lib/types";

export const USER_DEVICE_TYPE_META: Record<string, { label: string; short: string; decision: string; color: string }> = {
  subvention: {
    label: "Subvention",
    short: "Aide financière non remboursable, souvent liée à des critères précis.",
    decision: "À regarder en priorité si ton projet correspond aux critères.",
    color: DEVICE_TYPE_COLORS.subvention,
  },
  pret: {
    label: "Prêt public",
    short: "Financement remboursable, parfois avec conditions avantageuses.",
    decision: "À comparer avec ton besoin de trésorerie et ta capacité de remboursement.",
    color: DEVICE_TYPE_COLORS.pret,
  },
  avance_remboursable: {
    label: "Avance remboursable",
    short: "Financement à rembourser selon les modalités prévues par l’organisme.",
    decision: "Utile si tu peux absorber un remboursement différé ou conditionné.",
    color: DEVICE_TYPE_COLORS.avance_remboursable,
  },
  garantie: {
    label: "Garantie",
    short: "Mécanisme qui facilite l’accès à un prêt ou réduit le risque pour un financeur.",
    decision: "Pertinent si tu cherches à sécuriser un financement bancaire.",
    color: DEVICE_TYPE_COLORS.garantie,
  },
  credit_impot: {
    label: "Crédit d’impôt",
    short: "Avantage fiscal à mobiliser après ou pendant des dépenses éligibles.",
    decision: "À vérifier avec ton expert-comptable avant de l’intégrer au plan de financement.",
    color: DEVICE_TYPE_COLORS.credit_impot,
  },
  exoneration: {
    label: "Exonération",
    short: "Réduction ou suppression de charges, taxes ou impôts sous conditions.",
    decision: "Intéressant si ton activité entre dans le périmètre géographique ou sectoriel.",
    color: DEVICE_TYPE_COLORS.exoneration,
  },
  aap: {
    label: "Appel à projets",
    short: "Fenêtre de candidature avec date limite, dossier et sélection.",
    decision: "À prioriser si la deadline est proche et que le dossier est réaliste.",
    color: DEVICE_TYPE_COLORS.aap,
  },
  appel_a_projets: {
    label: "Appel à projets",
    short: "Fenêtre de candidature avec date limite, dossier et sélection.",
    decision: "À prioriser si la deadline est proche et que le dossier est réaliste.",
    color: DEVICE_TYPE_COLORS.aap,
  },
  ami: {
    label: "Appel à manifestation",
    short: "Phase d’identification ou de pré-sélection, souvent avant un appel complet.",
    decision: "Utile pour se positionner tôt, même si le financement n’est pas encore final.",
    color: DEVICE_TYPE_COLORS.ami,
  },
  accompagnement: {
    label: "Accompagnement",
    short: "Programme d’appui, mentorat, incubation, accélération ou expertise.",
    decision: "Pertinent si tu cherches du réseau, de la méthode ou une préparation au financement.",
    color: DEVICE_TYPE_COLORS.accompagnement,
  },
  concours: {
    label: "Concours",
    short: "Sélection compétitive avec prix, visibilité, mentorat ou dotation.",
    decision: "À tenter si ton projet est différenciant et que le temps de candidature reste raisonnable.",
    color: DEVICE_TYPE_COLORS.concours,
  },
  investissement: {
    label: "Investissement",
    short: "Capital, quasi-fonds propres ou prise de participation par un investisseur.",
    decision: "À étudier si tu es prêt à ouvrir ton capital ou discuter avec des investisseurs.",
    color: DEVICE_TYPE_COLORS.investissement,
  },
  institutional_project: {
    label: "Projet institutionnel",
    short: "Projet porté par une institution, souvent informatif plutôt qu’un appel direct.",
    decision: "À utiliser comme signal de marché, pas comme candidature immédiate sauf indication claire.",
    color: "bg-slate-200 text-slate-800",
  },
  autre: {
    label: "À qualifier",
    short: "La source ne permet pas encore de classer clairement la nature du financement.",
    decision: "À ouvrir avec prudence et confirmer sur la source officielle.",
    color: DEVICE_TYPE_COLORS.autre,
  },
};

export function getUserDeviceTypeMeta(deviceType?: string | null) {
  const key = deviceType || "autre";
  return USER_DEVICE_TYPE_META[key] || {
    label: key || "À qualifier",
    short: "Nature du financement à confirmer.",
    decision: "Vérifie la source officielle avant de décider.",
    color: DEVICE_TYPE_COLORS.autre,
  };
}
