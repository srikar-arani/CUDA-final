#!/bin/bash

# This script setup AP mode and client mode switch. 
# https://unix.stackexchange.com/questions/459942/using-systemctl-edit-via-bash-script
# run as sudo.


# disable debian networking and dhcpcd
# sudo -Es
systemctl mask networking.service dhcpcd.service

if [ -f "/etc/network/interfaces" ]
then
    mv /etc/network/interfaces /etc/network/interfaces~
fi

if [ "NO" != "$(grep resolvconf= /etc/resolvconf.conf | (IFS='='; read a b ; echo $b))" ]
then 
  sed -i '1i resolvconf=NO' /etc/resolvconf.conf
fi



# enable systemd-networkd
systemctl enable systemd-networkd.service systemd-resolved.service
ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf 

cat > /etc/wpa_supplicant/wpa_supplicant-wlan0.conf <<EOF
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="Aptitude_Wireless"
    psk="AMS@125Cremona"
}
EOF

chmod 600 /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
systemctl disable wpa_supplicant.service
systemctl enable wpa_supplicant@wlan0.service

# generate random freq
Freq=$(($(($(($RANDOM%11))*5))+2412))
# setup wpa_supplicant as AP with ap0
cat > /etc/wpa_supplicant/wpa_supplicant-ap0.conf <<EOF
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="$1"
    mode=2
    key_mgmt=WPA-PSK
    proto=RSN WPA
    psk="aptitude"
    frequency=$Freq
}
EOF
chmod 600 /etc/wpa_supplicant/wpa_supplicant-ap0.conf

#configure interface 
cat > /etc/systemd/network/08-wlan0.network <<EOF
[Match]
Name=wlan0
[Network]
DHCP=yes
[DHCP]
RouteMetric=20
UseDomains=yes
EOF

cat > /etc/systemd/network/12-ap0.network <<EOF
[Match]
Name=ap0
[Network]
Address=192.168.0.1/24
DHCPServer=yes
[DHCPServer]
DNS=84.200.69.80 1.1.1.1
EOF

#Modify service for access point to use ap0
systemctl disable wpa_supplicant@ap0.service

# normally use this
# sudo systemctl edit --full wpa_supplicant@ap0.service 

# to use it in script, 
# need to write the service config, however, cannot cat: permission denied,
# so use python to create the file.
# /etc/systemd/system/wpa_supplicant@ap0.service 
# cat > /etc/systemd/system/wpa_supplicant@ap0.service <<EOF
# [Unit]
# Description=WPA supplicant daemon (interface-specific version)
# Requires=sys-subsystem-net-devices-wlan0.device
# After=sys-subsystem-net-devices-wlan0.device
# Conflicts=wpa_supplicant@wlan0.service
# Before=network.target
# Wants=network.target

# [Service]
# Type=simple
# ExecStartPre=/sbin/iw dev wlan0 interface add ap0 type __ap
# ExecStart=/sbin/wpa_supplicant -c/etc/wpa_supplicant/wpa_supplicant-%I.conf -Dnl80211,wext -i%I
# ExecStopPost=/sbin/iw dev ap0 del

# [Install]
# Alias=multi-user.target.wants/wpa_supplicant@%i.service
# EOF


# default mode should be client mode, or can be access point mode.
systemctl enable wpa_supplicant@wlan0.service
systemctl disable wpa_supplicant@ap0.service
# reboot

# switch servce by 
#  sudo systemctl start wpa_supplicant@ap0.service
#  sudo systemctl start wpa_supplicant@wlan0.service



# problems: the wlan interface doesn't support scanning. 


# systemctl disable wpa_supplicant@wlan0.service
# systemctl enable wpa_supplicant@ap0.service

