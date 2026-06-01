# RetailMind

An internal AI assistant for retail companies with two capabilities:
**Document Q&A** (retrieval-augmented generation over uploaded PDFs) and
**Analytics Q&A** (natural language → SQL over a Postgres retail database).
A router decides which capability handles each question.

See [`docs/01_project_overview.md`](docs/01_project_overview.md) for a full description and
[`docs/02_decisions_log.md`](docs/02_decisions_log.md) for the reasoning behind every architectural choice.

---

## Local development database

The dev database runs in Docker. A fresh container automatically applies the
schema migration and seeds ~5,000 sales rows on first boot.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose plugin)

### Start the database

```bash
# Copy the example env file (only needed once)
cp .env.example .env

# Start the Postgres container in the background
docker compose up -d
```

On first start Docker pulls `postgres:16`, creates the `retailmind` database,
and runs the scripts in `scripts/` in alphabetical order:
`001_schema.sql` (schema + roles) then `002_seed.sql` (reference data + ~5,000 sales rows).

This init step only runs on a **fresh volume**. If the volume already exists,
the container starts immediately without re-running the scripts.

> **Warning — editing migration or seed files:**
> If you change `001_schema.sql` or `002_seed.sql`, a plain `docker compose up`
> will **silently ignore your changes** because the data directory already exists.
> You must destroy the volume first:
> ```bash
> docker compose down -v   # deletes the volume — all data is lost
> docker compose up -d     # fresh boot; init scripts run again
> ```

### Connection details

| Setting  | Value                  |
|----------|------------------------|
| Host     | `localhost`            |
| Port     | `5432`                 |
| Database | `retailmind`           |
| User     | `postgres`             |
| Password | value of `POSTGRES_PASSWORD` in `.env` (default: `retailmind_dev`) |

Example `psql` connection:

```bash
psql postgresql://postgres:retailmind_dev@localhost:5432/retailmind
```

### Reset to a clean state (re-run seed)

The seed script starts with `TRUNCATE … RESTART IDENTITY CASCADE`, so it is
safe to re-run at any time. To get a completely fresh container:

```bash
# Stop the container and delete the named volume
docker compose down -v

# Start fresh — init scripts run again from scratch
docker compose up -d
```

---

## Folder layout

```
RetailMind/
├── backend/          # Python API server, agents, provider abstraction
├── frontend/         # Web UI (framework TBD)
├── data/
│   └── sample_docs/  # Sample PDFs for local development
├── docs/             # Architecture docs, decisions log, progress notes
├── scripts/          # SQL migrations run by Docker on first boot
│   ├── 001_schema.sql
│   └── 002_seed.sql
├── docker-compose.yml
└── .env.example
```
