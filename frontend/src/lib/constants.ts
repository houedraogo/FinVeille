/**
 * Constantes partagées à travers l'application.
 * C'est ici qu'il faut ajouter/modifier les listes de pays et secteurs.
 */

export const COUNTRIES = [
  "France",
  "Sénégal",
  "Côte d'Ivoire",
  "Maroc",
  "Tunisie",
  "Cameroun",
  "Mali",
  "Burkina Faso",
  "Niger",
  "Togo",
  "Bénin",
  "Guinée",
  "Madagascar",
  "RD Congo",
  "Kenya",
  "Ghana",
  "Nigeria",
  "Éthiopie",
  "Afrique de l'Ouest",
  "Afrique",
] as const;

export const SECTORS = [
  "agriculture",
  "energie",
  "sante",
  "numerique",
  "education",
  "environnement",
  "industrie",
  "tourisme",
  "transport",
  "finance",
  "eau",
  "social",
  "culture",
  "immobilier",
] as const;

export type Country = (typeof COUNTRIES)[number];
export type Sector  = (typeof SECTORS)[number];
