# gbfs-toolkit : manques relevés en construisant la pipeline unifiée

Constats issus de l'écriture de `unified_audit.py` + `run_unified_audit.py`.
Priorité : P1 = correction/correctness, P2 = ergonomie scientifique, P3 = confort.

## P1.1 — Bug du résolveur de catalogue (correctness)

`io/catalog.py::resolve` choisit la colonne URL ainsi :

```python
url_col = next((c for c in catalog.columns
                if ("auto" in c and "discovery" in c) or c == "url"), None)
```

Comme l'OU accepte `c == "url"` et que la colonne `url` (site web de l'opérateur)
précède souvent `auto-discovery_url` dans la liste MobilityData, **le résolveur
fetch la page d'accueil au lieu du `gbfs.json`**. Symptôme observé :
`fetch https://www.careem.com/...: 404` au lieu du flux GBFS.

**Correctif :** prioriser l'auto-discovery, puis se rabattre sur `url`.

```python
disc = next((c for c in catalog.columns if "auto" in c and "discovery" in c), None)
url_col = disc or next((c for c in catalog.columns if c == "url"), None)
```

## P1.2 — Fonction manquante : audit de catalogue par lot

La librairie offre `audit_feed(url)` (un flux) et `fetch_multiple(ids)` (fetch
seul), mais **rien qui fetch N systèmes et renvoie un verdict station-level tidy
+ un statut par système**. Tout `unified_audit.py` (fetch → `station_information()`
→ concat → `audit_static` → agrégation système, avec gestion des flux morts) est
la preuve de ce manque. C'est l'API de haut niveau dont a besoin tout audit
multi-système (exactement le cœur du papier).

**API proposée :**

```python
def audit_catalogue(system_ids=None, *, catalog=None, archive_dir=None,
                    a7_scope="docked", a4_sigma=3.0, max_workers=8):
    """Fetch and audit many systems. Returns (verdict_stations, status_per_system).
    If archive_dir is given, freeze raw station_information + provenance there."""
```

## P2.1 — Archivage reproductible fetch -> disque avec provenance

`generate_manifest(lake_dir)` hashe un lake **existant**, mais il manque le
one-shot « fetch un flux et écris ses frames canoniques avec `fetched_at`, URL
source et hash par frame ». C'est la boucle BYOD reproductible (fetch une fois,
geler, auditer de façon déterministe) que j'ai dû coder à la main dans
`run_unified_audit.py::fetch_and_archive`.

**API proposée :** `feed.snapshot(to=dir)` qui écrit `{system_id}/information.parquet`
+ une ligne de provenance, ou `gb.archive_systems(ids, catalog, to=dir)`.

## P2.2 — Agrégation des flags au niveau système

Réduire les flags A1-A7 station-level en par-système (système flaggé ssi ≥1
station flaggée) est l'opération que fait tout le papier, recodée ici en
`unified_audit.system_flags`. Mérite un helper :

```python
def system_flags(verdict):  # -> DataFrame indexé par system_id, colonnes A1..A7 + n_stations
```

ou un paramètre `level="system"` sur `audit_static`/`audit_frames`.

## P3.1 — Comptage « exclusif » inter-classes

Le papier reporte « systèmes flaggés A7 **et par aucune autre classe** ». Un petit
utilitaire `exclusive_flags(verdict)` (ou `only=("A7",)`) éviterait de le recoder.

## P3.2 — Jointure pays/type automatique

Quand un `catalog` est fourni, attacher `country_code` (et le type inféré) au
verdict éviterait la jointure manuelle systématique.

## P3.3 — Ergonomie : `station_information` est une méthode

`feed.station_information()` se lit comme un attribut (`info = feed.station_information`
renvoie la fonction, puis `.columns` lève une erreur opaque). Cohérent avec
`summary()`/`snapshot()`/`audit()`, donc à garder, mais à signaler dans la doc
quickstart (piège classique).

---

**Recommandation :** P1.1 (bug résolveur) et P1.2 (`audit_catalogue`) sont les
deux à intégrer en priorité ; ils transforment ce script de recherche en API
première classe et corrigent un fetch silencieusement faux.
