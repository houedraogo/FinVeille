import { Suspense } from "react";
import DevicesPageContent from "@/components/DevicesPageContent";

export default function PrivateDevicesPage() {
  return (
    <Suspense>
      <DevicesPageContent
        title="Fonds & investisseurs à prioriser"
        lockedDeviceTypes={["investissement"]}
        availableDeviceTypes={[]}
        defaultSort="amount_max"
        showClosingFilter={false}
        actionableNow={true}
      />
    </Suspense>
  );
}
