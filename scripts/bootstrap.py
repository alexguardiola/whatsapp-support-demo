#!/usr/bin/env python3
"""Create the demo account, agent, team, website inbox and agent bot through Chatwoot's APIs.

Secrets go to .env (mode 600) and are never printed. Re-running is a no-op once bootstrapped.
"""
import json
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from envfile import read_env, update_env  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BOT_URL = "http://bot:8000/webhook/{secret}"
DEMO_ORIGIN = "http://localhost:8088"


def api(base: str, method: str, path: str, token_header: tuple[str, str] | None = None, body: dict | None = None) -> dict:
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token_header:
        req.add_header(*token_header)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} failed: HTTP {e.code} {e.read()[:300]!r}")
    return json.loads(raw) if raw else {}


def wait_for(base: str, timeout: int = 240) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base + "/api", timeout=5) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(3)
    sys.exit(f"Chatwoot did not answer at {base} within {timeout}s (run `make up` first).")


def platform_token() -> str:
    """A Platform App token cannot be created over HTTP, so it is minted once with rails runner."""
    ruby = 'app = PlatformApp.find_or_create_by!(name: "demo-bootstrap"); puts "PLATFORM_TOKEN=#{app.access_token.token}"'
    out = subprocess.run(
        ["docker", "compose", "exec", "-T", "chatwoot-rails", "bundle", "exec", "rails", "runner", ruby],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    for line in out.stdout.splitlines():
        if line.startswith("PLATFORM_TOKEN="):
            return line.split("=", 1)[1].strip()
    sys.exit(f"Could not create the platform app (exit {out.returncode}). See `docker compose logs chatwoot-rails`.")


def finish_onboarding() -> None:
    """Accounts made over the Platform API leave Chatwoot's first-run flag set, so every dashboard URL would
    redirect to the sign-up form and invite a second account. Clearing it sends people to the login page."""
    ruby = '::Redis::Alfred.delete(::Redis::Alfred::CHATWOOT_INSTALLATION_ONBOARDING); puts "ONBOARDING_DONE"'
    out = subprocess.run(
        ["docker", "compose", "exec", "-T", "chatwoot-rails", "bundle", "exec", "rails", "runner", ruby],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if "ONBOARDING_DONE" not in out.stdout:
        sys.exit(f"Could not finish Chatwoot's first-run setup (exit {out.returncode}). See `docker compose logs chatwoot-rails`.")


def main() -> None:
    env = read_env()
    if env.get("CHATWOOT_ACCOUNT_ID"):
        print("Already bootstrapped (CHATWOOT_ACCOUNT_ID is set in .env). Run `make clean` to start over.")
        return
    base = env.get("CHATWOOT_URL", "http://localhost:3010").rstrip("/")
    print(f"Waiting for Chatwoot at {base} ...")
    wait_for(base)

    ptoken = platform_token()
    platform = ("api_access_token", ptoken)
    account = api(base, "POST", "/platform/api/v1/accounts", platform, {"name": "Fisioterapia Ondaviva (demo)", "locale": "es"})
    acc = account["id"]
    user = api(
        base, "POST", "/platform/api/v1/users", platform,
        {"name": env["ADMIN_NAME"], "email": env["ADMIN_EMAIL"], "password": env["ADMIN_PASSWORD"]},
    )
    api(base, "POST", f"/platform/api/v1/accounts/{acc}/account_users", platform, {"user_id": user["id"], "role": "administrator"})
    utoken = api(base, "POST", f"/platform/api/v1/users/{user['id']}/token", platform)["access_token"]
    app_api = ("api_access_token", utoken)
    print(f"Account {acc} and administrator created.")

    team = api(base, "POST", f"/api/v1/accounts/{acc}/teams", app_api,
               {"name": "recepcion", "description": "Personas que atienden las conversaciones que el bot deriva"})
    api(base, "POST", f"/api/v1/accounts/{acc}/teams/{team['id']}/team_members", app_api, {"user_ids": [user["id"]]})

    inbox = api(
        base, "POST", f"/api/v1/accounts/{acc}/inboxes", app_api,
        {
            "name": "Web Ondaviva",
            "channel": {
                "type": "web_widget",
                "website_url": DEMO_ORIGIN,
                "widget_color": "#FF5B1F",
                "welcome_title": "Hola, somos Ondaviva",
                "welcome_tagline": "Te respondemos al momento. Si hace falta, te atiende una persona del equipo.",
            },
        },
    )
    api(base, "POST", f"/api/v1/accounts/{acc}/inbox_members", app_api, {"inbox_id": inbox["id"], "user_ids": [user["id"]]})

    hook_secret = env.get("BOT_WEBHOOK_SECRET") or secrets.token_hex(24)
    bot = api(
        base, "POST", f"/api/v1/accounts/{acc}/agent_bots", app_api,
        {"name": "Asistente Ondaviva", "description": "Responde con fuentes; deriva a persona si duda",
         "outgoing_url": BOT_URL.format(secret=hook_secret)},
    )
    api(base, "POST", f"/api/v1/accounts/{acc}/inboxes/{inbox['id']}/set_agent_bot", app_api, {"agent_bot": bot["id"]})
    if not bot.get("access_token"):
        sys.exit("Chatwoot did not return the agent bot token; check that the user is an administrator.")
    print(f"Website inbox {inbox['id']}, team {team['id']} and agent bot {bot['id']} created and connected.")

    update_env({
        "BOT_WEBHOOK_SECRET": hook_secret,
        "CHATWOOT_ACCOUNT_ID": str(acc),
        "CHATWOOT_INBOX_ID": str(inbox["id"]),
        "CHATWOOT_WEBSITE_TOKEN": inbox["website_token"],
        "CHATWOOT_PLATFORM_TOKEN": ptoken,
        "CHATWOOT_USER_TOKEN": utoken,
        "BOT_CHATWOOT_BOT_TOKEN": bot["access_token"],
        "BOT_WEBHOOK_HMAC_SECRET": bot.get("secret") or "",
        "BOT_CHATWOOT_TEAM_ID": str(team["id"]),
    })
    (ROOT / "demo" / "config.js").write_text(
        "window.ONDAVIVA_CHAT = " + json.dumps({"baseUrl": base, "websiteToken": inbox["website_token"]}) + ";\n",
        encoding="utf-8",
    )
    finish_onboarding()
    print("Saved credentials to .env and widget settings to demo/config.js.")
    print(f"Log in at {base} with ADMIN_EMAIL / ADMIN_PASSWORD from .env. Demo page: {DEMO_ORIGIN}")


if __name__ == "__main__":
    main()
