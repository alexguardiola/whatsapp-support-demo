# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-29

### Added

- Chatwoot Community v4.19.1 stack in one `compose.yaml`: PostgreSQL with pgvector, Redis, Rails, Sidekiq, the bot, `llm-relay` and an nginx demo page. Images are pinned by tag and digest, published ports are bound to `127.0.0.1`, and Chatwoot Rails, the relay and the demo page have healthchecks.
- Python agent bot (FastAPI) that answers from the Markdown files in `knowledge/`, retrieved with BM25, through any OpenAI-compatible endpoint with structured output. The default is a local Ollama with `qwen3:14b`.
- Guardrails that hand the conversation to a person: keyword pre-check for complaints, refunds and requests for a person; hand-off intents; required citations; citation ids checked against the retrieved sections; prices only from the price sheet; a confidence floor; a daily cap on model calls and tokens.
- Hand-off flow: a message to the customer that accounts for business hours, a private note with the reason, the team assignment and status `open`.
- Webhook path secret and HMAC signature check on Chatwoot's agent-bot webhook.
- `make up`, `make bootstrap`, `make e2e`, `make fake`, `make test` and `make clean`. `make bootstrap` sets up the account, inbox, team and agent bot through Chatwoot's APIs.
- 74 unit tests that need neither Docker nor a model, and recorded model outputs for `--fake-llm`.
- Synthetic knowledge base for the fictitious clinic Fisioterapia Ondaviva.

[Unreleased]: https://github.com/SaskullOps/whatsapp-support-demo/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/SaskullOps/whatsapp-support-demo/releases/tag/v0.1.0
