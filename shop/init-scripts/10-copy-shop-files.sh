#!/bin/sh
set -e
cp -R /tmp/shop-files/themes/. /var/www/html/themes/
cp -R /tmp/shop-files/modules/. /var/www/html/modules/
chown -R www-data:www-data /var/www/html/themes /var/www/html/modules
