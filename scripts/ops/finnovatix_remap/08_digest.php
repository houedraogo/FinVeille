<?php
// Synthese par consultant des modifications de dispositifs suivis (une notification par destinataire, jamais une par dossier).
// Lit : RUN, DIGEST_MODE (dry|apply|rollback), DIGEST_JSON_B64, DIGEST_MAX (defaut 30). Passe par NotificationCenter::notify
// (preferences utilisateur respectees, aucun e-mail : sendEmail=false). Rejouable : une synthese deja creee pour ce run est
// ignoree ; `rollback` ne supprime que les syntheses creees par ce run.
require '/var/www/html/vendor/autoload.php';
$app = require '/var/www/html/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();

use Illuminate\Support\Facades\DB;

$run = getenv('RUN') ?: 'FXREMAP';
$mode = getenv('DIGEST_MODE') ?: 'dry';
$max = (int) (getenv('DIGEST_MAX') ?: 30);
$digest = json_decode(base64_decode((string) getenv('DIGEST_JSON_B64')), true) ?: [];
$type = 'funding_opportunity_changed';
echo 'base=' . DB::connection()->getDatabaseName() . ' hote=' . config('database.connections.mysql.host') . "\n";

if ($mode === 'rollback') {
    $n = DB::table('notifications')->where('type', $type)->where('data->run', $run)->where('data->kind', 'kafundo_remap_digest')->delete();
    echo "syntheses supprimees : {$n}\n";
    exit(0);
}
if (count($digest) > $max) {
    fwrite(STDERR, 'ARRET: ' . count($digest) . " destinataires > plafond {$max}\n");
    exit(1);
}
$notifier = app(App\Microsoft\Services\NotificationCenter::class);
$created = $skipped = $off = 0;
foreach ($digest as $userId => $items) {
    $exists = DB::table('notifications')->where('user_id', $userId)->where('type', $type)->where('data->run', $run)->exists();
    if ($exists) { $skipped++; continue; }
    $user = App\Models\User::find($userId);
    if ($user === null) { fwrite(STDERR, "utilisateur {$userId} introuvable\n"); continue; }
    // regroupe par dispositif : une ligne de changement, puis les dossiers concernes
    $byCall = [];
    foreach ($items as $it) { $byCall[$it['funding_call_id']][] = $it; }
    $lines = [];
    foreach ($byCall as $rows) {
        $lines[] = '• ' . $rows[0]['dispositif'] . ' — ' . $rows[0]['changes'];
        $names = array_values(array_unique(array_map(fn ($r) => $r['project'], $rows)));
        $shown = array_slice($names, 0, 12);
        $lines[] = '   Dossiers (' . count($names) . ') : ' . implode(', ', $shown) . (count($names) > 12 ? ', …' : '');
    }
    $title = 'Synthèse — ' . count($byCall) . ' dispositif(s) mis à jour, ' . count($items) . ' dossier(s) concerné(s)';
    $body = "Mise à jour technique du catalogue de financements : les valeurs ci-dessous ont été réalignées sur la source (aucune action requise, information).
" . implode("
", $lines);
    if ($mode === 'dry') { echo "[simulation] user={$userId} dossiers=" . count($items) . "\n"; continue; }
    $first = $items[0]['project_id'];
    $n = $notifier->notify($user, $type, $title, $body, 'refresh-cw', 'amber', route('consulting.funding.overview', $first),
        ['kind' => 'kafundo_remap_digest', 'run' => $run, 'items' => $items]);
    $n === null ? $off++ : $created++;
}
echo "syntheses creees={$created} deja_presentes={$skipped} categorie_desactivee={$off} destinataires=" . count($digest) . "\n";
