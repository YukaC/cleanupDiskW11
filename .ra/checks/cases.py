"""Seed/clean fixtures: one case per invariant rule.

Data only, kept apart from the runner so each file stays readable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Case:
    rule: str
    # files that make the fixture look like the target stack
    scaffold: dict[str, str]
    # the single seeded violation, as path -> content
    seed: dict[str, str]
    # files that must be absent for the rule to be silent again
    clean: dict[str, str]


COMMON_SCAFFOLD = {
    "package.json": '{\n  "name": "fixture",\n  "private": true,\n'
    '  "dependencies": { "express": "^4.19.0" }\n}\n',
}

# Same plus a UI: design/a11y/UI-state rules skip when no frontend stack is detected.
UI_SCAFFOLD = {
    "package.json": '{\n  "name": "fixture",\n  "private": true,\n'
    '  "dependencies": { "express": "^4.19.0", "react": "^18.3.1",'
    ' "react-dom": "^18.3.1" }\n}\n',
}

CASES: list[Case] = [
    Case(
        rule="module_state",
        scaffold={**COMMON_SCAFFOLD, "src/server.js": "export const app = 1;\n"},
        seed={
            "src/session-store.js": "const activeSessions = new Map();\nexport default activeSessions;\n"
        },
        clean={
            "src/session-store.js": "export function getSession() { return new Map(); }\n"
        },
    ),
    Case(
        rule="disk_writes",
        scaffold={**COMMON_SCAFFOLD, "src/server.js": "export const app = 1;\n"},
        seed={
            "src/report.js": "import { writeFileSync } from 'node:fs';\n"
            "export function save(p) { writeFileSync('/var/app/out.json', p); }\n"
        },
        clean={
            "src/report.js": "import { writeFileSync } from 'node:fs';\n"
            "export function save(p) { writeFileSync('/data/out.json', p); }\n"
        },
    ),
    Case(
        rule="env_config",
        scaffold={**COMMON_SCAFFOLD, "src/server.js": "export const app = 1;\n"},
        seed={"src/config.js": "export const pin = process.env.ADMIN_PIN || '1234';\n"},
        clean={"src/config.js": "export const pin = process.env.ADMIN_PIN;\n"},
    ),
    Case(
        rule="http_timeout",
        scaffold={**COMMON_SCAFFOLD, "src/server.js": "export const app = 1;\n"},
        seed={
            "src/client.js": "export async function call(u) {\n  const r = await fetch(u, { method: 'GET' });\n  return r.json();\n}\n"
        },
        clean={
            "src/client.js": "export async function call(u) {\n  const r = await fetch(u, { method: 'GET', signal: AbortSignal.timeout(5000) });\n  return r.json();\n}\n"
        },
    ),
    Case(
        # Browser assets are served, not executed in the request process: a fetch
        # without timeout in static/app.js must stay silent.
        rule="http_timeout",
        scaffold={
            **COMMON_SCAFFOLD,
            "src/server.js": "export const app = 1;\n",
            "static/app.js": "export async function call(u) {\n"
                             "  const r = await fetch(u, { method: 'GET' });\n"
                             "  return r.json();\n}\n",
        },
        seed={
            "src/server.js": "export async function call(u) {\n"
                             "  const r = await fetch(u, { method: 'GET' });\n"
                             "  return r.json();\n}\n"
        },
        clean={"src/server.js": "export const app = 1;\n"},
    ),
    Case(
        rule="query_limit",
        scaffold={**COMMON_SCAFFOLD, "src/server.js": "export const app = 1;\n"},
        seed={
            "src/db.js": "export const all = db.prepare('SELECT * FROM jobs').all();\n"
        },
        clean={
            "src/db.js": "export const all = db.prepare('SELECT * FROM jobs LIMIT ?').all(50);\n"
        },
    ),
    Case(
        rule="db_pool",
        scaffold={**COMMON_SCAFFOLD, "src/server.js": "export const app = 1;\n"},
        seed={
            "src/pool.js": "import { Pool } from 'pg';\nexport const pool = new Pool({ connectionString: url });\n"
        },
        clean={
            "src/pool.js": "import { Pool } from 'pg';\nexport const pool = new Pool({ connectionString: url, max: 10 });\n"
        },
    ),
    Case(
        rule="health_endpoint",
        scaffold={
            **COMMON_SCAFFOLD,
            "src/server.js": "import express from 'express';\n"
            "const app = express();\napp.listen(3000);\n",
        },
        seed={},
        clean={"src/health.js": "export const route = '/api/health';\n"},
    ),
    Case(
        rule="structured_logs",
        scaffold={**COMMON_SCAFFOLD, "src/server.js": "export const app = 1;\n"},
        seed={
            "src/handler.js": "export function handle() { console.log('handled'); return 1; }\n"
        },
        clean={
            "src/handler.js": "import { logger } from './logger.js';\n"
            "export function handle() { logger.info('handled'); return 1; }\n"
            "export const _l = logger;\n"
        },
    ),
    Case(
        rule="correlation_id",
        scaffold={**COMMON_SCAFFOLD, "src/server.js": "export const app = 1;\n"},
        seed={
            "src/handler.js": "export function h(req) {\n  logError({ event: 'a', message: 'x', code: 'E' });\n"
            "  logError({ event: 'b', message: 'y', code: 'F' });\n"
            "  logError({ event: 'c', message: 'z', code: 'G' });\n}\n"
            "export const logError = console.error;\n"
        },
        clean={
            "src/handler.js": "export function h(req) {\n"
            "  logError({ request_id: req.id, event: 'a', message: 'x' });\n"
            "  logError({ request_id: req.id, event: 'b', message: 'y' });\n"
            "  logError({ request_id: req.id, event: 'c', message: 'z' });\n}\n"
            "export const logError = console.error;\n"
        },
    ),
    Case(
        rule="hardcoded_secrets",
        scaffold={**COMMON_SCAFFOLD, "src/server.js": "export const app = 1;\n"},
        seed={
            "src/auth.js": "export const serviceApiKey = 'skLive7f3A9b2C1d4E5f6A7b8C9d0E1f2A3';\n"
        },
        clean={
            "src/auth.js": "export const serviceApiKey = process.env.SERVICE_API_KEY;\n"
        },
    ),
    Case(
        rule="static_cache",
        scaffold={
            **UI_SCAFFOLD,
            "next.config.js": "module.exports = { distDir: 'build', "
            "assetPrefix: '/assets/main.js' };\n",
        },
        seed={},
        clean={
            "next.config.js": "module.exports = { headers: async () => [{ source: '/assets/:path*',\n"
            "  headers: [{ key: 'Cache-Control', value: 'public, max-age=31536000, immutable' }] }] };\n"
        },
    ),
    Case(
        rule="no_orchestrator",
        scaffold={**COMMON_SCAFFOLD, "src/server.js": "export const app = 1;\n"},
        seed={
            "docker-compose.yml": "services:\n  a:\n    image: a\n  b:\n    image: b\n  c:\n    image: c\n  d:\n    image: d\n"
        },
        clean={
            "docker-compose.yml": "services:\n  a:\n    image: a\n  b:\n    image: b\n"
        },
    ),
    Case(
        rule="migration_reversible",
        scaffold={
            **COMMON_SCAFFOLD,
            "src/server.js": "export const app = 1;\n",
            "migrations/0001_init.sql": "CREATE TABLE t (id int);\n",
        },
        seed={"migrations/0002_drop.sql": "ALTER TABLE t DROP COLUMN legacy_flag;\n"},
        clean={
            "migrations/0002_drop.sql": "-- down: ALTER TABLE t ADD COLUMN legacy_flag boolean;\n"
            "ALTER TABLE t DROP COLUMN legacy_flag;\n"
        },
    ),
    Case(
        rule="artifact",
        scaffold={
            **COMMON_SCAFFOLD,
            "src/server.js": "import express from 'express';\n"
            "const app = express();\napp.listen(3000);\n",
        },
        seed={},
        clean={"Dockerfile": 'FROM node:22-slim\nCMD ["node", "src/server.js"]\n'},
    ),
    Case(
        rule="design_tokens",
        scaffold={
            **UI_SCAFFOLD,
            "src/app.jsx": "export const App = () => <div />;\n",
            "src/index.css": ":root {}\n",
        },
        seed={
            "src/Card.jsx": "export const Card = () => <div style={{ color: '#3a7bd5' }} />;\n"
        },
        clean={
            "src/Card.jsx": "export const Card = () => <div style={{ color: 'var(--color-primary)' }} />;\n"
        },
    ),
    Case(
        rule="a11y_basic",
        scaffold={
            **UI_SCAFFOLD,
            "src/app.jsx": "import React from 'react';\nexport const App = () => <div />;\n",
        },
        seed={
            "src/Avatar.jsx": 'export const Avatar = () => <img src="/a.png" width={40} />;\n'
        },
        clean={
            "src/Avatar.jsx": 'export const Avatar = () => <img src="/a.png" alt="perfil" />;\n'
        },
    ),
    Case(
        rule="ui_states",
        scaffold={
            **UI_SCAFFOLD,
            "src/app.jsx": "import React from 'react';\nimport { List } from './List.jsx';\n"
            "export const App = () => <List />;\n",
            "src/List.jsx": "import React from 'react';\nexport const List = () => <ul />;\n",
        },
        seed={
            "src/Data.jsx": "import React from 'react';\n"
            "export function Data() {\n  const rows = await fetch('/x');\n  return <div>{rows.length}</div>;\n}\n"
        },
        clean={
            "src/Data.jsx": "import React from 'react';\n"
            "export function Data() {\n  const rows = await fetch('/x');\n"
            "  const isLoading = false;\n  const isEmpty = rows.length === 0;\n"
            "  if (isLoading) return <div>loading</div>;\n  if (isEmpty) return <div>empty</div>;\n"
            "  return <div>{rows.length}</div>;\n}\n"
        },
    ),
]
