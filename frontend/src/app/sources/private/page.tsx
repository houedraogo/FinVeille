import SourcesPageContent from "@/components/SourcesPageContent";

export default function PrivateSourcesPage() {
  return (
    <SourcesPageContent
      category="private"
      title="Sources — Financement privé"
      subtitle="Fonds d'investissement, investisseurs privés, capital-risque"
      defaultSourceType="fonds_prive"
    />
  );
}
