#!/usr/bin/env python3
import argparse
import csv
import json
import os
import subprocess
import sys

INPUT_FILE = "packages.csv"
OUTPUT_FILE = "mutation.graphql"
LABEL_DESC = "test label"


def graphql_request(url, token, query):
    import urllib.request
    payload = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        f"{url}/catalog/api/v1/custom/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_ca_json():
    print("Fetching curation audit data...")
    result = subprocess.run(
        ["jf", "ca", "--format", "json"],
        input="n",
        capture_output=True,
        text=True,
    )

    # Extract the JSON array from output
    output = result.stdout
    start = output.find("[")
    end = output.rfind("]") + 1
    if start == -1 or end == 0:
        print("ERROR: Could not find JSON array in curation audit output.")
        sys.exit(1)

    packages = json.loads(output[start:end])

    # Deduplicate and write CSV
    rows = set()
    for pkg in packages:
        name = pkg.get("blocked_package_name", "")
        version = pkg.get("blocked_package_version", "")
        pkg_type = pkg.get("type", "")
        if name:
            rows.add((name, version, pkg_type))

    with open(INPUT_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["blocked_package_name", "blocked_package_version", "type"])
        for row in sorted(rows):
            writer.writerow(row)

    print(f"Written {len(rows)} package(s) to {INPUT_FILE}")


def check_label_exists(url, token, label_name):
    print(f"Checking if label '{label_name}' exists...")
    query = f'{{ customCatalogLabel {{ getLabel(name: "{label_name}") {{ name }} }} }}'
    try:
        response = graphql_request(url, token, query)
        name = response.get("data", {}).get("customCatalogLabel", {}).get("getLabel", {})
        return name is not None and name.get("name") is not None
    except Exception as e:
        print(f"WARNING: Label check failed: {e}")
        return False


def create_label(url, token, label_name):
    print(f"Creating label: {label_name}...")
    query = (
        f'mutation {{ customCatalogLabel {{ createCustomCatalogLabel('
        f'label: {{name: "{label_name}", description: "{LABEL_DESC}"}}) '
        f'{{ name description }} }} }}'
    )
    response = graphql_request(url, token, query)
    if "errors" in response:
        print(f"ERROR creating label: {response['errors']}")
        sys.exit(1)
    print(f"Label '{label_name}' created successfully.")


def generate_mutation(label_name, source_file=INPUT_FILE):
    if not os.path.exists(source_file):
        print(f"ERROR: Input file '{source_file}' not found.")
        sys.exit(1)

    print(f"Generating mutation from: {source_file}")

    lines = []
    lines.append("mutation {")
    lines.append("  customCatalogLabel {")
    lines.append("    assignCustomCatalogLabelToPublicPackageVersions(")
    lines.append("      publicPackageVersionsLabel: {")
    lines.append("        publicPackageVersions: [")

    entries = []
    with open(source_file, newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0] in ("", "blocked_package_name"):
                continue
            name, version, pkg_type = row[0], row[1], row[2]
            entries.append(
                f'          {{publicPackage: {{name: "{name}", type: "{pkg_type}"}}, version: "{version}"}}'
            )

    lines.append(",\n".join(entries))
    lines.append("        ],")
    lines.append(f'        labelName: "{label_name}"')
    lines.append("      }")
    lines.append("    )")
    lines.append("  }")
    lines.append("}")

    with open(OUTPUT_FILE, "w") as f:
        f.write("\n".join(lines))

    print(f"Mutation generated with {len(entries)} package(s) -> {OUTPUT_FILE}")


def update_label(url, token, label_name):
    print(f"Assigning packages to label '{label_name}'...")
    with open(OUTPUT_FILE) as f:
        query = f.read()
    response = graphql_request(url, token, query)
    if "errors" in response:
        print(f"ERROR assigning packages: {response['errors']}")
        sys.exit(1)
    print("Packages assigned successfully.")


def main():
    parser = argparse.ArgumentParser(description="JFrog Catalog Label Manager")
    parser.add_argument("jfrog_url", help="JFrog URL e.g. https://myorg.jfrog.io")
    parser.add_argument("jfrog_token", help="JFrog access token")
    parser.add_argument("label_name", help="Label name e.g. worksafe_new_label")
    parser.add_argument(
        "--from-file",
        action="store_true",
        help=f"Read packages from existing {INPUT_FILE} instead of running curation audit",
    )
    args = parser.parse_args()

    if args.from_file:
        print(f"Mode: reading packages from existing file -> {INPUT_FILE}")
        if not os.path.exists(INPUT_FILE):
            print(f"ERROR: '{INPUT_FILE}' not found. Provide a CSV with columns: name,version,type")
            sys.exit(1)
    else:
        print("Mode: fetching packages from JFrog Curation Audit")
        get_ca_json()

    generate_mutation(args.label_name)

    if check_label_exists(args.jfrog_url, args.jfrog_token, args.label_name):
        print(f"Label '{args.label_name}' already exists — skipping creation, proceeding to assign packages.")
    else:
        print(f"Label '{args.label_name}' does not exist — creating it.")
        create_label(args.jfrog_url, args.jfrog_token, args.label_name)

    update_label(args.jfrog_url, args.jfrog_token, args.label_name)
    print("Done.")


if __name__ == "__main__":
    main()
