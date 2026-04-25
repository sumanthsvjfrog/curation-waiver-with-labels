#!/bin/bash
JFROG_URL="${1:?Enter JFrog URL e.g. https://myorg.jfrog.io}"
JFROG_TOKEN="${2:?Enter JFrog Token}"
LABEL_NAME="${3:?Enter Label Name e.g. worksafe_new_label}"
LABEL_DESC="test label"
INPUT_FILE="packages.csv"
OUTPUT_FILE="mutation.graphql"
FROM_FILE=false

# Parse optional --from-file flag
for arg in "$@"; do
  [[ "$arg" == "--from-file" ]] && FROM_FILE=true
done

GetCAJson() {
  echo "Fetching curation audit data..."
  echo "n" | jf ca --format json > ca2.json
  sed -n '/^\[/,/^\]/p' ca2.json > ca.json
  cat ca.json | jq -rc '["blocked_package_name","blocked_package_version","type"],
       (.[] | [.blocked_package_name, .blocked_package_version, .type])
       | @csv' | tr -d '"' | sort -u > "$INPUT_FILE"
}

CheckLabelExists() {
  echo "Checking if label '$LABEL_NAME' exists..."

  local query="{ customCatalogLabel { getLabel(name: \"$LABEL_NAME\") { name } } }"

  local response
  response=$(curl -s -X POST "$JFROG_URL/catalog/api/v1/custom/graphql" \
    -H "Authorization: Bearer $JFROG_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg q "$query" '{query: $q}')")

  # If getLabel returns a name, the label exists
  echo "$response" | jq -e '.data.customCatalogLabel.getLabel.name != null' > /dev/null 2>&1
}

CreateLabel() {
  echo "Creating label: $LABEL_NAME..."

  local query="mutation { customCatalogLabel { createCustomCatalogLabel(label: {name: \"$LABEL_NAME\", description: \"$LABEL_DESC\"}) { name description } } }"

  curl -s -X POST "$JFROG_URL/catalog/api/v1/custom/graphql" \
    -H "Authorization: Bearer $JFROG_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg q "$query" '{query: $q}')"
  echo ""
}

generate_mutation() {
  local source_file="${1:-$INPUT_FILE}"

  if [[ ! -f "$source_file" ]]; then
    echo "ERROR: Input file '$source_file' not found."
    exit 1
  fi

  echo "Generating mutation from: $source_file"

  {
    echo "mutation {"
    echo "  customCatalogLabel {"
    echo "    assignCustomCatalogLabelToPublicPackageVersions("
    echo "      publicPackageVersionsLabel: {"
    echo "        publicPackageVersions: ["

    local first=true
    local count=0

    while IFS=',' read -r name version type; do
      # Skip header row or empty lines
      [[ -z "$name" || "$name" == "blocked_package_name" ]] && continue

      if [ "$first" = true ]; then
        first=false
      else
        echo ","
      fi

      echo "          {publicPackage: {name: \"$name\", type: \"$type\"}, version: \"$version\"}"
      ((count++))

    done < "$source_file"

    echo ""
    echo "        ],"
    echo "        labelName: \"$LABEL_NAME\""
    echo "      }"
    echo "    )"
    echo "  }"
    echo "}"
  } > "$OUTPUT_FILE"

  echo "Mutation generated with $count package(s) -> $OUTPUT_FILE"
}

UpdateLabel() {
  echo "Assigning packages to label '$LABEL_NAME'..."

  curl -s -X POST "$JFROG_URL/catalog/api/v1/custom/graphql" \
    -H "Authorization: Bearer $JFROG_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$(jq -Rs '{query: .}' "$OUTPUT_FILE")"
  echo ""
}

# ── Main flow ────────────────────────────────────────────────────────────────

if [ "$FROM_FILE" = true ]; then
  echo "Mode: reading packages from existing file -> $INPUT_FILE"
  if [[ ! -f "$INPUT_FILE" ]]; then
    echo "ERROR: '$INPUT_FILE' not found. Provide a CSV with columns: name,version,type"
    exit 1
  fi
else
  echo "Mode: fetching packages from JFrog Curation Audit"
  GetCAJson
fi

generate_mutation "$INPUT_FILE"

if CheckLabelExists; then
  echo "Label '$LABEL_NAME' already exists — skipping creation, proceeding to assign packages."
else
  echo "Label '$LABEL_NAME' does not exist — creating it."
  CreateLabel
fi

UpdateLabel
echo "Done."
