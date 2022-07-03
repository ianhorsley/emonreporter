#!/bin/bash
# -------------------------------------------------------------
# emonReporter install and update script
# -------------------------------------------------------------
# Assumes emonreporter repository installed via git:
# git clone https://github.com/ianhorsley/emonreporter.git

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
usrdir=${DIR/\/emonreporter/}

echo $DIR
echo $usrdir

echo "Updates"
sudo apt update
#sudo apt-get install -y python3-serial python3-configobj python3-pip python3-pymodbus bluetooth libbluetooth-dev
sudo python -m pip install heatmisercontroller pyownet



#sudo useradd -M -r -G dialout,tty -c "EmonReporter user" emonreporter

# ---------------------------------------------------------
# EmonReporter config file
# ---------------------------------------------------------
echo "- installing Configuration File"
if [ ! -d /etc/emonreporter ]; then
    sudo mkdir /etc/emonreporter
fi

if [ ! -f /etc/emonreporter/emonreporter.conf ]; then
    sudo cp $usrdir/emonreporter/conf/default.emonreporter.conf /etc/emonreporter/emonreporter.conf
    # requires write permission for configuration from emoncms:config module
    sudo chmod 666 /etc/emonreporter/emonreporter.conf

    # Temporary: replace with update to default settings file
    #sed -i "s/loglevel = DEBUG/loglevel = WARNING/" /etc/emonreporter/emonreporter.conf
fi

# ---------------------------------------------------------
# Symlink emonreporter source to /usr/share/emonreporter
# ---------------------------------------------------------
sudo ln -sf $usrdir/emonreporter/src /usr/local/bin/emonreporter

# ---------------------------------------------------------
# Install service
# ---------------------------------------------------------
echo "- installing emonreporter.service"
sudo ln -sf $usrdir/emonreporter/service/emonreporter.service /lib/systemd/system
sudo systemctl enable emonreporter.service
sudo systemctl restart emonreporter.service

state=$(systemctl show emonreporter | grep ActiveState)
echo "- Service $state"
# ---------------------------------------------------------