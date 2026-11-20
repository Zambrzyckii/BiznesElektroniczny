#!/bin/sh
set -e

runuser -g www-data -u www-data -- php /var/www/html/bin/console prestashop:config set PS_MAIL_METHOD --value 2 --env=prod
runuser -g www-data -u www-data -- php /var/www/html/bin/console prestashop:config set PS_MAIL_SERVER --value mailpit --env=prod
runuser -g www-data -u www-data -- php /var/www/html/bin/console prestashop:config set PS_MAIL_SMTP_PORT --value 1025 --env=prod
runuser -g www-data -u www-data -- php /var/www/html/bin/console prestashop:config set PS_MAIL_SMTP_ENCRYPTION --value off --env=prod
