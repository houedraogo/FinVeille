import DevicesPageContent from "@/components/DevicesPageContent";

export default function PrivateDevicesPage() {
  return (
    <DevicesPageContent
      title="Fonds & investisseurs à prioriser"
      lockedDeviceTypes={["investissement"]}
      availableDeviceTypes={[]}
      defaultSort="amount_max"
      showClosingFilter={false}
      actionableNow={true}
      introTitle="Une sélection investisseur exploitable"
      introText="Cette vue évite d'exposer tout le stock privé par défaut et garde les fonds permanents, récurrentiels ou suffisamment qualifiés."
    />
  );
}
