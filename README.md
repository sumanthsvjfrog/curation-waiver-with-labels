# JFrog Catalog Label & Curation Waiver Automation

Automate the creation and assignment of **JFrog Catalog custom labels** to blocked packages identified by **JFrog Curation Audit** — or from your own package list — and use those labels as **waivers inside Curation Policies** to allow approved packages through at scale.

This tool improves on the standard Curation Waiver workflow by giving teams a scriptable, repeatable way to bulk-tag blocked packages with custom catalog labels. Once a label is created and packages are assigned to it, the label can be attached as a waiver to one or more Curation Policies directly from the JFrog Platform UI — allowing all packages under that label to bypass the policy block without requiring individual per-package waiver requests. This makes it ideal for teams managing large sets of approved-but-blocked packages across multiple policies and repositories.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                         Two Input Modes                         │
│                                                                 │
│  [Mode 1] jf ca (Curation Audit)    [Mode 2] packages.csv       │
│             │                                │                  │
│             └──────────────┬─────────────────┘                  │
│                            ▼                                    │
│                  Generate GraphQL Mutation                      │
│                            │                                    │
│               ┌────────────▼─────────────┐                      │
│               │   Label exists in        │                      │
│               │   JFrog Catalog?         │                      │
│               └──────┬───────────┬───────┘                      │
│                    YES           NO                             │
│                      │           │                              │
│                      │      Create Label                        │
│                      │           │                              │
│                      └─────┬─────┘                              │
│                            ▼                                    │
│             Assign Packages to Label via GraphQL                │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │         Add Label as Waiver in Curation Policy UI       │    │
│  │                                                         │    │
│  │  Curation → Policies → Edit Policy → Waivers            │    │
│  │  ➕ Add waiver → Select Label → worksafe_new_label      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                    │
│                            ▼                                    │
│   ✅ Packages allowed through Curation Policy                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

> **NOTE:** This tool requires the **new JFrog Catalog service**. Please validate your platform reflects the new Catalog UI before proceeding.

1. Complete [General configuration tasks required for JFrog Curation](https://jfrog.com/help/r/jfrog-security-user-guide/products/curation/configure-curation)

2. Create your remote repository and connect it to JFrog Curation:
   [Connect Remote Repositories to Curation](https://jfrog.com/help/r/jfrog-security-user-guide/products/curation/configure-repositories/connect-remote-repositories-to-curation)

3. Install and configure the [JFrog CLI](https://jfrog.com/help/r/jfrog-cli):
   ```bash
   jf config add
   ```

4. Ensure the following tools are available on your system:

   | Tool | Purpose |
   |------|---------|
   | `jf` | JFrog CLI — runs Curation Audit |
   | `jq` | JSON parsing (bash script only) |
   | `curl` | GraphQL API calls (bash script only) |
   | `python3` | Required for the Python version |

---

## Usage

Both a **Bash** and **Python** version are provided — they are functionally identical.

### Arguments

| Position / Flag | Description | Example |
|-----------------|-------------|---------|
| `JFROG_URL` | Your JFrog platform URL | `https://myorg.jfrog.io` |
| `JFROG_TOKEN` | JFrog access token | `eyJ0eXAi...` |
| `LABEL_NAME` | Name of the catalog label to create/update | `worksafe_new_label` |
| `--from-file` | *(optional)* Skip curation audit, read from `packages.csv` | |

---

### Mode 1 — From Curation Audit (default)

Runs `jf ca` (Curation Audit) to fetch all blocked packages automatically, then creates or updates the label.

**Bash:**
```bash
chmod +x ./catalog_label.sh
./catalog_label.sh https://myorg.jfrog.io <token> my_label
```

**Python:**
```bash
python3 catalog_label.py https://myorg.jfrog.io <token> my_label
```

---

### Mode 2 — From File (`--from-file`)

Reads packages from an existing `packages.csv` instead of running the curation audit. Useful when you want to label a specific curated list of packages.

**CSV format (`packages.csv`):**
```
package_name,package_version,type
lodash,4.17.15,npm
log4j,2.14.1,maven
requests,2.25.1,pypi
```

**Bash:**
```bash
./catalog_label.sh https://myorg.jfrog.io <token> my_label --from-file
```

**Python:**
```bash
python3 catalog_label.py https://myorg.jfrog.io <token> my_label --from-file
```

---
## From UI
<img width="1728" height="707" alt="image" src="https://github.com/user-attachments/assets/9680fee5-24f7-4ac4-81e3-9fe5b298d3d3" />


## What the Script Does — Step by Step

### Step 1 — Fetch or Load Packages

- **Default mode:** Runs `jf ca --format json`, extracts blocked packages, deduplicates, and writes to `packages.csv`
- **`--from-file` mode:** Reads directly from an existing `packages.csv`

### Step 2 — Generate GraphQL Mutation

Builds a `mutation.graphql` file that maps each package + version to the target label using the Catalog `assignCustomCatalogLabelToPublicPackageVersions` mutation.

### Step 3 — Check if Label Exists

Queries the Catalog GraphQL API using `getLabel`. If the label already exists, creation is skipped — packages are assigned directly. This makes the script safe to re-run without hitting duplicate label errors.

### Step 4 — Create Label *(if needed)*

Creates the custom catalog label via `createCustomCatalogLabel` mutation.

### Step 5 — Assign Packages

Sends the generated `mutation.graphql` to the Catalog API to assign all packages and their versions to the label.

---

## Step 6 — Attach the Label to a Curation Policy Waiver

Once the script has created the catalog label and assigned packages to it, the final step is to **add that label as a waiver** inside your Curation Policy. This tells JFrog Curation to allow the labeled packages through, even if they would otherwise be blocked by the policy.

### How to add the label as a waiver in the UI

1. Navigate to **Platform → Curation → Policies**
2. Open the policy you want to apply the waiver to (e.g. `projectkey-critical-block`)
3. Scroll to the **Waivers** section (Step 4 in the policy wizard)
4. Click **➕ Add waiver**
5. Select **Label** as the waiver type
6. Search for and select the label you created (e.g. `worksafe_new_label`)
7. Click **Next** and save the policy

> The waiver will now allow all packages assigned to that label to pass through the Curation policy, without needing individual per-package waiver requests.

### Example — Policy with label waiver attached

```
Edit Curation Policy
├── ✅ Policy Name       projectkey-critical-block
├── ✅ Scope             Specific repositories → bmc-docker-remote
├── ✅ Policy Condition  Malicious package
├── 4  Waivers
│       This waiver contains the following labels/packages:
│       1 Waived labels  →  worksafe_new_label
│       [+ Add waiver]
└── ✅ Actions & Notifications  Dry run
```

### End-to-End Flow

```
 jf ca / packages.csv
         │
         ▼
  catalog_label.sh / .py
         │
         ├─── Creates label:        worksafe_new_label
         ├─── Assigns packages:     lodash@4.17.15, log4j@2.14.1 ...
         │
         ▼
  JFrog Catalog → Custom Labels → worksafe_new_label
         │
         ▼
  Curation Policy → Waivers → Add waiver → worksafe_new_label
         │
         ▼
  ✅ Blocked packages now allowed through for that policy
```

---

## Output Files

| File | Description |
|------|-------------|
| `packages.csv` | Deduplicated list of blocked packages (name, version, type) |
| `mutation.graphql` | Generated GraphQL mutation sent to the Catalog API |

---

## Example Output

```
Mode: fetching packages from JFrog Curation Audit
Fetching curation audit data...
Generating mutation from: packages.csv
Mutation generated with 12 package(s) -> mutation.graphql
Checking if label 'my_label' exists...
Label 'my_label' does not exist — creating it.
Creating label: my_label...
Assigning packages to label 'my_label'...
Done.
```

---

## Comparison with Standard Curation Waiver Workflow

| | Standard Waiver Flow | This Tool |
|---|---|---|
| Trigger | Developer manually requests waiver via UI | Script runs on demand or in CI |
| Label creation | Auto-created on waiver approval | Created programmatically with custom name |
| Package scope | Per waiver request | Bulk — all blocked packages at once |
| Repeatability | Manual re-approval needed | Re-run script anytime |
| Audit file | Not generated | `packages.csv` kept as artifact |
| Input source | Curation policy UI | Curation Audit CLI or custom CSV |

---

## Files in This Repo

```
.
├── catalog_label.sh       # Bash version
├── catalog_label.py       # Python version (no pip install needed)
├── packages.csv           # Generated or manually provided package list
├── mutation.graphql       # Generated GraphQL mutation (created at runtime)
└── README.md
```

---

## Notes

- The script is **idempotent** — re-running it with the same label name will not create a duplicate; it will just re-assign packages.
- The `packages.csv` generated by the script uses only three columns: `name`, `version`, `type`. The `waiver_allowed` field from the raw curation audit output is intentionally excluded as it is not used in the label assignment.
- Both script versions use **no external dependencies** beyond standard tooling (`jf`, `jq`, `curl` for bash; stdlib only for Python).
