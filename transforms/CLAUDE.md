# Transformations Directory Guide

## Structure

```
transformations/
├── _shared/              # Shared macros, audits, seeds across all projects
│   ├── macros/
│   ├── audits/
│   └── seeds/
├── ebird/                # eBird-specific sqlmesh project
│   ├── config.yaml
│   ├── models/
│   │   ├── staging/      # stg_ebird_* models — clean raw data
│   │   ├── intermediate/ # int_ebird_* models — business logic
│   │   └── marts/        # fct_ebird_* / dim_ebird_* models — analytics
│   └── tests/
├── home_team/            # Cross-domain analytics (joins across sources)
│   ├── config.yaml
│   └── models/
└── away_team/            # Alternative/scratch project
```

## Per-Source Projects

Each registered pipeline can have its own sqlmesh project under `transformations/<source>/`.

- **Config**: Each project has its own `config.yaml` pointing to `../../data/databox.db`
- **Schemas**: Read from `raw_<source>.*` (populated by dlt), write to `<source>.*`
- **Naming**: `<source>.stg_<source>_<entity>`, `<source>.int_<source>_<entity>`, etc.

## home_team/

Reserved for **cross-domain** models that join across sources. Not for single-source transforms.

## Commands

```bash
# Via CLI (recommended)
databox transform plan <project>
databox transform run <project>
databox transform test <project>

# Via sqlmesh directly
cd transformations/<project>
sqlmesh plan
sqlmesh run
sqlmesh test
```

If no project is specified, the CLI auto-discovers all projects with a `config.yaml`.
