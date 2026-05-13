# Linking Overleaf to this repository

This repository ships the manuscript in two places that you can pick from
depending on your Overleaf plan and personal preference :

| Location | Branch | Content layout |
|---|---|---|
| `paper/` on `main` | `main` | `paper/manuscript.tex`, `paper/references.bib`, `paper/figures/` |
| Root of `overleaf-paper` branch | `overleaf-paper` | `manuscript.tex`, `references.bib`, `figures/` |

Overleaf expects the LaTeX files at the project root. **Always sync the
`overleaf-paper` branch, not `main`.**

The `overleaf-paper` branch is derived from `paper/` via `git subtree
split` ; it preserves the commit history of paper-only changes and is
auto-updated whenever `paper/` evolves on `main` (see the *Updating* section
below).

---

## Option 1 -- Overleaf Premium (GitHub auto-sync)

If you have Overleaf Premium or an institutional licence :

1. Open your Overleaf project.
2. **Menu → GitHub → Link to GitHub**.
3. Authorise Overleaf to read `rohanfosse/gbfs-audit-catalogue`.
4. In the branch picker, select **`overleaf-paper`** (not `main`).
5. Set **`manuscript.tex`** as the main document.

From now on, every push to `overleaf-paper` triggers an Overleaf re-sync,
and every Overleaf edit creates a commit on the branch.

---

## Option 2 -- Free plan (manual git remote)

If you are on Overleaf's free plan :

1. In Overleaf, **Menu → Sync → Git**.
2. Copy the project URL (it looks like
   `https://git.overleaf.com/<project-id>`).
3. From a terminal :

   ```bash
   # Clone the overleaf-paper branch into a local working folder
   git clone -b overleaf-paper \
       https://github.com/rohanfosse/gbfs-audit-catalogue.git overleaf-mirror
   cd overleaf-mirror

   # Add Overleaf as a second remote
   git remote add overleaf https://git.overleaf.com/<project-id>

   # Push the paper to Overleaf
   git push overleaf overleaf-paper:master
   ```

   When Overleaf prompts for a password, paste the Git Auth token from
   Overleaf's **Account Settings → Git authentication**.

4. To pull Overleaf-side edits back :

   ```bash
   git pull overleaf master
   git push origin overleaf-paper
   ```

---

## Updating the `overleaf-paper` branch from `main`

After any edit to `paper/` on `main`, refresh the side branch :

```bash
cd "$(git rev-parse --show-toplevel)"
git checkout main
git subtree split --prefix=paper -b overleaf-paper-new
git checkout overleaf-paper
git reset --hard overleaf-paper-new
git branch -D overleaf-paper-new
git push --force-with-lease origin overleaf-paper
```

The `--force-with-lease` flag is the safe variant of force-push : it
refuses to overwrite remote changes that Overleaf may have committed
since the last sync. If it fails, do a `git pull overleaf master` first.

A small helper script can be added at `paper/sync_overleaf.sh` if you
want to do this in one command.

---

## Why two branches instead of moving the manuscript to the repo root?

The repository has multiple deliverables : code, dataset, dashboard,
documentation. Promoting the manuscript to the root would crowd the
landing page and confuse non-paper consumers. The `overleaf-paper`
branch gives Overleaf the flat layout it expects without breaking the
main project structure.
