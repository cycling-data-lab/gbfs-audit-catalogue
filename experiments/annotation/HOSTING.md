# Hosting the annotation database (Supabase)

For a shared online campaign (Rohan + Gaël annotating via a URL), the
annotations must live in a hosted database — Streamlit Cloud's filesystem
is **ephemeral** and a local SQLite file would be wiped on every reboot.

The app auto-selects its backend (`storage.get_store()`):

- **No config** → local SQLite (`annotations.db`). Fine for solo/local use.
- **`ANNOTATION_DB_URL` set** (starts with `postgres`) → hosted PostgreSQL.

## 1. Create the Supabase database (~5 min)

1. Sign up at <https://supabase.com> (free tier) and create a **New project**.
   Pick a region close to you (e.g. `eu-west-3` Paris). Set a database
   password and **save it**.
2. Wait ~2 min for provisioning.
3. Go to **Project Settings → Database → Connection string → URI**.
4. Select the **Transaction pooler** (host contains `pooler.supabase.com`,
   port `6543`) — best for short serverless connections.
5. Copy the URI and replace `[YOUR-PASSWORD]` with your DB password. Append
   `?sslmode=require` if it is not already there. Example:

   ```
   postgresql://postgres.abcdefgh:MyPassw0rd@aws-0-eu-west-3.pooler.supabase.com:6543/postgres?sslmode=require
   ```

The `annotations` table is created automatically on first launch.

## 2. Configure locally (optional, for testing)

Copy the template and paste your URI:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit .streamlit/secrets.toml -> set ANNOTATION_DB_URL
```

`.streamlit/secrets.toml` is git-ignored. Run `streamlit run
experiments/annotation/annotator_app.py` — the sidebar should connect
without error.

## 3. Deploy on Streamlit Cloud

1. Push the repo (already done) and create an app at
   <https://share.streamlit.io> pointing to
   `experiments/annotation/annotator_app.py`.
2. In the app's **Settings → Secrets**, paste the single line:

   ```toml
   ANNOTATION_DB_URL = "postgresql://postgres.abcdefgh:MyPassw0rd@aws-0-eu-west-3.pooler.supabase.com:6543/postgres?sslmode=require"
   ```

3. Save → the app reboots and writes go to Supabase. Share the URL with
   Gaël; both of you pick your name in the dropdown and annotate.

## 4. View / export the results

- **Supabase dashboard**: Table Editor → `annotations` to browse/filter;
  use the SQL Editor or the table's export button for CSV.
- **In-app**: the sidebar "Export legacy" button writes the Q1–Q5 CSV that
  `compute_reliability.py` consumes. Run it once per annotator, then:

  ```bash
  python -m experiments.annotation.compute_reliability \
      --labels1 labels_rohan.csv --labels2 labels_gael.csv \
      --output reliability_report.json
  ```

## Notes

- The free tier **pauses** a project after ~1 week of inactivity; just
  reopen the Supabase dashboard to resume.
- Both annotators write their own rows (keyed by annotator + station), so
  concurrent use is safe — no row contention.
- To switch back to local SQLite, simply remove `ANNOTATION_DB_URL`.
- Alternatives with the same interface: Neon, Railway, or any PostgreSQL
  DSN. Turso (hosted SQLite) or Google Sheets would need a small backend
  addition in `storage.py`.
