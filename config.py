import os

# ─── Azure Bot / Microsoft Graph ─────────────────────────────────────────── 
APP_ID     = os.environ.get("APP_ID",     "90c67c89-acf9-4a37-aeb9-b4f05e873f43")
TENANT_ID  = os.environ.get("TENANT_ID",  "46b14d0b-783c-458a-8080-2e53081940e6")
APP_SECRET = os.environ.get("APP_SECRET", "")

# ─── Anthropic ───────────────────────────────────────────────────────────── 
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ─── Managed Agent IDs (from console.anthropic.com) ──────────────────────── 
AGENT_IDS = {
    "michael":  "agent_011CaY3U6od6MrfSshVCRvgY",
    "victoria": "agent_011CaW77RFGLq9wc1WfGyRsm",
    "simon":    "agent_011CaVyewydr8EvWrhH488KN",
    "rachel":   "agent_011CaXbwz16nhqaEjeJoRbdq",
}

# ─── Environment IDs (one per agent) ─────────────────────────────────────── 
ENVIRONMENT_IDS = {
    "michael":  "env_01HsHwJEDTmJc6imXe2fHTfa",
    "victoria": "env_019Fc85Tpyv33jJtXuKQoGR3",
    "simon":    "env_01Eos4skkK4D6NtxGnDjhbqq",
    "rachel":   "env_01WNYqvZX7ubUxyf2hMJdCNi",
}

# ─── Vault IDs (credentials: Naukri, Graph API, SharePoint etc.) ─────────── 
VAULT_IDS = {
    "michael":  ["vlt_011CafxjVjszEXPX9hoXRzkF"],
    "victoria": ["vlt_011CaXmQZK6GbHWHc532ahhW"],
    "simon":    ["vlt_011CafxjVjszEXPX9hoXRzkF"],
    "rachel":   ["vlt_011CaWAYNLw1fiHYNyuqytuB"],
}

# ─── Agent display names ──────────────────────────────────────────────────── 
AGENT_DISPLAY_NAMES = {
    "michael":  "Michael | CEO, Practus",
    "victoria": "Victoria | Chief of Staff, Practus",
    "simon":    "Simon | CHRO, Practus",
    "rachel":   "Rachel | Chief Brand Officer, Practus",
}

# ─── Agent email identities ──────────────────────────────────────────────── 
AGENT_EMAILS = {
    "michael":  "michael@roibypractus.com",
    "victoria": "victoria@roibypractus.com",
    "simon":    "simon@roibypractus.com",
    "rachel":   "rachel@roibypractus.com",
}

# ─── Teams channel IDs ───────────────────────────────────────────────────── 
TEAM_ID = os.environ.get("TEAM_ID", "e06c06b9-6fd8-4b38-85ba-35e97c6620f0")
CHANNEL_IDS = {
    "agentassignments": os.environ.get("CHANNEL_AGENTASSIGNMENTS", "19:20e4b4f8d82a445aa8966a3e8193f04f@thread.tacv2"),
    "agentcollab":      os.environ.get("CHANNEL_AGENTCOLLAB",      "19:1f08cf3e5d5c4ff6bb6940638aa8fb1d@thread.tacv2"),
    "agentlogs":        os.environ.get("CHANNEL_AGENTLOGS",        "19:4d494419a94a41a0acfd7db5e3e471d6@thread.tacv2"),
    "agntkpidaily":     os.environ.get("CHANNEL_AGNTKPIDAILY",     "19:380877b41bb84d4aa06230570c832bad@thread.tacv2"),
    "ceodashboard":     os.environ.get("CHANNEL_CEODASHBOARD",     "19:8edbfbe164714cf79bc76902ebbb7719@thread.tacv2"),
    "agentalerts":      os.environ.get("CHANNEL_AGENTALERTS",      "19:99b4ffdd66f74e0ea2dd1effd6ec5f1c@thread.tacv2"),
}

# ─── Signal keywords ─────────────────────────────────────────────────────── 
NEEDS_APPROVAL_KEYWORDS = [
    "NEEDS_APPROVAL:",
    "requesting approval",
    "need catherine's approval",
    "need victoria's approval",
    "awaiting approval",
    "pending approval",
]
NEEDS_INFO_KEYWORDS = [
    "NEEDS_INFO:",
    "waiting for michael",
    "need michael's decision",
    "need ceo decision",
]
ALERT_KEYWORDS = ["🔴", "BLOCKED", "AT RISK", "URGENT", "ESCALATE", "RED FLAG"]

# ─── Scheduler times (UTC — IST is UTC+5:30) ────────────────────────────── 
KPI_POST_TIME_UTC       = "03:30"   # 9:00 AM IST
DASHBOARD_TIME_UTC      = "14:30"   # 8:00 PM IST
WEEKLY_SUMMARY_TIME_UTC = "12:00"   # 5:30 PM IST Friday
COMMITLOG_CHECK_UTC     = "04:30"   # 10:00 AM IST Thursday

# ─── Safety ──────────────────────────────────────────────────────────────── 
MAX_AGENT_HOPS  = 3
SESSION_TIMEOUT = 300   # seconds — close idle sessions after 5 minutes
