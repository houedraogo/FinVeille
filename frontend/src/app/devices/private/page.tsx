import DevicesPageContent from "@/components/DevicesPageContent";

export default function PrivateDevicesPage() {
  return (
    <DevicesPageContent
      title="Fonds & Investisseurs"
      lockedDeviceTypes={["investissement"]}
      availableDeviceTypes={[]}        // Le type est fixe, pas de filtre type
      defaultSort="amount_max"         // Tri par montant par défaut
      showClosingFilter={false}        // Les investisseurs n'ont pas de date de clôture
    />
  );
}
