#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  # Tools pre-installed in analyze-debian-13 image
  :
else
  set -x

  # Generate SBOM from uv.lock (using uv)
  uv export --quiet --format cyclonedx1.5 --output-file sbom-uv.cdx.json
  uv tool run --from cyclonedx-bom cyclonedx-py environment "$(uv python find)"\
    --gather-license-texts --output-reproducible --output-file sbom.cdx.json

  # Generate SBOM from uv.lock
  #syft uv.lock:uv-lock --output spdx-json > sbom.spdx.json

  # Generate SBOM from source tree
  syft dir:. --output spdx-json > sbom.spdx.json

  # Scan SBOM with grype (fail on critical vulnerabilities with --fail-on critical)
  grype sbom:sbom.spdx.json --output sarif > vuln-scan.sarif
  grype sbom:sbom.spdx.json
  #grype sbom:sbom.cdx.json

  # Scan SBOM with trivy
  trivy sbom sbom.spdx.json
  #trivy sbom sbom.cdx.json

  # Scan uv.lock directly against OSV database
  osv-scanner --lockfile=uv.lock --lockfile sbom.spdx.json
  #osv-scanner scan source --lockfile uv.lock --lockfile sbom.cdx.json
fi
