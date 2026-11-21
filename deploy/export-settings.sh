#!/bin/sh
set -e
cd "$(dirname "$0")"

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

tables=$(cat settings/tables.txt)

keys=""
for key in $(cat settings/config-keys.txt); do
  keys="$keys,'$key'"
done
keys=${keys#,}

scoped=$(echo "SELECT name FROM ps_configuration WHERE (id_shop IS NOT NULL OR id_shop_group IS NOT NULL) AND name IN ($keys);" | db_query)
if [ -n "$scoped" ]; then
  echo "Keys set for a single shop or shop group, the export would miss them:" >&2
  echo "$scoped" >&2
  exit 1
fi

{
  for table in $tables; do
    echo "TRUNCATE TABLE $table;"
  done
  docker compose exec -T db sh -c 'mariadb-dump --default-character-set=utf8mb4 -u"$MARIADB_USER" -p"$MARIADB_PASSWORD" --single-transaction --no-create-info --skip-extended-insert --order-by-primary --skip-dump-date --skip-comments "$MARIADB_DATABASE" "$@"' sh $tables
} > settings/snapshot.sql

mkdir -p settings/carrier-logos
rm -f settings/carrier-logos/*.jpg
for file in $(docker compose exec -T shop sh -c 'cd /var/www/html/img/s && ls *.jpg 2>/dev/null || true'); do
  docker compose cp "shop:/var/www/html/img/s/$file" "settings/carrier-logos/$file"
done

db_query > settings/config.tsv <<SQL
SELECT c.name, IFNULL(l.iso_code, '-'), IF(cl.id_lang IS NULL, c.value, cl.value)
FROM ps_configuration c
LEFT JOIN ps_configuration_lang cl ON cl.id_configuration = c.id_configuration
LEFT JOIN ps_lang l ON l.id_lang = cl.id_lang
WHERE c.id_shop IS NULL AND c.id_shop_group IS NULL
AND c.name IN ($keys)
AND (cl.id_lang IS NULL OR l.active = 1)
AND IF(cl.id_lang IS NULL, c.value, cl.value) IS NOT NULL
ORDER BY c.name, l.iso_code;
SQL

module_states > settings/modules.tsv

echo "SELECT theme_name FROM ps_shop WHERE id_shop = 1;" | db_query > settings/theme.txt

{
  echo "DELETE FROM ps_hook_module WHERE id_shop = 1;"
  db_query <<'SQL'
SELECT CONCAT('INSERT INTO ps_hook_module (id_module, id_shop, id_hook, position) SELECT m.id_module, 1, h.id_hook, ', hm.position, ' FROM ps_module m, ps_hook h WHERE m.name = ', QUOTE(m.name), ' AND h.name = ', QUOTE(h.name), ';')
FROM ps_hook_module hm
JOIN ps_module m ON m.id_module = hm.id_module
JOIN ps_hook h ON h.id_hook = hm.id_hook
WHERE hm.id_shop = 1
ORDER BY h.name, hm.position, m.name;
SQL
} > settings/hook-positions.sql

{
  echo "DELETE FROM ps_module_carrier WHERE id_shop = 1;"
  echo "DELETE FROM ps_module_country WHERE id_shop = 1;"
  echo "DELETE FROM ps_module_currency WHERE id_shop = 1;"
  db_query <<'SQL'
SELECT CONCAT('INSERT INTO ps_module_carrier (id_module, id_shop, id_reference) SELECT id_module, 1, ', x.id_reference, ' FROM ps_module WHERE name = ', QUOTE(m.name), ';')
FROM ps_module_carrier x JOIN ps_module m ON m.id_module = x.id_module
WHERE x.id_shop = 1
UNION ALL
SELECT CONCAT('INSERT INTO ps_module_country (id_module, id_shop, id_country) SELECT id_module, 1, ', x.id_country, ' FROM ps_module WHERE name = ', QUOTE(m.name), ';')
FROM ps_module_country x JOIN ps_module m ON m.id_module = x.id_module
WHERE x.id_shop = 1
UNION ALL
SELECT CONCAT('INSERT INTO ps_module_currency (id_module, id_shop, id_currency) SELECT id_module, 1, ', x.id_currency, ' FROM ps_module WHERE name = ', QUOTE(m.name), ';')
FROM ps_module_currency x JOIN ps_module m ON m.id_module = x.id_module
WHERE x.id_shop = 1
ORDER BY 1;
SQL
} > settings/payment-restrictions.sql
