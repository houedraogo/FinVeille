import DevicesPageContent from "@/components/DevicesPageContent";

// Types publics : tout sauf 'investissement'
const PUBLIC_TYPES = ["subvention", "pret", "aap", "accompagnement", "garantie", "concours"];

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
