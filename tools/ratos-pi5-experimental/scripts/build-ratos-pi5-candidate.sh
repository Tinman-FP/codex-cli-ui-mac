#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  build-ratos-pi5-candidate.sh --source /path/to/RatOS.img.xz --out ./work

Options:
  --source PATH       Official RatOS Raspberry Pi image, .img or .img.xz
  --out PATH          Output folder
  --extra-gib N       Extra GiB to add to the root partition (default: 4)
  --kernel VERSION    Raspberry Pi 2712 kernel version (default: 6.12.93+rpt-rpi-2712)
  -h, --help          Show this help

This creates an experimental Raspberry Pi 5 boot-grafted candidate image.
The source image is copied first and is not modified.
EOF
}

source_image=""
out_dir=""
extra_gib="4"
kernel_version="6.12.93+rpt-rpi-2712"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      source_image="${2:-}"
      shift 2
      ;;
    --out)
      out_dir="${2:-}"
      shift 2
      ;;
    --extra-gib)
      extra_gib="${2:-}"
      shift 2
      ;;
    --kernel)
      kernel_version="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$source_image" || -z "$out_dir" ]]; then
  usage >&2
  exit 2
fi

if [[ ! -f "$source_image" ]]; then
  echo "Source image not found: $source_image" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required." >&2
  exit 1
fi

if [[ "$source_image" == *.xz ]] && ! command -v xz >/dev/null 2>&1; then
  echo "xz is required to expand .img.xz files." >&2
  exit 1
fi

mkdir -p "$out_dir/debs"
out_dir="$(cd "$out_dir" && pwd)"
source_abs="$(cd "$(dirname "$source_image")" && pwd)/$(basename "$source_image")"

source_img="$out_dir/source.img"
candidate_img="$out_dir/ratos-pi5-candidate.img"

echo "Preparing source image..."
if [[ "$source_abs" == *.xz ]]; then
  xz -T0 -dc "$source_abs" > "$source_img"
else
  cp "$source_abs" "$source_img"
fi

cp "$source_img" "$candidate_img"

echo "Patching candidate image inside Docker..."
docker run --rm -i --platform linux/arm64 --privileged \
  -v "$out_dir:/work" \
  ubuntu:22.04 \
  bash -s -- "$kernel_version" "$extra_gib" <<'DOCKER_SCRIPT'
set -euo pipefail

kernel_version="$1"
extra_gib="$2"
image="/work/ratos-pi5-candidate.img"
debs="/work/debs"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"

export DEBIAN_FRONTEND=noninteractive
apt-get update >/dev/null
apt-get install -y ca-certificates dosfstools e2fsprogs gnupg kmod parted wget xz-utils >/dev/null

install -d -m 0755 /usr/share/keyrings
wget -qO- https://archive.raspberrypi.org/debian/raspberrypi.gpg.key \
  | gpg --dearmor -o /usr/share/keyrings/raspberrypi-archive-keyring.gpg
printf '%s\n' \
  "deb [signed-by=/usr/share/keyrings/raspberrypi-archive-keyring.gpg arch=arm64] http://archive.raspberrypi.org/debian/ bookworm main" \
  >/etc/apt/sources.list.d/raspberrypi-bookworm.list
apt-get update >/dev/null

mkdir -p "$debs"
cd "$debs"
apt-get download "linux-image-$kernel_version" raspi-firmware >/dev/null

kernel_deb="$(ls -1 "linux-image-${kernel_version}"*.deb | head -1)"
firmware_deb="$(ls -1 raspi-firmware_*.deb | head -1)"

parted -s "$image" unit s print >/work/partition-before.txt
truncate -s +"${extra_gib}G" "$image"
parted -s "$image" resizepart 2 100%
parted -s "$image" unit s print >/work/partition-after.txt

partition_line() {
  local number="$1"
  parted -sm "$image" unit s print | awk -F: -v n="$number" '$1 == n {print $0}'
}

sector_value() {
  printf '%s\n' "$1" | cut -d: -f "$2" | tr -d 's'
}

boot_line="$(partition_line 1)"
root_line="$(partition_line 2)"
boot_start="$(sector_value "$boot_line" 2)"
boot_size="$(sector_value "$boot_line" 4)"
root_start="$(sector_value "$root_line" 2)"

boot_offset=$((boot_start * 512))
boot_size_bytes=$((boot_size * 512))
root_offset=$((root_start * 512))

root_loop="$(losetup -f --show -o "$root_offset" "$image")"
e2fsck -f -y "$root_loop" >/work/rootfs-pre-resize-fsck.txt
resize2fs "$root_loop" >/work/rootfs-resize.txt
losetup -d "$root_loop"

mkdir -p /mnt/ratos-root /mnt/ratos-boot

cleanup() {
  set +e
  mountpoint -q /mnt/ratos-boot && umount /mnt/ratos-boot
  mountpoint -q /mnt/ratos-root && umount /mnt/ratos-root
}
trap cleanup EXIT

mount -o loop,offset="$root_offset" "$image" /mnt/ratos-root
mount -o loop,offset="$boot_offset",sizelimit="$boot_size_bytes" "$image" /mnt/ratos-boot

mkdir -p /mnt/ratos-root/var/local/ratos-pi5-graft
mkdir -p /mnt/ratos-boot/overlays

cp /mnt/ratos-boot/config.txt "/mnt/ratos-boot/config.txt.pre-pi5-graft-$stamp"
cp /mnt/ratos-boot/cmdline.txt "/mnt/ratos-boot/cmdline.txt.pre-pi5-graft-$stamp"

dpkg-deb -x "$debs/$kernel_deb" /mnt/ratos-root
dpkg-deb -x "$debs/$firmware_deb" /mnt/ratos-root

cp -R /mnt/ratos-root/usr/lib/raspi-firmware/. /mnt/ratos-boot/
cp "/mnt/ratos-root/usr/lib/linux-image-$kernel_version/broadcom"/bcm27*.dtb /mnt/ratos-boot/
cp -R "/mnt/ratos-root/usr/lib/linux-image-$kernel_version/overlays"/. /mnt/ratos-boot/overlays/
cp "/mnt/ratos-root/boot/vmlinuz-$kernel_version" /mnt/ratos-boot/kernel_2712.img
cp "/mnt/ratos-root/boot/vmlinuz-$kernel_version" "/mnt/ratos-boot/vmlinuz-$kernel_version"

depmod -b /mnt/ratos-root "$kernel_version"

if ! grep -q "Tinman Pi 5 experimental boot graft" /mnt/ratos-boot/config.txt; then
  {
    printf '\n'
    printf '####################################################\n'
    printf '#### Tinman Pi 5 experimental boot graft\n'
    printf '#### Added by build-ratos-pi5-candidate.sh on %s\n' "$stamp"
    printf '#### Keeps RatOS Bullseye userland intact and boots a Pi 5 2712 kernel.\n'
    printf '####################################################\n'
    printf '[pi5]\n'
    printf 'arm_64bit=1\n'
    printf 'kernel=kernel_2712.img\n'
    printf 'dtoverlay=vc4-kms-v3d-pi5\n'
    printf 'dtoverlay=disable-bt-pi5\n'
    printf '\n'
    printf '[all]\n'
  } >>/mnt/ratos-boot/config.txt
fi

cat >/mnt/ratos-root/var/local/ratos-pi5-graft/manifest.txt <<EOF
RatOS Pi 5 experimental boot graft
created_utc=$stamp
kernel_version=$kernel_version
kernel_package=$kernel_deb
firmware_package=$firmware_deb

What changed:
- Added Raspberry Pi 5 2712 kernel modules under /lib/modules/$kernel_version.
- Added matching Raspberry Pi 5 DTBs and overlays to the FAT boot partition.
- Added current Raspberry Pi firmware blobs to the FAT boot partition.
- Added kernel_2712.img to the FAT boot partition.
- Appended a [pi5] boot stanza to config.txt.

What did not change:
- RatOS userland remains the original image userland.
- This image has not been boot-tested on a Raspberry Pi 5 by this script.
EOF

cp /mnt/ratos-root/var/local/ratos-pi5-graft/manifest.txt /mnt/ratos-boot/ratos-pi5-graft-manifest.txt

printf 'BOOT_FILES\n' >/work/pi5-graft-verification.txt
ls -lh /mnt/ratos-boot/kernel_2712.img /mnt/ratos-boot/bcm2712-rpi-5-b.dtb /mnt/ratos-boot/overlays/vc4-kms-v3d-pi5.dtbo >>/work/pi5-graft-verification.txt
printf '\nROOT_MODULES\n' >>/work/pi5-graft-verification.txt
ls -ld "/mnt/ratos-root/lib/modules/$kernel_version" >>/work/pi5-graft-verification.txt
printf '\nCOMPAT_CONFIG\n' >>/work/pi5-graft-verification.txt
grep -E '^(CONFIG_COMPAT|CONFIG_EXT4_FS|CONFIG_MMC|CONFIG_VFAT_FS|CONFIG_DEVTMPFS)=' "/mnt/ratos-root/boot/config-$kernel_version" >>/work/pi5-graft-verification.txt
printf '\nHASHES\n' >>/work/pi5-graft-verification.txt
sha256sum /mnt/ratos-boot/kernel_2712.img /mnt/ratos-boot/bcm2712-rpi-5-b.dtb >>/work/pi5-graft-verification.txt
printf '\nCONFIG_TAIL\n' >>/work/pi5-graft-verification.txt
tail -40 /mnt/ratos-boot/config.txt >>/work/pi5-graft-verification.txt

sync
umount /mnt/ratos-boot
umount /mnt/ratos-root
trap - EXIT

boot_loop="$(losetup -f --show -o "$boot_offset" --sizelimit "$boot_size_bytes" "$image")"
root_loop="$(losetup -f --show -o "$root_offset" "$image")"
{
  printf '\nFAT_CHECK\n'
  fsck.fat -vn "$boot_loop" || true
  printf '\nEXT4_CHECK\n'
  e2fsck -f -n "$root_loop" || true
} >>/work/pi5-graft-verification.txt
losetup -d "$boot_loop"
losetup -d "$root_loop"
DOCKER_SCRIPT

echo "Candidate image: $candidate_img"
echo "Verification: $out_dir/pi5-graft-verification.txt"
