export default function MentionsLegalesPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12 text-slate-700">
      <h1 className="text-3xl font-bold text-slate-950">Mentions légales</h1>
      <p className="mt-2 text-sm text-slate-400">Dernière mise à jour : mai 2025</p>

      {/* Éditeur */}
      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">Éditeur du site</h2>
        <div className="mt-3 space-y-1 text-sm leading-7">
          <p><span className="font-medium">Raison sociale :</span> Finnovatix</p>
          <p><span className="font-medium">Forme juridique :</span> Entreprise individuelle / SASU</p>
          <p><span className="font-medium">Responsable de la publication :</span> Hamed Ouedraogo</p>
          <p><span className="font-medium">Email :</span>{" "}
            <a href="mailto:contact@kafundo.com" className="text-primary-600 hover:underline">
              contact@kafundo.com
            </a>
          </p>
          <p><span className="font-medium">Site web :</span>{" "}
            <a href="https://kafundo.com" className="text-primary-600 hover:underline" target="_blank" rel="noopener noreferrer">
              kafundo.com
            </a>
          </p>
        </div>
      </section>

      {/* Hébergement */}
      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">Hébergement</h2>
        <div className="mt-3 space-y-1 text-sm leading-7">
          <p><span className="font-medium">Hébergeur :</span> Hostinger International Ltd.</p>
          <p><span className="font-medium">Adresse :</span> 61 Lordou Vironos Street, 6023 Larnaca, Chypre</p>
          <p><span className="font-medium">Site :</span>{" "}
            <a href="https://www.hostinger.com" className="text-primary-600 hover:underline" target="_blank" rel="noopener noreferrer">
              www.hostinger.com
            </a>
          </p>
        </div>
      </section>

      {/* Propriété intellectuelle */}
      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">Propriété intellectuelle</h2>
        <p className="mt-3 text-sm leading-7">
          L'ensemble des contenus présents sur la plateforme Kafundo (textes, graphiques, logos, icônes, algorithmes de
          scoring et de matching) est la propriété exclusive de Finnovatix et est protégé par les lois françaises et
          internationales relatives à la propriété intellectuelle. Toute reproduction, distribution ou utilisation sans
          autorisation écrite préalable est interdite.
        </p>
      </section>

      {/* Données personnelles */}
      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">Données personnelles</h2>
        <p className="mt-3 text-sm leading-7">
          Les données collectées par Kafundo sont traitées conformément au Règlement Général sur la Protection des
          Données (RGPD). Vous disposez d'un droit d'accès, de rectification, d'effacement et de portabilité de vos
          données depuis vos{" "}
          <a href="/settings/security" className="text-primary-600 hover:underline">
            paramètres de sécurité
          </a>
          . Pour toute demande, contactez-nous à{" "}
          <a href="mailto:contact@kafundo.com" className="text-primary-600 hover:underline">
            contact@kafundo.com
          </a>
          .
        </p>
        <p className="mt-3 text-sm leading-7">
          Pour plus d'informations, consultez notre{" "}
          <a href="/legal/privacy" className="text-primary-600 hover:underline">
            politique de confidentialité
          </a>
          .
        </p>
      </section>

      {/* Cookies */}
      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">Cookies</h2>
        <p className="mt-3 text-sm leading-7">
          Kafundo utilise uniquement des cookies techniques nécessaires au fonctionnement du service (session,
          authentification, préférences). Aucun cookie publicitaire ou de traçage tiers n'est déposé sans votre
          consentement explicite.
        </p>
      </section>

      {/* Limitation de responsabilité */}
      <section className="mt-10">
        <h2 className="text-xl font-semibold text-slate-900">Limitation de responsabilité</h2>
        <p className="mt-3 text-sm leading-7">
          Les informations présentées sur Kafundo sont issues de sources publiques et sont fournies à titre indicatif.
          Kafundo ne peut être tenu responsable d'erreurs, d'omissions ou de résultats obtenus suite à l'utilisation
          de ces informations. Tout dossier de financement doit être vérifié sur les sources officielles avant soumission.
        </p>
      </section>

      {/* Droit applicable */}
      <section className="mt-10 pb-16">
        <h2 className="text-xl font-semibold text-slate-900">Droit applicable</h2>
        <p className="mt-3 text-sm leading-7">
          Les présentes mentions légales sont soumises au droit français. En cas de litige, les tribunaux français seront
          seuls compétents.
        </p>
      </section>
    </main>
  );
}
