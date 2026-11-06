# The Hushmark GitHub App: set-up guide

The GitHub App gives teams a **one-click install** across many repositories and lets a
maintainer re-run a review by commenting `/hushmark`. It runs the same review as the GitHub
Action (`service.run_check`), so the check, the receipt and the NEAR anchor are identical.
Decision: [ADR-0010](../adr/0010-github-app-and-mcp-server.md).

Use **either** the App **or** the Action on a repository, not both: both post a check named
`Hushmark`.

Set-up happens once, by whoever runs the server. It takes about 20 minutes, in three parts:
create the App, deploy the server, then install the App.

## 1. Create the App on GitHub

Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App**
(https://github.com/settings/apps/new) and fill in:

| Field | Value |
|---|---|
| GitHub App name | `Hushmark` (if taken, `Hushmark Check`) |
| Homepage URL | `https://tryhushmark.vercel.app` |
| Webhook → Active | **Untick for now.** You will add the URL in part 3, once the server exists |
| Webhook secret | A long random string. Make one with `python3 -c "import secrets; print(secrets.token_hex(32))"` and keep it for part 2 |
| Repository permissions | **Checks: Read and write**, **Contents: Read-only**, **Pull requests: Read-only**, Metadata: Read-only (always on). Nothing else |
| Subscribe to events | **Pull request**, **Issue comment** |
| Where can this GitHub App be installed? | **Any account**, so other teams can install it in one click |

Click **Create GitHub App**, then on the App's page:

1. Note the **App ID** (a number near the top).
2. Under **Private keys**, click **Generate a private key**. A `.pem` file downloads. It is the
   App's password: never commit it, never paste it into chat.

Why these permissions: Contents to read the pinned diff and `.hushmark.yml` from the base
commit, Pull requests for the title, body and commits, Checks to post the `Hushmark` check,
and Metadata to check that a `/hushmark` commenter is an admin or maintainer. The App cannot
push code, comment or change settings.

## 2. Deploy the server (Render, free)

The repository includes `render.yaml`, a Render blueprint.

1. Sign in at https://render.com with GitHub and give Render access to this repository.
2. **New → Blueprint**, pick this repository. Render reads `render.yaml` and shows the
   service `hushmark-app`.
3. Fill in the secrets it asks for:

| Variable | Value |
|---|---|
| `HUSHMARK_APP_ID` | The App ID from part 1 |
| `HUSHMARK_APP_PRIVATE_KEY` | The whole content of the `.pem` file, including the `BEGIN` and `END` lines |
| `HUSHMARK_WEBHOOK_SECRET` | The webhook secret from part 1 |
| `NEARAI_API_KEY` | The NEAR AI Cloud key (the same one as the Action's secret) |
| `NEAR_ANCHOR_KEY` | The anchor key from `NEAR_ANCHOR_KEY.txt` (optional; without it, nothing is anchored) |

`NEAR_ANCHOR_ACCOUNT` (`anchor.hushmark.testnet`) and `HUSHMARK_DAILY_REVIEWS` (`20`) are
already set by the blueprint.

4. Click **Apply**. When the deploy finishes, open `https://<your-service>.onrender.com/healthz`.
   It should say `ok`.

**Keep it awake.** Render's free plan sleeps after 15 minutes without traffic, and GitHub
gives a webhook only 10 seconds to be answered. Add a free uptime monitor (for example
UptimeRobot) that opens `/healthz` every 5 minutes. If a delivery was missed anyway, open the
App's **Advanced → Recent Deliveries** and click **Redeliver**.

Other hosts work too: the `Dockerfile` builds the same server (`python -m hushmark.server`,
port 8000, set `PORT` to change it). CI builds the image and checks `/healthz` on every push.

## 3. Connect and install

1. Back on the App's settings page, tick **Webhook → Active** and set the **Webhook URL** to
   `https://<your-service>.onrender.com/webhook`. Save.
2. Install it: open `https://github.com/apps/<app-slug>/installations/new` (the slug is the
   App's name in lowercase with dashes, shown in its public page URL). Choose the account and
   the repositories. This link is the **one-click install** to share with other teams.
3. Test it on a repository that does **not** run the Hushmark Action:
   - Open a pull request that adds a Markdown file containing a hidden HTML comment telling
     AI agents to do something. A `Hushmark` check appears within a minute.
   - Comment `/hushmark` on the pull request as a maintainer: the check runs again. A comment
     from someone with only write access does nothing (`not_maintainer`).
4. Optional: add `.hushmark.yml` with `mode: block` to the default branch, and in branch
   protection require the `Hushmark` check with the App as its source.

## How it behaves

- Every delivery's `X-Hub-Signature-256` is checked before the body is read; anything else
  gets `401 webhook_invalid`.
- The server answers at once (`202 queued`) and reviews in a background worker, one at a
  time. A pull request already waiting is not queued twice, and a redelivered webhook is not
  reviewed twice.
- The receipt (hashes only) is shown in the check's details, so anyone can verify it
  (`RECEIPT.md`). The App keeps no database: the daily budget is counted in memory and starts
  again if the server restarts, and a re-run of the same commit is a new review whose anchor
  the contract refuses.
- Logs are one JSON line per event with the delivery ID, repository ID, PR number and receipt
  ID. Never code, never finding text.

## If something goes wrong

| Symptom | Check |
|---|---|
| No check appears | App → Advanced → Recent Deliveries: is the response `202`? A `401` means the webhook secret differs between GitHub and Render |
| Deliveries time out | The server was asleep: add the uptime monitor, then Redeliver |
| Check says `tee_unavailable` | `NEARAI_API_KEY` is missing or wrong on the server |
| No "Anchored on NEAR testnet" line | `NEAR_ANCHOR_KEY` is missing, or the check says why it was not recorded |
| Render logs show `review_failed` with `HTTPStatusError` | The private key or App ID is wrong, or the App was uninstalled from that repository |
