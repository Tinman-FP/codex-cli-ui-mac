#!/bin/bash
set -euo pipefail

echo "Stopping Tinman engineering stack..."

if ! command -v colima >/dev/null 2>&1; then
  echo "Colima is not installed or not on PATH."
  exit 0
fi

if colima status >/dev/null 2>&1; then
  colima stop
else
  echo "Colima is already stopped."
fi

echo
echo "Engineering stack is sleeping."
