import DevicesPageContent from "@/components/DevicesPageContent";

// Types publics : tout sauf 'investissement'
const PUBLIC_TYPES = ["subvention", "pret", "aap", "accompagnement", "garantie", "concours", "autre"];

export default function PublicDevicesPage() {
  return (
    <DevicesPageContent
      title="Opportunités publiques à prioriser"
      lockedDeviceTypes={PUBLIC_TYPES}
      availableDeviceTypes={PUBLIC_TYPES}
      defaultSort="relevance"
      showClosingFilter={true}
      actionableNow={true}
      introTitle="Une sélection exploitable, pas tout le catalogue"
      introText="Par défaut, Kafundo masque les fiches trop ambiguës et affiche seulement les opportunités ouvertes, récurrentes ou avec une date fiable."
    />
  );
}
