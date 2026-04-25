import DevicesPageContent from "@/components/DevicesPageContent";

// Types publics : tout sauf 'investissement'
const PUBLIC_TYPES = ["subvention", "pret", "aap", "accompagnement", "garantie", "concours", "autre"];

export default function PublicDevicesPage() {
  return (
    <DevicesPageContent
      title="Opportunités de financement public"
      lockedDeviceTypes={PUBLIC_TYPES}
      availableDeviceTypes={PUBLIC_TYPES}
      defaultSort="relevance"
      showClosingFilter={true}
    />
  );
}
