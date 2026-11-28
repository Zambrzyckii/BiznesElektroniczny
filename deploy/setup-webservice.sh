#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "${PS_WS_KEY:-}" ] && [ -f "$SCRIPT_DIR/.env" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in
      ''|'#'*) continue ;;
      PS_WS_KEY=*)
        val="${line#PS_WS_KEY=}"
        if [[ "$val" =~ ^\"(.*)\"$ ]]; then
          val="${BASH_REMATCH[1]}"
        elif [[ "$val" =~ ^\'(.*)\'$ ]]; then
          val="${BASH_REMATCH[1]}"
        fi
        export PS_WS_KEY="$val"
        ;;
    esac
  done < "$SCRIPT_DIR/.env"
fi

: "${PS_WS_KEY:?Set PS_WS_KEY (32 chars) in the environment or deploy/.env}"

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
if (strlen($key) !== 32 || !ctype_alnum($key)) {
    file_put_contents('php://stderr', "PS_WS_KEY must be exactly 32 alphanumeric characters\n");
    exit(1);
}
if ($key === 'ChangeMeWebserviceKey32Chars0001') {
    file_put_contents('php://stderr', "PS_WS_KEY must not use the example placeholder value\n");
    exit(1);
}

Context::getContext()->employee = new Employee(1);

if (!Configuration::updateValue('PS_WEBSERVICE', 1)) {
    file_put_contents('php://stderr', "Failed to enable PS_WEBSERVICE\n");
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
    file_put_contents('php://stderr', "Failed to save WebserviceKey\n");
    exit(1);
}

$account->associateTo(1);

$permissions = [
    'categories' => ['GET' => 1, 'POST' => 1, 'PUT' => 1],
    'products' => ['GET' => 1, 'POST' => 1, 'PUT' => 1],
    'stock_availables' => ['GET' => 1, 'PUT' => 1],
    'tax_rule_groups' => ['GET' => 1],
    'tax_rules' => ['GET' => 1],
    'taxes' => ['GET' => 1],
];

if (!WebserviceKey::setPermissionForAccount((int) $account->id, $permissions)) {
    file_put_contents('php://stderr', "Failed to set WebserviceKey permissions\n");
    exit(1);
}

echo 'Webservice enabled and key configured (id=' . (int) $account->id . ").\n";
PHP
