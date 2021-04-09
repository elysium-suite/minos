#!/bin/bash

#######################################
# Minos Scoring Engine Install Script #
#######################################

if ! [[ $EUID -eq 0 ]]; then
   echo -e "${err} Install script must be run as sudo (sudo ./install.sh)"
   exit 1
fi

if ! [ -z ${1+x} ]; then
    echo "Usage: ./install.sh"
    exit 1
fi

if ! [ $(pwd) == "/opt/minos/setup" ]; then
	  echo -e "$warn Please make sure you downloaded the folder to /opt/minos,"
    echo "    and are running install.sh from /opt/minos/setup."
    exit 1
fi

cat <<EOF

#############################################################

88b           d88  88
888b         d888  ""
88\`8b       d8'88
88 \`8b     d8' 88  88  8b,dPPYba,    ,adPPYba,   ,adPPYba,
88  \`8b   d8'  88  88  88P'   \`"8a  a8"     "8a  I8[    ""
88   \`8b d8'   88  88  88       88  8b       d8   \`"Y8ba,
88    \`888'    88  88  88       88  "8a,   ,a8"  aa    ]8I
88     \`8'     88  88  88       88   \`"YbbdP"'   \`"YbbdP"'
#############################################################

EOF

# Color codes
plus="\033[1;32m[+]\e[m"
warn="\033[1;33m[!]\e[m"
err="\033[1;31m[!]\e[m"

# Update package list and set list to check if package needs updating
echo -e "$plus Updating package list..."
apt update

# Check if a package is installed before trying to install it
install_package() {
    if ! (dpkg -l $1 > /dev/null 2>&1); then
        apt install -y $1 && echo -e "\t$plus Successfully installed $1." || echo -e "\t$err Installing $1 failed!"
    else
        echo -e "\t$plus Package $1 is already installed."
    fi
}

echo -e "\n$plus Installing dependencies..."
install_package python3
install_package python3-pip
install_package python3-dev
install_package freerdp2-x11
install_package smbclient
install_package nginx
CRYPTOGRAPHY_DONT_BUILD_RUST=1
pip3 install -U dnspython pysmb paramiko requests timeout-decorator toml pycryptodome
pip3 install -U Flask flask_login flask-wtf bcrypt uwsgi

echo -e "$plus Configuring nginx..."
cp /opt/minos/setup/minos.site /etc/nginx/sites-available/
rm /etc/nginx/sites-enabled/minos.site /etc/nginx/sites-enabled/default 2>/dev/null
ln -s /etc/nginx/sites-available/minos.site /etc/nginx/sites-enabled/

echo -e "$plus Creating services (init.d style)..."
cp -f /opt/minos/setup/minos /etc/init.d/
touch /opt/minos/engine/scoring.db

chgrp -R www-data /opt/minos/engine/etc/
chmod -R g+w /opt/minos

# Start all the services
echo -e "$plus Starting services..."
service nginx start

echo -e "\n$plus To interact or view the engine, navigate to:"
echo -e "\t http://localhost\n"
echo -e "$plus Minos has been set up! To start, run:"
echo -e "\t service minos start\n"
