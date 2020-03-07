#!/bin/bash

#######################################
# Minos Scoring Engine Install Script #
#######################################

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
err="\033[1;31m{!]\e[m"

# Root check
if ! [[ $EUID -eq 0 ]]; then
   echo -e "${err} Install script must be run as sudo (sudo ./install.sh)"
   exit 1
fi

if ! [ -z ${1+x} ]; then
    echo "Usage: ./install.sh"
    exit 1
fi

# Copying directory to opt
if ! [ $(pwd) == "/opt/minos/setup" ]; then
	echo -e "$warn Copy files to /opt/minos? This WILL overwrite your previous files in this directory. Press any key to continue or CTRL-c to break."
	echo -e "$warn Please ensure that install.sh is in its original location in the repo and you are in the same folder as the script."
	read
	echo -e "$plus Copying files to /opt/minos..."
	mkdir -p /opt/minos
	cp -rf ../ /opt/minos
fi

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

echo -e "\n$plus Installing engine dependencies..."
    install_package python3
    install_package python3-pip
    install_package python3-dev
    install_package libsasl2-dev
    install_package freetds-dev
    install_package libssl-dev
    install_package libffi-dev
    install_package libldap2-dev
    install_package freerdp2-x11
    install_package smbclient
    pip3 install -U dnspython paramiko requests timeout-decorator python-ldap toml

echo -e "$plus Installing web dependencies..."
    install_package python3-tk
    install_package python3-pip
    install_package nginx
    pip3 install -U Flask flask_login flask-wtf bcrypt uwsgi

echo -e "$plus Configuring nginx..."
    cp install/minos.site /etc/nginx/sites-available/
    rm /etc/nginx/sites-enabled/minos.site /etc/nginx/sites-enabled/default 2>/dev/null
    ln -s /etc/nginx/sites-available/minos.site /etc/nginx/sites-enabled/

echo -e "$plus Creating services..."
    cp install/minos.service /etc/systemd/system/
    chown -R www-data: /opt/minos/
    chmod -R g+w /opt/minos

# Start all the services
echo -e "$plus Starting services..."
systemctl daemon-reload
systemctl restart rsyslog
systemctl restart nginx

echo -e "\n$plus Minos has been set up! To start, run:"
echo -e "\t systemctl start nginx scoring_engine scoring_web\n"
echo -e "$plus To interact or view the engine, navigate to:"
echo -e "\t http://127.0.0.1\n"
