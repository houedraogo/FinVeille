import DevicesPageContent from "@/components/DevicesPageContent";

// Types publics : tout sauf 'investissement'
const PUBLIC_TYPES = ["subvention", "pret", "aap", "accompagnement", "garantie", "concours", "autre"];

export default function PublicDevicesPage() {
  return (
    <DevicesPageContent
      title="Dispositifs de financement public"
      lockedDeviceTypes={PUBLIC_TYPES}
      availableDeviceTypes={PUBLIC_TYPES}
      defaultSort="updated_at"
      showClosingFilter={true}
    />
  );
}
