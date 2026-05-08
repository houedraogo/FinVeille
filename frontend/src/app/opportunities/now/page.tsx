import DevicesPageContent from "@/components/DevicesPageContent";

const ACTIONABLE_TYPES = [
  "subvention",
  "pret",
  "aap",
  "accompagnement",
  "garantie",
  "concours",
  "investissement",
  "autre",
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
      introTitle="Une vue resserree sur les financements vraiment exploitables"
      introText="Cette selection masque les fiches trop ambigues et garde uniquement les opportunites ouvertes, recurrentes ou avec une date limite fiable."
    />
  );
}
