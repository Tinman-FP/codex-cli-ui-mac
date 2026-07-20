#!/bin/bash
set -euo pipefail

echo "Starting Tinman engineering stack..."

if ! command -v colima >/dev/null 2>&1; then
  echo "Colima is not installed or not on PATH."
  exit 1
fi

if colima status >/dev/null 2>&1; then
  echo "Colima is already running."
else
  colima start
fi

echo
echo "Docker status:"
docker ps

echo
echo "Available engineering images:"
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | awk 'NR==1 || /openfoam|su2|qblade|paraview|gmsh|calculix/i'

echo
echo "Engineering stack is ready."
