import DevicesPageContent from "@/components/DevicesPageContent";

// Types publics actionnables : tout sauf financement privé et projets institutionnels.
const PUBLIC_TYPES = [
  "subvention",
  "pret",
  "avance_remboursable",
  "garantie",
  "credit_impot",
  "exoneration",
  "aap",
  "appel_a_projets",
  "ami",
  "accompagnement",
  "concours",
];

export default function PublicDevicesPage() {
  return (
    <DevicesPageContent
      title="Opportunites publiques a prioriser"
      lockedDeviceTypes={PUBLIC_TYPES}
      availableDeviceTypes={PUBLIC_TYPES}
      defaultSort="relevance"
      showClosingFilter={true}
      actionableNow={true}
    />
  );
}
