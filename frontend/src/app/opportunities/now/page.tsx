import DevicesPageContent from "@/components/DevicesPageContent";

const ACTIONABLE_TYPES = [
  "subvention",
  "pret",
  "aap",
  "accompagnement",
  "garantie",
  "concours",
  "investissement",
];

export default function OpportunitiesNowPage() {
  return (
    <DevicesPageContent
      title="Opportunites a saisir maintenant"
      lockedDeviceTypes={ACTIONABLE_TYPES}
      availableDeviceTypes={ACTIONABLE_TYPES}
      defaultSort="close_date"
      showClosingFilter={true}
      actionableNow={true}
    />
  );
}
