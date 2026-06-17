# 📊 Self-Hosted GitHub Analytics Setup

## What you get

| What | How it's generated | Where it lives |
|------|-------------------|-----------------|
| `stats.json` | `update-stats.yml` GitHub Action (runs daily + on every push) | `hynko431/hynko431` repo root |
| `metrics.svg` | `metrics.yml` GitHub Action using `lowlighter/metrics` (runs daily) | `hynko431/hynko431` repo root |
| Badge images | Shields.io reads `stats.json` from `raw.githubusercontent.com` | GitHub's own CDN |
| Profile view counter | `komarev.com/ghpvc` — a lightweight counter, not Vercel | External (single tiny service) |

**Everything except the profile-view pixel lives in your own repo.** No Vercel, no third-party stats server.

---

## Setup steps

### 1. Copy the workflow files into your profile repo

```
hynko431/hynko431/
├── .github/
│   └── workflows/
│       ├── update-stats.yml    ← copy this
│       └── metrics.yml         ← copy this
├── stats.json                  ← auto-created by the workflow on first run
└── metrics.svg                 ← auto-created by the workflow on first run
```

### 2. Enable Actions on your profile repo

Go to `https://github.com/hynko431/hynko431/settings/actions` and make sure:

- Actions are **allowed**
- Workflow permissions → set to **"Read and write permissions"** (so the bot can commit `stats.json` and `metrics.svg` back)

### 3. Run manually the first time

Go to **Actions → Update GitHub Stats → Run workflow** (and same for **Generate Metrics SVG**).

This creates `stats.json` and `metrics.svg` immediately without waiting for the cron trigger.

### 4. Paste the README section

The analytics section is already included in your `README.md`. It includes:
- Dynamic badges that pull live values from `stats.json`
- Your `metrics.svg` visual analytics
- All self-hosted, no external dependencies

---

## How the dynamic badges work

The badges use Shields.io's `dynamic/json` endpoint:

```
https://img.shields.io/badge/dynamic/json
  ?url=https://raw.githubusercontent.com/hynko431/hynko431/main/stats.json
  &query=$.total_contributions
  &label=Total Contributions
  &color=2ea44f
  &style=for-the-badge
```

**How it works:**
1. Shields.io fetches your `stats.json` file (which is just a file on GitHub)
2. It reads the value at the JSON path you specify (e.g., `$.total_contributions`)
3. It renders the badge with that value
4. Re-fetches every few minutes on its own cache cycle
5. Badges update automatically every time your Action commits a new `stats.json`

---

## What updates automatically

| Event | Triggers |
|-------|----------|
| Every midnight UTC | Both workflows run on cron |
| Any push to `main` | `update-stats.yml` runs immediately |
| Manual dispatch | Both workflows have `workflow_dispatch` — run anytime from the Actions tab |

After each run:
- `stats.json` gets a fresh commit (only if values changed, thanks to `git diff --cached --quiet`)
- Badges on your README update within minutes

---

## Customising `metrics.svg`

The `metrics.yml` workflow uses `lowlighter/metrics`. You can add or remove plugins:

```yaml
plugin_calendar: yes           # contribution heatmap
plugin_languages: yes          # language breakdown bar
plugin_activity: yes           # recent activity feed
plugin_achievements: yes       # GitHub achievements (add this if you want it)
plugin_notable: yes            # notable contributions to other repos
```

**Full plugin list:** https://github.com/lowlighter/metrics/blob/master/README.md

**Current configuration in your workflow:**
- Base sections: header, activity, community, repositories
- Calendar: 2 years of contribution history
- Languages: 8 languages shown (ignoring HTML, CSS, shell, Dockerfile, etc.)
- Activity: 6 recent events from last 30 days
- Theme: dark, large display, Asia/Kolkata timezone

---

## What data does `stats.json` contain?

```json
{
  "total_contributions": 969,              // All-time contributions across all years
  "contributions_this_year": 456,          // Contributions in current calendar year
  "pull_requests_opened": 24,              // All pull requests you opened
  "pull_requests_merged": 18,              // Pull requests that have been merged
  "pull_requests_reviewed": 42,            // Pull requests you reviewed
  "issues_opened": 15,                     // Issues you opened
  "issues_closed": 12,                     // Issues you closed
  "repositories": 32,                      // Public repositories
  "stars": 156,                            // Total stars earned across all repos
  "updated_at": "2026-06-17T00:15:32Z"    // Last update timestamp (UTC)
}
```

---

## Badge URLs (for reference)

If you want to customize or move the badges, here are the URLs:

**Total Contributions:**
```
https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fhynko431%2Fhynko431%2Fmain%2Fstats.json&query=%24.total_contributions&label=Total%20Contributions&color=2ea44f&style=for-the-badge&logo=github&logoColor=white
```

**Pull Requests Opened:**
```
https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fhynko431%2Fhynko431%2Fmain%2Fstats.json&query=%24.pull_requests_opened&label=PRs%20Opened&color=0075ca&style=for-the-badge&logo=git&logoColor=white
```

**Pull Requests Merged:**
```
https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fhynko431%2Fhynko431%2Fmain%2Fstats.json&query=%24.pull_requests_merged&label=PRs%20Merged&color=6f42c1&style=for-the-badge&logo=git&logoColor=white
```

**Pull Requests Reviewed:**
```
https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fhynko431%2Fhynko431%2Fmain%2Fstats.json&query=%24.pull_requests_reviewed&label=PRs%20Reviewed&color=28a745&style=for-the-badge&logo=git&logoColor=white
```

**Issues Opened:**
```
https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fhynko431%2Fhynko431%2Fmain%2Fstats.json&query=%24.issues_opened&label=Issues%20Opened&color=ffc107&style=for-the-badge&logo=github&logoColor=white
```

**Issues Closed:**
```
https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fhynko431%2Fhynko431%2Fmain%2Fstats.json&query=%24.issues_closed&label=Issues%20Closed&color=17a2b8&style=for-the-badge&logo=github&logoColor=white
```

**Repositories:**
```
https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fhynko431%2Fhynko431%2Fmain%2Fstats.json&query=%24.repositories&label=Repositories&color=e36209&style=for-the-badge&logo=folder&logoColor=white
```

**Stars:**
```
https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fhynko431%2Fhynko431%2Fmain%2Fstats.json&query=%24.stars&label=Stars%20Earned&color=f9c513&style=for-the-badge&logo=star&logoColor=white
```

---

## No secrets needed

`${{ secrets.GITHUB_TOKEN }}` is automatically available in every GitHub Actions run — you don't need to create any Personal Access Token or add any secrets manually. It's built-in and refreshed for each workflow execution.

---

## Troubleshooting

### Badges show "invalid" or broken

**Cause:** `stats.json` doesn't exist yet or has the wrong format.

**Fix:** 
1. Go to **Actions → Update GitHub Stats → Run workflow** manually
2. Wait 2 minutes for the workflow to complete
3. Check that `stats.json` appears in your repo root
4. Refresh your README page

### Metrics SVG doesn't appear

**Cause:** `metrics.yml` hasn't run yet or didn't complete successfully.

**Fix:**
1. Go to **Actions → Generate Metrics SVG → Run workflow** manually
2. Check the workflow logs for errors
3. Ensure you have the `lowlighter/metrics@latest` action in your workflow

### Workflow fails with "Permission denied"

**Cause:** GitHub Actions doesn't have write permissions.

**Fix:**
1. Go to your repo **Settings → Actions → General**
2. Under "Workflow permissions," select **"Read and write permissions"**
3. Click **Save**

---

## Architecture diagram

```
Your Profile Repo (hynko431/hynko431)
│
├── .github/workflows/
│   ├── update-stats.yml          ← Fetches data from GitHub API
│   └── metrics.yml               ← Generates visual SVG
│
├── stats.json                    ← Generated JSON (committed daily)
│   └── Read by → Shields.io (dynamic badges)
│
├── metrics.svg                   ← Generated SVG (committed daily)
│   └── Embedded in README
│
└── README.md                     ← Displays badges + metrics.svg
    └── Viewed by → GitHub users
```

---

## Next steps

1. ✅ Workflows are set up (`update-stats.yml` and `metrics.yml`)
2. ✅ README has analytics section with badges and metrics
3. 📋 Run workflows manually to generate initial `stats.json` and `metrics.svg`
4. 🎯 Everything else happens automatically via cron and commits

Enjoy your self-hosted analytics! 🚀
