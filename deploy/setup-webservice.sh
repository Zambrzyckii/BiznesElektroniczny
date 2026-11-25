#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

: "${PS_WS_KEY:?Set PS_WS_KEY (32 chars) in the environment}"

run_php() {
  if [ ! -f /var/www/html/config/config.inc.php ]; then
    docker compose -f "$SCRIPT_DIR/compose.yaml" exec -T -e PS_WS_KEY shop runuser -g www-data -u www-data -- php
  elif [ "$(id -u)" -eq 0 ]; then
    runuser -g www-data -u www-data -- php
  else
    php
  fi
}

run_php <<'PHP'
<?php
require_once '/var/www/html/config/config.inc.php';

$key = (string) getenv('PS_WS_KEY');
if (strlen($key) !== 32) {
    fwrite(STDERR, "PS_WS_KEY must be exactly 32 characters\n");
    exit(1);
}

Context::getContext()->employee = new Employee(1);

if (!Configuration::updateValue('PS_WEBSERVICE', 1)) {
    fwrite(STDERR, "Failed to enable PS_WEBSERVICE\n");
    exit(1);
}

$id = (int) WebserviceKey::getIdFromKey($key);
if ($id > 0) {
    $account = new WebserviceKey($id);
} else {
    $account = new WebserviceKey();
    $account->key = $key;
}

$account->active = true;
$account->description = 'Scraper import key';

if (!$account->save()) {
    fwrite(STDERR, "Failed to save WebserviceKey\n");
    exit(1);
}

$account->associateTo(1);

if (!WebserviceKey::setPermissionForAccount((int) $account->id, ['categories' => ['GET' => 1, 'POST' => 1, 'PUT' => 1]])) {
    fwrite(STDERR, "Failed to set WebserviceKey permissions\n");
    exit(1);
}

echo 'Webservice enabled and key configured (id=' . (int) $account->id . ").\n";
PHP
