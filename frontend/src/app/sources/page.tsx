import RoleGate from "@/components/RoleGate";
import SourcesPageContent from "@/components/SourcesPageContent";

export default function PublicSourcesPage() {
  return (
    <RoleGate
      allow={["admin", "editor"]}
      title="Sources réservées à l'équipe"
      message="Les utilisateurs standard n'ont pas accès à la gestion des sources de collecte."
    >
      <SourcesPageContent
        category="public"
        title="Sources — Financement public"
        subtitle="Agences publiques, institutions, portails officiels"
        defaultSourceType="institution_publique"
      />
    </RoleGate>
  );
}
