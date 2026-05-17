export default function TermsPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12 text-slate-700">
      <h1 className="text-3xl font-bold text-slate-950">Conditions générales d'utilisation</h1>
      <p className="mt-2 text-sm text-slate-400">Dernière mise à jour : mai 2025</p>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">1. Objet</h2>
        <p className="mt-3 text-sm leading-7">
          Kafundo est une plateforme SaaS de veille et d'identification d'opportunités de financement (subventions,
          prêts, appels à projets, investisseurs) destinée aux entreprises, startups et consultants. Les présentes
          CGU définissent les conditions d'accès et d'utilisation du service.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">2. Accès au service</h2>
        <p className="mt-3 text-sm leading-7">
          L'accès à Kafundo nécessite la création d'un compte. L'utilisateur s'engage à fournir des informations
          exactes lors de son inscription et à maintenir la confidentialité de ses identifiants. Tout accès non
          autorisé doit être signalé immédiatement à{" "}
          <a href="mailto:contact@kafundo.com" className="text-primary-600 hover:underline">contact@kafundo.com</a>.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">3. Plans et facturation</h2>
        <p className="mt-3 text-sm leading-7">
          Kafundo propose plusieurs plans tarifaires (Découverte, Pro, Team). Les abonnements payants sont facturés
          mensuellement via Stripe. Le plan Découverte est gratuit et soumis à des limites d'usage. Les
          abonnements peuvent être résiliés à tout moment depuis les paramètres de facturation, avec effet à la
          fin de la période en cours.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">4. Données et fiabilité</h2>
        <p className="mt-3 text-sm leading-7">
          Les données affichées sur Kafundo sont issues de sources publiques et doivent être confirmées sur les
          sources officielles avant toute décision ou candidature. Kafundo fournit une aide à la décision et ne
          garantit pas l'exhaustivité ni l'exactitude des informations présentées.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">5. Utilisation acceptable</h2>
        <p className="mt-3 text-sm leading-7">
          Il est interdit d'utiliser Kafundo pour : extraire massivement les données (scraping), contourner les
          limites du plan souscrit, revendre l'accès à des tiers, ou utiliser le service à des fins illicites.
          Toute violation peut entraîner la suspension immédiate du compte.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">6. Propriété intellectuelle</h2>
        <p className="mt-3 text-sm leading-7">
          Les algorithmes de scoring, de matching et de veille de Kafundo sont la propriété exclusive de
          Finnovatix. L'utilisateur conserve la propriété de ses données et projets.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">7. Responsabilité</h2>
        <p className="mt-3 text-sm leading-7">
          Kafundo ne pourra être tenu responsable de dommages indirects liés à l'utilisation du service, à
          l'indisponibilité temporaire de la plateforme ou à des décisions prises sur la base des informations
          fournies.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">8. Modification des CGU</h2>
        <p className="mt-3 text-sm leading-7">
          Kafundo se réserve le droit de modifier les présentes CGU à tout moment. Les utilisateurs seront
          informés par email des modifications substantielles. La poursuite de l'utilisation du service vaut
          acceptation des nouvelles CGU.
        </p>
      </section>

      <section className="mt-10 pb-16">
        <h2 className="text-xl font-semibold text-slate-900">9. Contact</h2>
        <p className="mt-3 text-sm leading-7">
          Pour toute question relative aux présentes CGU :{" "}
          <a href="mailto:contact@kafundo.com" className="text-primary-600 hover:underline">contact@kafundo.com</a>
        </p>
        <p className="mt-4 text-sm">
          <a href="/legal/mentions" className="text-primary-600 hover:underline">Mentions légales</a>
          {" · "}
          <a href="/legal/privacy" className="text-primary-600 hover:underline">Politique de confidentialité</a>
        </p>
      </section>
    </main>
  );
}
