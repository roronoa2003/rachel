"""
managed_agent.py

Calls Console agents via Anthropic Managed Agents REST API.
Falls back to raw Messages API if Managed Agents fails.
"""
import anthropic
import time
import requests
from config import (
    ANTHROPIC_API_KEY,
    AGENT_IDS,
    ENVIRONMENT_IDS,
    VAULT_IDS,
)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

FALLBACK_PROMPTS = {
    "michael": "You are Michael, CEO of Practus — an AI-native consulting firm. You assign tasks to agents (Simon=CHRO, Victoria=CoS, Rachel=Branding), make final decisions, orchestrate operations. Be decisive and commercially sharp. Sign off as Michel | CEO, Practus.",
    "victoria": "You are Victoria, Chief of Staff to Michael at Practus. You synthesize agent updates into CEO briefs (3 greens, 3 ambers, 3 reds), track commitments, maintain institutional memory. Be calm and precise. Sign off as Victoria | Chief of Staff, Practus.",
    "simon":    "You are Simon, CHRO at Practus. You source candidates from Naukri (primary), apply 6-criteria scorecard (Domain, Experience, References, Culture, Availability, Cost — 4.0+=HIRE), manage onboarding and knowledge capture. Be pragmatic and data-driven. Sign off as Simon | CHRO, Practus.",
    "rachel":   "You are Rachel, Chief Brand Officer at Practus. You create LinkedIn content (3-4x/week), design brand assets using Teal #228899 and Gold #FDB81A, write case studies and thought leadership. Be creative and on-brand. Sign off as Rachel | Chief Brand Officer, Practus.",
}

MODEL_MAP = {
    "michael":  "claude-sonnet-4-6",
    "victoria": "claude-sonnet-4-6",
    "simon":    "claude-sonnet-4-6",
    "rachel":   "claude-sonnet-4-6",
}

MANAGED_AGENTS_HEADERS = {
    "x-api-key":          ANTHROPIC_API_KEY,
    "anthropic-version":  "2023-06-01",
    "anthropic-beta":     "managed-agents-2026-04-01",
    "Content-Type":       "application/json",
}


def call_managed_agent(agent_name: str, message: str, extra_context: str = "") -> str:
    full_message = f"{extra_context}\n\n{message}" if extra_context else message
    result = _try_managed_agents(agent_name, full_message)
    if result:
        return result
    print(f"[managed_agent] falling back to raw API for {agent_name}")
    return _call_raw_api(agent_name, full_message)


def _try_managed_agents(agent_name: str, message: str) -> str:
    agent_id       = AGENT_IDS.get(agent_name)
    environment_id = ENVIRONMENT_IDS.get(agent_name)
    vault_ids      = VAULT_IDS.get(agent_name, [])

    if not agent_id or not environment_id:
        return ""

    session_id = None
    try:
        payload = {"agent": agent_id, "environment_id": environment_id}
        if vault_ids:
            payload["vault_ids"] = vault_ids

        r = requests.post(
            "https://api.anthropic.com/v1/sessions",
            headers=MANAGED_AGENTS_HEADERS,
            json=payload,
            timeout=30,
        )
        if r.status_code not in (200, 201):
            print(f"[managed_agent] session create failed {r.status_code}: {r.text[:200]}")
            return ""
        session_id = r.json().get("id")
        if not session_id:
            return ""

        print(f"[managed_agent] session created for {agent_name}: {session_id}")

        r2 = requests.post(
            f"https://api.anthropic.com/v1/sessions/{session_id}/messages",
            headers=MANAGED_AGENTS_HEADERS,
            json={"role": "user", "content": message},
            timeout=30,
        )
        if r2.status_code not in (200, 201):
            print(f"[managed_agent] message send failed {r2.status_code}: {r2.text[:200]}")
            return ""

        response_text = ""
        for _ in range(60):
            time.sleep(3)
            r3 = requests.get(
                f"https://api.anthropic.com/v1/sessions/{session_id}/events",
                headers=MANAGED_AGENTS_HEADERS,
                timeout=15,
            )
            if r3.status_code != 200:
                continue
            for event in r3.json().get("events", []):
                etype = event.get("type", "")
                if etype == "agent.text_delta":
                    response_text += event.get("delta", "")
                elif etype == "agent.message_stop":
                    print(f"[managed_agent] {agent_name} done via Managed Agents")
                    return response_text

        return response_text if response_text else ""

    except Exception as e:
        print(f"[managed_agent] REST error for {agent_name}: {e}")
        return ""
    finally:
        if session_id:
            try:
                requests.post(
                    f"https://api.anthropic.com/v1/sessions/{session_id}/terminate",
                    headers=MANAGED_AGENTS_HEADERS,
                    timeout=10,
                )
            except Exception:
                pass


def _call_raw_api(agent_name: str, message: str, history: list = None) -> str:
    system = FALLBACK_PROMPTS.get(agent_name, "You are a helpful assistant.")
    model  = MODEL_MAP.get(agent_name, "claude-sonnet-4-6")
    msgs   = history if history else [{"role": "user", "content": message}]
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system,
            messages=msgs,
        )
        return resp.content[0].text
    except Exception as e:
        print(f"[managed_agent] raw API error for {agent_name}: {e}")
        return f"[{agent_name}] Error — please try again."


def call_managed_agent_with_history(agent_name: str, messages: list, extra_context: str = "") -> str:
    if not messages:
        return f"[error] no messages for {agent_name}"
    history = list(messages)
    if extra_context and history:
        last = history[-1]
        history[-1] = {"role": last["role"], "content": f"{extra_context}\n\n{last['content']}"}
    return _call_raw_api(agent_name, "", history=history)
