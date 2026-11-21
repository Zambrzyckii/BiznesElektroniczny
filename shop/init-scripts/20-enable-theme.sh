#!/bin/sh
set -e
theme=dobrakaloria
active_theme=$(mysql -h "$DB_SERVER" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWD" -N -s -e "SELECT theme_name FROM ${DB_PREFIX}shop WHERE id_shop = 1" "$DB_NAME")
if [ "$active_theme" != "$theme" ]; then
  runuser -g www-data -u www-data -- php /var/www/html/bin/console prestashop:theme:enable "$theme" --env=prod
fi
