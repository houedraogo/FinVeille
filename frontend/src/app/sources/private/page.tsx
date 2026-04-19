import RoleGate from "@/components/RoleGate";
import SourcesPageContent from "@/components/SourcesPageContent";

export default function PrivateSourcesPage() {
  return (
    <RoleGate
      allow={["admin", "editor"]}
      title="Sources réservées à l'équipe"
      message="Les utilisateurs standard n'ont pas accès au référentiel des sources privées."
    >
      <SourcesPageContent
        category="private"
        title="Sources — Financement privé"
        subtitle="Fonds d'investissement, investisseurs privés, capital-risque"
        defaultSourceType="fonds_prive"
      />
    </RoleGate>
  );
}
