# Security policy

## Scope

This is a demo. The business, its documents and its prices are invented, and the stack is meant to run on your own machine. It is not hardened for production as shipped.

What the defaults do:

- Only two ports are published, both on `127.0.0.1`: Chatwoot on 3010 and the demo page on 8088. PostgreSQL, Redis and the bot have no published port.
- `llm-relay` uses host networking so it can reach a model server on the host's loopback. It listens only on a Unix socket inside a Docker volume and opens no TCP port.
- `make up` runs `scripts/gen-env.sh`, which writes `.env` with random values from Python's `secrets` module and mode 600. `make bootstrap` adds the Chatwoot API tokens to the same file. `.env` is gitignored, the scripts never print its values, and `make clean` deletes it. The same secrets also reach the containers as environment variables, and Chatwoot stores the agent bot's webhook URL (with its path secret) and HMAC secret in its database.
- The bot's webhook URL has a random path secret, and the bot checks Chatwoot's `X-Chatwoot-Signature` HMAC with a 5-minute window and drops repeated delivery ids and signatures. It writes no HTTP access log, so the path secret is not logged.
- The bot and `llm-relay` run with a read-only root filesystem, all Linux capabilities dropped and `no-new-privileges`.

Settings that are only acceptable for a local demo:

- Chatwoot runs over plain HTTP with `FORCE_SSL=false`.
- `SAFE_FETCH_ALLOW_PRIVATE_NETWORK=true` lets Chatwoot call the bot on the Docker network. In production, leave it unset and give the bot an HTTPS URL.

## Supported versions

Only the latest release gets fixes.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: open the repository's **Security** tab and choose **Report a vulnerability**, or go to <https://github.com/SaskullOps/whatsapp-support-demo/security/advisories/new>. Please do not open a public issue for a security problem.

Include the commit or release, the steps to reproduce, and what an attacker could do with it.

Vulnerabilities in Chatwoot, PostgreSQL, Redis or nginx belong upstream with those projects.
