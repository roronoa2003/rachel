import requests
import json
from config import APP_ID, TENANT_ID, APP_SECRET, TEAM_ID, CHANNEL_IDS, AGENT_EMAILS

_token_cache = {"token": None, "expires_at": 0}


def get_token() -> str:
    """Get or refresh Microsoft Graph API token."""
    import time
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["token"]
    url  = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "client_id":     APP_ID,
        "client_secret": APP_SECRET,
        "scope":         "https://graph.microsoft.com/.default",
        "grant_type":    "client_credentials",
    }
    resp = requests.post(url, data=data, timeout=15)
    resp.raise_for_status()
    result = resp.json()
    _token_cache["token"]      = result["access_token"]
    _token_cache["expires_at"] = time.time() + result.get("expires_in", 3600)
    return _token_cache["token"]


def post_to_channel(channel_name: str, message: str) -> bool:
    """Post a message to a Teams channel by name."""
    channel_id = CHANNEL_IDS.get(channel_name)
    if not channel_id or not TEAM_ID:
        print(f"[teams] missing TEAM_ID or channel_id for {channel_name}")
        return False
    token   = get_token()
    url     = f"https://graph.microsoft.com/v1.0/teams/{TEAM_ID}/channels/{channel_id}/messages"
    body    = {"body": {"contentType": "html", "content": message}}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }
    resp = requests.post(url, headers=headers, json=body, timeout=15)
    if resp.status_code in (200, 201):
        print(f"[teams] posted to #{channel_name}")
        return True
    else:
        print(f"[teams] post failed {resp.status_code}: {resp.text}")
        return False


def send_dm(from_agent: str, to_agent: str, message: str) -> bool:
    """
    Send a DM between two agent accounts via Microsoft Graph.
    Creates or reuses a 1:1 chat between the two agent emails.
    """
    from_email = AGENT_EMAILS.get(from_agent)
    to_email   = AGENT_EMAILS.get(to_agent)
    if not from_email or not to_email:
        print(f"[teams] DM failed — unknown agent: {from_agent} or {to_agent}")
        return False
    token   = get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }
    # Step 1: resolve user IDs
    def get_user_id(email):
        r = requests.get(
            f"https://graph.microsoft.com/v1.0/users/{email}",
            headers=headers, timeout=10
        )
        if r.status_code == 200:
            return r.json().get("id")
        return None

    from_id = get_user_id(from_email)
    to_id   = get_user_id(to_email)
    if not from_id or not to_id:
        print(f"[teams] DM failed — could not resolve user IDs")
        return False

    # Step 2: create or get existing 1:1 chat
    chat_payload = {
        "chatType": "oneOnOne",
        "members": [
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{from_id}')"
            },
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{to_id}')"
            }
        ]
    }
    chat_resp = requests.post(
        "https://graph.microsoft.com/v1.0/chats",
        headers=headers, json=chat_payload, timeout=15
    )
    if chat_resp.status_code not in (200, 201):
        print(f"[teams] DM chat create failed: {chat_resp.status_code} {chat_resp.text}")
        return False
    chat_id = chat_resp.json().get("id")

    # Step 3: post message to the chat
    msg_resp = requests.post(
        f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages",
        headers=headers,
        json={"body": {"contentType": "html", "content": message}},
        timeout=15
    )
    if msg_resp.status_code in (200, 201):
        print(f"[teams] DM sent {from_agent} → {to_agent}")
        return True
    else:
        print(f"[teams] DM send failed: {msg_resp.status_code} {msg_resp.text}")
        return False


def send_email(from_agent: str, to_email: str, subject: str,
               body_html: str, cc_email: str = None) -> bool:
    """Send email via Microsoft Graph API on behalf of an agent."""
    from_email = AGENT_EMAILS.get(from_agent)
    if not from_email:
        print(f"[teams] unknown from_agent for email: {from_agent}")
        return False
    token   = get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }
    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content":     body_html,
            },
            "toRecipients": [{"emailAddress": {"address": to_email}}],
        }
    }
    if cc_email:
        payload["message"]["ccRecipients"] = [
            {"emailAddress": {"address": cc_email}}
        ]
    resp = requests.post(
        f"https://graph.microsoft.com/v1.0/users/{from_email}/sendMail",
        headers=headers, json=payload, timeout=15
    )
    if resp.status_code == 202:
        print(f"[teams] email sent from {from_email} to {to_email}")
        return True
    else:
        print(f"[teams] email failed {resp.status_code}: {resp.text}")
        return False


def get_team_and_channel_ids() -> dict:
    """
    Utility: list all teams and their channels so you can populate env vars.
    Run this once via setup_teams.py.
    """
    token   = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    teams_resp = requests.get(
        "https://graph.microsoft.com/v1.0/me/joinedTeams",
        headers=headers, timeout=15
    )
    if teams_resp.status_code != 200:
        # try beta endpoint which works with app-only auth
        teams_resp = requests.get(
            "https://graph.microsoft.com/v1.0/groups?$filter=resourceProvisioningOptions/Any(x:x eq 'Team')",
            headers=headers, timeout=15
        )
    result = {}
    if teams_resp.status_code == 200:
        teams = teams_resp.json().get("value", [])
        for team in teams:
            tid   = team.get("id")
            tname = team.get("displayName", "")
            channels_resp = requests.get(
                f"https://graph.microsoft.com/v1.0/teams/{tid}/channels",
                headers=headers, timeout=15
            )
            if channels_resp.status_code == 200:
                channels = channels_resp.json().get("value", [])
                result[tname] = {
                    "team_id":  tid,
                    "channels": {c["displayName"]: c["id"] for c in channels}
                }
    return result
