#!/bin/bash
AUTHOR='barsikus007 <barsikus07@gmail.com>'

(
    installed_version=$(dpkg -s rockpi-penta | grep '^Version:' | sed -e 's/Version: //g')
    latest_version=$(curl -s https://api.github.com/repos/barsikus007/rockpi-penta/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
    if [ "$installed_version" != "$latest_version" ]; then
        echo "New version available: $latest_version"
        echo "Installed version: $installed_version"
        echo "Updating..."
        curl -L --output /tmp/rockpi-penta-"${latest_version}".deb "https://github.com/barsikus007/rockpi-penta/releases/download/${latest_version}/rockpi-penta-${latest_version}.deb"
        sudo dpkg -i /tmp/rockpi-penta.deb
        rm -f /tmp/rockpi-penta.deb
        echo "Done."
    else
        echo "No updates available."
    fi
)
