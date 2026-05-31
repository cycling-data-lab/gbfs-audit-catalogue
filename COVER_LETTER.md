# Cover Letter — Computer Standards & Interfaces

**Date:** [submission date]

**To:** Editor-in-Chief
*Computer Standards & Interfaces*
Elsevier

**Re:** Submission of manuscript *"Auditing GBFS bike-sharing feeds at country and global scale: A reproducible anomaly taxonomy for open mobility data"*

---

Dear Editor-in-Chief,

We are pleased to submit our manuscript for consideration as a research article in *Computer Standards & Interfaces*. The work reports a country- and global-scale audit of the General Bikeshare Feed Specification (GBFS) — a regulatory open-data standard maintained by the Open Mobility Foundation and mandated for French operators under the 2019 Mobility Orientation Law — applied to the 1,509-system MobilityData canonical catalogue across 48 countries.

The contribution is fourfold and directly aligned with the scope of *CS&I*. First, we derive a seven-class data-quality taxonomy (five structural errors, two semantic warnings) from an empirical audit and formalise each class as a reproducible detection rule. Second, we operationalise the taxonomy as a nine-step idempotent purging protocol whose design properties (idempotence, reversibility, step-level logging, explicit parameterisation, FAIR release) are mapped explicitly onto the ISO/IEC 25012:2008 data-quality dimensions and the companion ISO/IEC 25024:2015 measurement standard — to our knowledge the first reference implementation of these standards on an open mobility specification. Third, we release the *GBFS Audit Catalogue* (46,307 stations, 46 typed columns) under ODbL on Zenodo with concept DOI 10.5281/zenodo.20125460, together with a JSON Schema, a DCAT-AP record, a Frictionless Data Package descriptor and a Croissant manifest — the four machine-readable interoperability artefacts the data-engineering community now expects of a FAIR release. Fourth, we pre-register a retrospective hold-out validation on twelve months of MobilityData additions that the rule set passes on point estimate and confidence interval, and provide a Docker image for bit-exact reproduction.

We selected *Computer Standards & Interfaces* because the contribution sits squarely at the intersection of three of the journal's traditional concerns: the empirical audit of a published interoperability specification, the formal interface between a regulatory data feed and downstream research consumers, and the alignment of a domain artefact with ISO/IEC quality standards. The closest methodological precedents — the canonical GTFS validator literature, the data-quality dimensions of Wang and Strong, and the property-based-testing tradition imported from software engineering — are all part of the *CS&I* readership's intellectual heritage, and we believe the audience is the right one to assess and build on this work.

The manuscript reports original work and is not under consideration at any other venue. A preprint version is **not** currently deposited; we will deposit on Zenodo / HAL only after the journal's preprint policy has been verified at the desk-acceptance stage. All authors have approved the submission and have no competing financial or personal interests to declare. Generative AI tools (GitHub Copilot, Claude) were used for code completion and editorial language polishing only; their use is declared explicitly in the manuscript and the authors take full responsibility for the content.

Suggested reviewer profiles (the editor is invited to select or substitute):

- A researcher active on GTFS or GBFS validation tooling (e.g., contributors to the Canonical GTFS Schedule Validator at MobilityData, or the OMF GBFS technical committee).
- A specialist in open-mobility-data quality and reproducibility (e.g., active contributors to the *transport.data.gouv.fr* national portal, the French ADEME open-mobility working group, or the European EuroMobility coordination).
- A data-engineering researcher working on declarative validation frameworks (Great Expectations, Pandera, Frictionless Data) and their application to regulatory open-data feeds.
- A bike-sharing / micromobility researcher with quantitative experience of demand modelling or supply-side composite indices on European corpora.

We have no specific reviewers to exclude, but kindly ask the editor to avoid reviewers from CESI LINEACT to preserve independence.

Thank you for considering our work. We look forward to the editorial assessment and remain available for any clarification.

With kind regards,

**Rohan Fossé** (corresponding author)
CESI Engineering School, Montpellier, France
[rfosse@cesi.fr](mailto:rfosse@cesi.fr)
ORCID: [0009-0002-2195-0198](https://orcid.org/0009-0002-2195-0198)

**Gaël Pallares**
CESI LINEACT (EA 7527), Montpellier, France
ORCID: [0009-0002-8680-604X](https://orcid.org/0009-0002-8680-604X)
