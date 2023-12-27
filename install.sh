#!/bin/bash
AUTHOR='barsikus007 <barsikus07@gmail.com>'
VERSION='0.12.11'
PI_MODEL=`tr -d '\0' < /proc/device-tree/model`
PI_DEB="https://github.com/barsikus007/rockpi-penta/releases/download/${VERSION}/rockpi-penta-${VERSION}.deb"
MRAASRC="https://github.com/radxa-pkg/mraa"
SSD1306="https://cos.setq.io/rockpi/pypi/Adafruit_SSD1306-v1.6.2.zip"
OVERLAY="https://raw.githubusercontent.com/barsikus007/rockpi-penta/master/rockpi-penta-3a.dts"
DISTRO=`cat /etc/os-release | grep VERSION_CODENAME | sed -e 's/VERSION_CODENAME\=//g'`

confirm() {
  printf "%s [Y/n] " "$1"
  read resp < /dev/tty
  if [ "$resp" == "" ] || [ "$resp" == "Y" ] || [ "$resp" == "y" ] || [ "$resp" == "yes" ]; then
    return 0
  fi
  if [ "$2" == "abort" ]; then
    echo -e "Abort.\n"
    exit 0
  fi
  return 1
}

add_repo() {
  if [ ! -f /etc/apt/sources.list.d/radxa.list ]; then
    temp=$(mktemp)
    curl -L --output "$temp" "https://github.com/radxa-pkg/radxa-archive-keyring/releases/latest/download/radxa-archive-keyring_$(curl -L https://github.com/radxa-pkg/radxa-archive-keyring/releases/latest/download/VERSION)_all.deb"
    sudo dpkg -i "$temp"
    rm -f "$temp"
    source /etc/os-release
    sudo tee /etc/apt/sources.list.d/radxa.list <<< "deb [signed-by=/usr/share/keyrings/radxa-archive-keyring.gpg] https://radxa-repo.github.io/$VERSION_CODENAME/ $VERSION_CODENAME main"
    sudo apt update
  fi
  # for libpython3.9 for mraa
  if [ ! -f /etc/apt/sources.list.d/deadsnakes-ubuntu-ppa-"$DISTRO".list ]; then
    sudo add-apt-repository ppa:deadsnakes/ppa -y
  fi
}

apt_check() {
  packages="unzip gcc python3-dev python3-setuptools python3-setuptools-scm python3-pip python3-pil"
  need_packages=""

  if [ "$DISTRO" == "bullseye" ]; then
    packages="$packages libc6 libjson-c5 libjson-c-dev libgtest-dev libgcc-s1 libstdc++6"
  elif [ "$DISTRO" == "focal" ] || [ "$DISTRO" == "jammy" ]; then
    packages="$packages mraa-tools python3-mraa"
  else
    packages="$packages libmraa"
  fi

  idx=1
  for package in $packages; do
    if ! apt list --installed 2> /dev/null | grep "^$package/" > /dev/null; then
      pkg=$(echo "$packages" | cut -d " " -f $idx)
      need_packages="$need_packages $pkg"
    fi
    ((++idx))
  done

  if [ "$need_packages" != "" ]; then
    echo -e "\nPackage(s) $need_packages is required.\n"
    confirm "Would you like to apt-get install the packages?" "abort"
    apt-get install --no-install-recommends $need_packages -y
  fi
}

mraa_build() {
  if command -v mraa-gpio &> /dev/null; then
    echo -e "\nmraa is already installed\n"
    return
  fi
  if [ "$DISTRO" == "jammy" ] || [ "$DISTRO" == "bullseye" ]; then
    echo -e "\nBuilding mraa...\n"
    pushd ~
    apt-get install --no-install-recommends swig cmake build-essential -y
    git clone -b master "$MRAASRC.git" && cd mraa
    sed -i 's/"Force tests to run with python3" OFF/"Force tests to run with python3" ON/' CMakeLists.txt
    mkdir -p build && cd build
    cmake .. && make && make install && ldconfig
    mraa-gpio version
    popd
  fi
}

deb_install() {
  TEMP_DEB="$(mktemp)"
  curl -sL "$PI_DEB" -o "$TEMP_DEB"
  dpkg -i "$TEMP_DEB"
  rm -f "$TEMP_DEB"
}

dtb_enable() {
  if [[ "$PI_MODEL" =~ "ROCK3" ]]; then
    TEMP_DIR="$(mktemp -d)"
    TEMP_DTS=$TEMP_DIR/rockpi-penta-3a.dts
    curl -sL "$OVERLAY" -o "$TEMP_DTS"
    armbian-add-overlay "$TEMP_DTS"
    rm -rf "$TEMP_DIR"
  else
    fname='rockpi-penta'
    mkdir -p /boot/overlay-user
    curl -sL https://cos.setq.io/rockpi/dtb/rockpi-penta.dtbo -o /boot/overlay-user/${fname}.dtbo
  
    ENV='/boot/armbianEnv.txt'
    [ -f /boot/dietpiEnv.txt ] && ENV='/boot/dietpiEnv.txt'
  
    if grep -q '^user_overlays=' "$ENV"; then
      line=$(grep '^user_overlays=' "$ENV" | cut -d'=' -f2)
      if grep -qE "(^|[[:space:]])${fname}([[:space:]]|$)" <<< $line; then
        echo "Overlay ${fname} was already added to /boot/armbianEnv.txt, skip"
      else
        sed -i -e "/^user_overlays=/ s/$/ ${fname}/" "$ENV"
      fi
    else
      sed -i -e "\$auser_overlays=${fname}" "$ENV"
    fi
  fi
}

pip_install() {
  TEMP_ZIP="$(mktemp)"
  TEMP_DIR="$(mktemp -d)"
  curl -sL "$SSD1306" -o "$TEMP_ZIP"
  unzip "$TEMP_ZIP" -d "$TEMP_DIR" > /dev/null
  cd "${TEMP_DIR}/Adafruit_SSD1306-v1.6.2"
  python3 setup.py install && cd -
  rm -rf "$TEMP_ZIP" "$TEMP_DIR"
}

main() {
  if [[ "$PI_MODEL" =~ "ROCK" ]]; then
    add_repo
    apt_check
    pip_install
    deb_install
    mraa_build
    dtb_enable
  else
    echo 'nothing'
  fi
}

main
