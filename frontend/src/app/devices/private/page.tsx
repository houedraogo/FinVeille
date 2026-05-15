import DevicesPageContent from "@/components/DevicesPageContent";

export default function PrivateDevicesPage() {
  return (
    <DevicesPageContent
      title="Fonds & investisseurs a prioriser"
      lockedDeviceTypes={["investissement"]}
      availableDeviceTypes={[]}
      defaultSort="amount_max"
      showClosingFilter={false}
      actionableNow={true}
    />
  );
}
