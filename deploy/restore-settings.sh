#!/bin/sh
set -e
cd "$(dirname "$0")"

tab=$(printf '\t')

db_query() {
  docker compose exec -T db sh -c 'mariadb --default-character-set=utf8mb4 -u"$MARIADB_USER" -p"$MARIADB_PASSWORD" --batch --skip-column-names "$MARIADB_DATABASE"'
}

module_states() {
  db_query <<'SQL'
SELECT m.name, IF(ms.id_module IS NULL, 'disabled', 'enabled')
FROM ps_module m
LEFT JOIN ps_module_shop ms ON ms.id_module = m.id_module AND ms.id_shop = 1
ORDER BY m.name;
SQL
}

console() {
  docker compose exec -T shop runuser -g www-data -u www-data -- php /var/www/html/bin/console "$@" --env=prod < /dev/null
}

console prestashop:theme:enable "$(cat settings/theme.txt)"

current=$(module_states)
while IFS="$tab" read -r name state; do
  current_state=$(printf '%s\n' "$current" | awk -F "$tab" -v name="$name" '$1 == name { print $2 }')
  if [ -z "$current_state" ]; then
    console prestashop:module install "$name"
    current_state=enabled
  fi
  if [ "$state" = enabled ] && [ "$current_state" = disabled ]; then
    console prestashop:module enable "$name"
  elif [ "$state" = disabled ] && [ "$current_state" = enabled ]; then
    console prestashop:module disable "$name"
  fi
done < settings/modules.tsv

current=$(module_states)
while IFS= read -r line; do
  if ! printf '%s\n' "$current" | grep -qxF "$line"; then
    echo "Module state not restored: $line" >&2
    exit 1
  fi
done < settings/modules.tsv

db_query < settings/snapshot.sql
docker compose exec -T shop sh -c 'rm -f /var/www/html/img/s/*.jpg'
for file in settings/carrier-logos/*.jpg; do
  [ -e "$file" ] || continue
  docker compose cp "$file" shop:/var/www/html/img/s/
done
docker compose exec -T shop chown -R www-data:www-data /var/www/html/img/s

while IFS="$tab" read -r name lang value; do
  value=$(printf '%bx' "$value")
  value=${value%x}
  if [ "$lang" = "-" ]; then
    console prestashop:config set "$name" "--value=$value"
  else
    console prestashop:config set "$name" "--value=$value" "--lang=$lang"
  fi
done < settings/config.tsv

db_query < settings/hook-positions.sql
db_query < settings/payment-restrictions.sql

console cache:clear
