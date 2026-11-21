#!/bin/sh
set -e

runuser -g www-data -u www-data -- php /var/www/html/bin/console prestashop:config set BANK_WIRE_OWNER --value "Zielona Spiżarnia Testowa Sp. z o.o." --env=prod
runuser -g www-data -u www-data -- php /var/www/html/bin/console prestashop:config set BANK_WIRE_DETAILS --value "PL00 0000 0000 0000 0000 0000 0000" --env=prod
runuser -g www-data -u www-data -- php /var/www/html/bin/console prestashop:config set BANK_WIRE_ADDRESS --value "Bank Testowy S.A., 00-000 Warszawa" --env=prod
runuser -g www-data -u www-data -- php /var/www/html/bin/console prestashop:module disable ps_checkpayment --env=prod
MYSQL_PWD="$DB_PASSWD" mysql -h "$DB_SERVER" -u "$DB_USER" "$DB_NAME" -e "UPDATE ps_order_state SET invoice = 1 WHERE module_name = 'ps_cashondelivery'"
