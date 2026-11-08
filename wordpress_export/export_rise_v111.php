<?php
/**
 * RISE Content Hub 1.11 -> RISE 2.0: read-only export for WP-CLI.
 * Run: RISE_EXPORT_OUTPUT=/secure/directory/rise-legacy.json wp eval-file export_rise_v111.php
 * NEVER run via a public URL or put export file inside web root.
 */
if (!defined('WP_CLI') || !WP_CLI || !defined('ABSPATH') || PHP_SAPI !== 'cli') {
    exit("Exclusivo para WP-CLI.\n");
}
global $wpdb;
$dest = getenv('RISE_EXPORT_OUTPUT');
if (!is_string($dest) || $dest === '' || substr($dest, -5) !== '.json' || !is_dir(dirname($dest))) {
    WP_CLI::error('Defina RISE_EXPORT_OUTPUT como caminho absoluto .json numa pasta existente fora do public_html.');
}
$real_dir = realpath(dirname($dest));
$document_root = realpath(ABSPATH);
if (!$real_dir || !$document_root || strpos($real_dir . DIRECTORY_SEPARATOR, $document_root . DIRECTORY_SEPARATOR) === 0) {
    WP_CLI::error('O destino não pode estar dentro da raiz pública do WordPress.');
}
if (file_exists($dest)) WP_CLI::error('O ficheiro já existe; não será substituído.');
$prefix = $wpdb->prefix . 'rise_hub_';
$tables = [
    'records' => 'records', 'membership' => 'membership', 'versions' => 'versions',
    'events' => 'events', 'ci_observations' => 'ci_observations',
    'ci_ads' => 'ci_ads', 'publishing_jobs' => 'publishing_jobs',
    'mc_campaigns' => 'mc_campaigns', 'mc_comments' => 'mc_comments',
    'mc_events' => 'mc_events',
];
$deny_pattern = '/(pass(word|wd)?|secret|token|api[_-]?key|client[_-]?secret|authorization|bearer|cookie|private[_-]?key|smtp.*pass|credential|auth[_-]?code)/i';
$redact = function ($value) use (&$redact, $deny_pattern) {
    if (is_array($value)) {
        $out = [];
        foreach ($value as $key => $item) {
            if (preg_match($deny_pattern, (string)$key)) continue;
            $out[$key] = $redact($item);
        }
        return $out;
    }
    return $value;
};
function rise_export_row($row, $redact) {
    foreach (['payload', 'detail', 'approvals'] as $field) {
        if (isset($row[$field]) && is_string($row[$field])) {
            $decoded = json_decode($row[$field], true);
            if (json_last_error() === JSON_ERROR_NONE) $row[$field] = $redact($decoded);
        }
    }
    return $redact($row);
}
$old_umask = umask(0077);
$stream = fopen($dest, 'x');
umask($old_umask);
if (!$stream) WP_CLI::error('Não foi possível criar o ficheiro.');
chmod($dest, 0600);
$counts = [];
try {
    $header = [
        'schema' => 'rise-wordpress-1.11-export-v1',
        'exported_at_utc' => gmdate('c'),
        'site' => home_url(),
        'timezone' => wp_timezone_string(),
        'secrets_excluded' => true,
        'assets_binary_included' => false,
        'publish_jobs_inert' => true,
    ];
    fwrite($stream, '{"metadata":' . wp_json_encode($header, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . ',"tables":{');
    $first_table = true;
    foreach ($tables as $label => $suffix) {
        $table = $prefix . $suffix;
        if (strpos($suffix, 'mc_') === 0) $table = $wpdb->prefix . 'rise_hub_' . $suffix;
        $exists = $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table)));
        if ($exists !== $table) continue;
        if (!$first_table) fwrite($stream, ',');
        $first_table = false;
        fwrite($stream, wp_json_encode($label) . ':[');
        $last_id = 0;
        $count = 0;
        while (true) {
            $rows = $wpdb->get_results($wpdb->prepare("SELECT * FROM `{$table}` WHERE id > %d ORDER BY id ASC LIMIT 300", $last_id), ARRAY_A);
            if (!$rows) break;
            foreach ($rows as $row) {
                $last_id = (int)$row['id'];
                if ($label === 'records' && ($row['kind'] ?? '') === 'integrations') continue;
                if ($count > 0) fwrite($stream, ',');
                $safe = rise_export_row($row, $redact);
                $json = wp_json_encode($safe, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
                if ($json === false) throw new RuntimeException("Erro a serializar {$label} id={$last_id}");
                fwrite($stream, $json);
                $count++;
            }
            if (count($rows) < 300) break;
        }
        fwrite($stream, ']');
        $counts[$label] = $count;
    }
    fwrite($stream, '},"counts":' . wp_json_encode($counts) . '}');
    fflush($stream);
    fclose($stream);
    WP_CLI::success('Exportação concluída. Tabelas: ' . wp_json_encode($counts) . '. Guarde o JSON de forma privada.');
} catch (Throwable $ex) {
    fclose($stream);
    unlink($dest);
    WP_CLI::error('Exportação cancelada: ' . $ex->getMessage());
}
