export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12 text-slate-700">
      <h1 className="text-3xl font-bold text-slate-950">Politique de confidentialité</h1>
      <p className="mt-2 text-sm text-slate-400">Dernière mise à jour : mai 2025</p>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">1. Données collectées</h2>
        <p className="mt-3 text-sm leading-7">
          Kafundo collecte uniquement les données nécessaires au fonctionnement du service :
        </p>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm leading-7">
          <li>Informations de compte : nom, adresse email, mot de passe (haché)</li>
          <li>Informations d'organisation : nom, secteur, pays cibles, type d'organisation</li>
          <li>Données d'usage : alertes, recherches sauvegardées, projets suivis, favoris</li>
          <li>Journaux techniques : connexions, actions (à des fins de sécurité et d'audit)</li>
        </ul>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">2. Finalité du traitement</h2>
        <p className="mt-3 text-sm leading-7">
          Les données sont utilisées pour : fournir et améliorer le service, personnaliser les recommandations
          et alertes, gérer les abonnements et la facturation, assurer la sécurité de la plateforme, et envoyer
          des communications liées au service (jamais de publicité tierce).
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">3. Base légale</h2>
        <p className="mt-3 text-sm leading-7">
          Le traitement est fondé sur l'exécution du contrat (fourniture du service), le consentement (alertes
          email optionnelles) et l'intérêt légitime (sécurité, amélioration du service).
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">4. Conservation des données</h2>
        <p className="mt-3 text-sm leading-7">
          Les données de compte sont conservées pendant la durée de l'abonnement, puis 30 jours après la
          résiliation (délai de récupération). Les journaux de sécurité sont conservés 12 mois. Sur demande
          explicite, toutes les données peuvent être supprimées immédiatement.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">5. Partage des données</h2>
        <p className="mt-3 text-sm leading-7">
          Kafundo ne vend pas vos données. Les données peuvent être partagées uniquement avec des
          sous-traitants techniques (hébergement Hostinger, paiement Stripe, email Brevo) dans le cadre
          strict de la fourniture du service, sous contrat de traitement de données conforme au RGPD.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">6. Vos droits (RGPD)</h2>
        <p className="mt-3 text-sm leading-7">
          Conformément au RGPD, vous disposez des droits suivants :
        </p>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm leading-7">
          <li><span className="font-medium">Accès</span> : obtenir une copie de vos données</li>
          <li><span className="font-medium">Rectification</span> : corriger vos données</li>
          <li><span className="font-medium">Effacement</span> : supprimer votre compte et vos données</li>
          <li><span className="font-medium">Portabilité</span> : exporter vos données au format JSON</li>
          <li><span className="font-medium">Opposition</span> : vous opposer à certains traitements</li>
        </ul>
        <p className="mt-3 text-sm leading-7">
          Ces droits s'exercent depuis vos{" "}
          <a href="/settings/security" className="text-primary-600 hover:underline">paramètres de sécurité</a>
          {" "}ou par email à{" "}
          <a href="mailto:contact@kafundo.com" className="text-primary-600 hover:underline">contact@kafundo.com</a>.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">7. Cookies</h2>
        <p className="mt-3 text-sm leading-7">
          Kafundo utilise uniquement des cookies techniques essentiels (session, authentification,
          préférences d'interface). Aucun cookie publicitaire ou analytique tiers n'est utilisé sans
          consentement.
        </p>
      </section>

      <section className="mt-10 pb-16">
        <h2 className="text-xl font-semibold text-slate-900">8. Contact</h2>
        <p className="mt-3 text-sm leading-7">
          Responsable du traitement : Finnovatix — Hamed Ouedraogo
          <br />
          Email :{" "}
          <a href="mailto:contact@kafundo.com" className="text-primary-600 hover:underline">contact@kafundo.com</a>
        </p>
        <p className="mt-3 text-sm leading-7">
          Vous pouvez également adresser une réclamation à la CNIL :{" "}
          <a href="https://www.cnil.fr" className="text-primary-600 hover:underline" target="_blank" rel="noopener noreferrer">
            www.cnil.fr
          </a>
        </p>
        <p className="mt-4 text-sm">
          <a href="/legal/mentions" className="text-primary-600 hover:underline">Mentions légales</a>
          {" · "}
          <a href="/legal/terms" className="text-primary-600 hover:underline">CGU</a>
        </p>
      </section>
    </main>
  );
}
