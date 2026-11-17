#!/bin/sh
set -e

runuser -g www-data -u www-data -- php /var/www/html/bin/console prestashop:config set PS_DETECT_COUNTRY --value 0 --env=prod
runuser -g www-data -u www-data -- php /var/www/html/bin/console prestashop:config set PS_TIMEZONE --value Europe/Warsaw --env=prod
