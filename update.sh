#!/bin/bash
AUTHOR='barsikus007 <barsikus07@gmail.com>'

(
    installed_version=$(dpkg -s rockpi-penta | grep '^Version:' | sed -e 's/Version: //g')
    latest_version=$(curl -s https://api.github.com/repos/barsikus007/rockpi-penta/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
    package_file=/tmp/rockpi-penta-"${latest_version}".deb
    if [ "$installed_version" != "$latest_version" ]; then
        echo "New version available: $latest_version"
        echo "Installed version: $installed_version"
        echo "Updating..."
        curl -sL --output "$package_file" "https://github.com/barsikus007/rockpi-penta/releases/download/${latest_version}/rockpi-penta-${latest_version}.deb"
        sudo dpkg -i "$package_file"
        rm -f "$package_file"
        echo "Done."
    else
        echo "No updates available."
    fi
)
