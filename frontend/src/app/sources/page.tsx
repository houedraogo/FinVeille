import SourcesPageContent from "@/components/SourcesPageContent";

export default function PublicSourcesPage() {
  return (
    <SourcesPageContent
      category="public"
      title="Sources — Financement public"
      subtitle="Agences publiques, institutions, portails officiels"
      defaultSourceType="institution_publique"
    />
  );
}
