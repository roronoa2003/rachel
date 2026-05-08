"""
orchestrator.py — Production grade

Features:
- Smart routing: bot decides which agent based on message content
- Agent-to-agent DMs for private coordination
- Parallel async processing — multiple employees handled simultaneously
- Relevance detection — agents decide if they need to collaborate
- Full inter-agent approval loops
"""
import asyncio
import time
import concurrent.futures

from config import (
    AGENT_DISPLAY_NAMES,
    NEEDS_APPROVAL_KEYWORDS,
    NEEDS_INFO_KEYWORDS,
    ALERT_KEYWORDS,
    MAX_AGENT_HOPS
)
from managed_agent import call_managed_agent, call_managed_agent_with_history
from memory import load_thread, save_thread, create_task, update_task_status
from teams import post_to_channel, send_dm

# Thread pool for parallel agent calls
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)


# ─── Signal parsing ──────────────────────────────────────────────────────────── 
def parse_signals(response_text: str) -> dict:
    text_lower = response_text.lower()
    signals = {
        "needs_approval": False,
        "needs_info":     False,
        "is_alert":       False,
        "target_agent":   None,
        "needs_dm":       False,
    }
    for kw in NEEDS_APPROVAL_KEYWORDS:
        if kw.lower() in text_lower:
            signals["needs_approval"] = True
            idx   = text_lower.find(kw.lower())
            after = response_text[idx + len(kw):idx + len(kw) + 40].strip().lower()
            for agent in ["michael", "victoria", "simon", "rachel"]:
                if agent in after:
                    signals["target_agent"] = agent
                    break
    for kw in NEEDS_INFO_KEYWORDS:
        if kw.lower() in text_lower:
            signals["needs_info"]   = True
            signals["target_agent"] = "michael"
            break
    for kw in ALERT_KEYWORDS:
        if kw in response_text:
            signals["is_alert"] = True
            break
    # Detect if agents should DM privately (sensitive/confidential content)
    dm_keywords = [
        "confidential", "private", "sensitive", "between us", "don't share",
        "internal only", "off the record", "personal matter", "salary",
        "performance issue", "termination", "pip", "conflict"
    ]
    if any(k in text_lower for k in dm_keywords):
        signals["needs_dm"] = True
    return signals


# ─── Smart agent routing ──────────────────────────────────────────────────────── 
def _determine_agent(channel_name: str, message_text: str) -> str:
    text = message_text.lower()
    # Explicit agent mentions take priority
    if "@simon"   in text or "simon,"   in text or "simon "   in text: return "simon"
    if "@rachel"  in text or "rachel,"  in text or "rachel "  in text: return "rachel"
    if "@victoria" in text or "victoria," in text or "victoria " in text: return "victoria"
    if "@michael" in text or "@michel"  in text or "michael," in text: return "michael"
    # Channel-based routing
    if channel_name == "ceodashboard": return "michael"
    if channel_name == "agentalerts":  return "victoria"
    # Smart keyword routing for agentassignments and agentcollab
    simon_keywords = [
        "hire","hiring","recruit","recruitment","candidate","candidates","naukri","talent",
        "consultant","onboard","onboarding","hr","people","headcount","vacancy","job",
        "interview","offer letter","salary band","compensation","chro","chief people",
        "resource","sourcing","background check","reference check","performance review"
    ]
    rachel_keywords = [
        "brand","branding","linkedin","marketing","content","design","post","campaign",
        "logo","visual","social media","creative","blog","article","case study",
        "whitepaper","employer brand","website","copy","graphics","cbo","chief brand",
        "announcement","press release","newsletter","thought leadership","spotlight"
    ]
    victoria_keywords = [
        "schedule","calendar","meeting","brief","okr","commit","status","update",
        "summary","dashboard","track","follow up","deadline","cos","chief of staff",
        "approval","sign off","weekly","monthly","report","institutional","memory","log"
    ]
    if any(k in text for k in simon_keywords):    return "simon"
    if any(k in text for k in rachel_keywords):   return "rachel"
    if any(k in text for k in victoria_keywords): return "victoria"
    # Default to Michael for strategic decisions
    return "michael"


# ─── Main async route — called per message, runs in parallel ────────────────── 
async def route_message_async(channel_name: str, sender_name: str,
                               message_text: str, user_id: str,
                               turn_context=None) -> str:
    loop       = asyncio.get_event_loop()
    agent_name = _determine_agent(channel_name, message_text)
    # Log to agentlogs in background (don't wait)
    asyncio.create_task(_log_async(channel_name, sender_name, agent_name, message_text))
    context = (
        f"Message received in Microsoft Teams #{channel_name}. "
        f"Sender: {sender_name}. "
        f"Respond according to your role and responsibilities."
    )
    # Call agent in thread pool (non-blocking)
    response = await loop.run_in_executor(
        _executor, call_managed_agent, agent_name, message_text, context
    )
    # Parse signals
    signals = parse_signals(response)
    # Format response
    display_name = AGENT_DISPLAY_NAMES.get(agent_name, agent_name)
    formatted    = f"**{display_name}**\n\n{response}"
    # Handle inter-agent coordination in background
    if signals["needs_approval"] and signals["target_agent"]:
        asyncio.create_task(
            _handle_approval_async(
                requesting_agent  = agent_name,
                approving_agent   = signals["target_agent"],
                original_message  = message_text,
                requesting_response = response,
                channel_name      = channel_name,
                sender_name       = sender_name,
                use_dm            = signals["needs_dm"],
                hop               = 1,
            )
        )
    # Post alert in background
    if signals["is_alert"]:
        asyncio.create_task(_post_alert_async(display_name, response))
    # Fan out if Michael assigned tasks
    if channel_name == "agentassignments" and agent_name == "michael":
        asyncio.create_task(_fan_out_async(response, message_text, sender_name))
    return formatted


def route_message(channel_name: str, sender_name: str,
                  message_text: str, user_id: str) -> None:
    """Sync wrapper for backward compatibility with scheduler."""
    agent_name   = _determine_agent(channel_name, message_text)
    display_name = AGENT_DISPLAY_NAMES.get(agent_name, agent_name)
    context  = (
        f"Message in #{channel_name} from {sender_name}. "
        f"Respond according to your role."
    )
    response = call_managed_agent(agent_name, message_text, context)
    signals  = parse_signals(response)
    post_to_channel(channel_name, f"<b>{display_name}</b><br><br>{response}")
    if signals["needs_approval"] and signals["target_agent"]:
        _handle_approval_sync(
            requesting_agent    = agent_name,
            approving_agent     = signals["target_agent"],
            original_message    = message_text,
            requesting_response = response,
            channel_name        = channel_name,
            use_dm              = signals["needs_dm"],
            hop                 = 1,
        )
    if signals["is_alert"]:
        post_to_channel("agentalerts", f"<b>🔴 ALERT from {display_name}</b><br><br>{response[:500]}")


# ─── DM routing ──────────────────────────────────────────────────────────────── 
async def route_dm_async(from_user_id: str, from_user_name: str, message_text: str) -> str:
    loop       = asyncio.get_event_loop()
    agent_name = _determine_agent("dm", message_text)
    context_id = f"dm_{from_user_id}"
    history    = load_thread(agent_name, context_id)
    history.append({"role": "user", "content": message_text})
    context = (
        f"Personal direct message from {from_user_name} in Microsoft Teams. "
        f"Respond directly and personally."
    )
    response = await loop.run_in_executor(
        _executor, call_managed_agent_with_history, agent_name, history, context
    )
    history.append({"role": "assistant", "content": response})
    save_thread(agent_name, context_id, history)
    display_name = AGENT_DISPLAY_NAMES.get(agent_name, agent_name)
    return f"**{display_name}**\n\n{response}"


def route_dm(from_user_id: str, from_user_name: str, to_agent: str, message_text: str) -> str:
    """Sync DM routing for backward compat."""
    context_id = f"dm_{from_user_id}"
    history    = load_thread(to_agent, context_id)
    history.append({"role": "user", "content": message_text})
    context    = f"Personal DM from {from_user_name}."
    response   = call_managed_agent_with_history(to_agent, history, context)
    history.append({"role": "assistant", "content": response})
    save_thread(to_agent, context_id, history)
    return response


# ─── Inter-agent approval — async ───────────────────────────────────────────── 
async def _handle_approval_async(requesting_agent: str, approving_agent: str,
                                  original_message: str, requesting_response: str,
                                  channel_name: str, sender_name: str,
                                  use_dm: bool, hop: int) -> None:
    if hop > MAX_AGENT_HOPS:
        await _post_channel_async("agentalerts",
            f"<b>⚠️ LOOP LIMIT</b> — {requesting_agent} → {approving_agent}. "
            f"Human intervention needed.")
        return
    loop            = asyncio.get_event_loop()
    req_display     = AGENT_DISPLAY_NAMES.get(requesting_agent, requesting_agent)
    approver_display = AGENT_DISPLAY_NAMES.get(approving_agent, approving_agent)
    request_msg = (
        f"<b>{req_display} → {approver_display}</b><br><br>"
        f"<b>Request:</b> {requesting_response[:600]}<br><br>"
        f"<b>Original task:</b> {original_message[:300]}"
    )
    if use_dm:
        await loop.run_in_executor(_executor, send_dm, requesting_agent, approving_agent, request_msg)
        await _post_channel_async("agentcollab",
            f"<b>{req_display}</b> has sent a private message to "
            f"<b>{approver_display}</b> regarding: {original_message[:100]}...")
    else:
        await _post_channel_async("agentcollab", request_msg)
        await loop.run_in_executor(_executor, send_dm, requesting_agent, approving_agent, request_msg)
    approval_context = (
        f"You have received a request from {requesting_agent.title()} "
        f"that needs your input. Original task: {original_message[:300]}"
    )
    approval_response = await loop.run_in_executor(
        _executor, call_managed_agent, approving_agent, requesting_response, approval_context
    )
    if use_dm:
        await loop.run_in_executor(_executor, send_dm, approving_agent, requesting_agent, approval_response)
    else:
        await _post_channel_async("agentcollab",
            f"<b>{approver_display} → {req_display}</b><br><br>{approval_response}")
        await loop.run_in_executor(_executor, send_dm, approving_agent, requesting_agent, approval_response)
    followup_context = f"{approving_agent.title()} responded: {approval_response[:500]}"
    final_response   = await loop.run_in_executor(
        _executor, call_managed_agent, requesting_agent,
        "Continue with the task based on the response you received.", followup_context
    )
    await _post_channel_async(channel_name,
        f"<b>{req_display}</b> (after {approver_display} response)<br><br>{final_response}")
    further = parse_signals(final_response)
    if further["needs_approval"] and further["target_agent"]:
        await _handle_approval_async(
            requesting_agent    = requesting_agent,
            approving_agent     = further["target_agent"],
            original_message    = original_message,
            requesting_response = final_response,
            channel_name        = channel_name,
            sender_name         = sender_name,
            use_dm              = further["needs_dm"],
            hop                 = hop + 1,
        )


def _handle_approval_sync(requesting_agent: str, approving_agent: str,
                           original_message: str, requesting_response: str,
                           channel_name: str, use_dm: bool, hop: int) -> None:
    if hop > MAX_AGENT_HOPS:
        return
    req_display      = AGENT_DISPLAY_NAMES.get(requesting_agent, requesting_agent)
    approver_display = AGENT_DISPLAY_NAMES.get(approving_agent, approving_agent)
    request_msg = (
        f"<b>{req_display} → {approver_display}</b><br><br>"
        f"{requesting_response[:600]}"
    )
    if use_dm:
        send_dm(requesting_agent, approving_agent, request_msg)
    else:
        post_to_channel("agentcollab", request_msg)
        send_dm(requesting_agent, approving_agent, request_msg)
    approval_context  = f"Request from {requesting_agent}: {requesting_response[:400]}"
    approval_response = call_managed_agent(approving_agent, requesting_response, approval_context)
    if use_dm:
        send_dm(approving_agent, requesting_agent, approval_response)
    else:
        post_to_channel("agentcollab", f"<b>{approver_display}</b><br><br>{approval_response}")
    followup = call_managed_agent(
        requesting_agent,
        "Continue based on the approval you received.",
        f"{approving_agent} responded: {approval_response[:400]}"
    )
    post_to_channel(channel_name, f"<b>{req_display}</b><br><br>{followup}")


# ─── Fan out task to multiple agents ────────────────────────────────────────── 
async def _fan_out_async(michael_response: str, original_task: str, sender_name: str) -> None:
    text   = michael_response.lower()
    agents = []
    if "simon"    in text: agents.append("simon")
    if "rachel"   in text: agents.append("rachel")
    if "victoria" in text: agents.append("victoria")
    if not agents:
        return
    task_id = f"task_{int(time.time())}"
    create_task(
        task_id         = task_id,
        owner           = "michael",
        description     = original_task[:500],
        assigned_agents = agents,
        channel         = "agentassignments",
    )
    loop = asyncio.get_event_loop()
    async def call_one(agent):
        context = (
            f"Michael (CEO) assigned you a task as part of {task_id}. "
            f"Michael's instructions: {michael_response[:600]}"
        )
        response = await loop.run_in_executor(
            _executor, call_managed_agent, agent, original_task, context
        )
        display  = AGENT_DISPLAY_NAMES.get(agent, agent)
        await _post_channel_async("agentassignments",
            f"<b>{display}</b> (task {task_id})<br><br>{response}")
        signals = parse_signals(response)
        if signals["needs_approval"] and signals["target_agent"]:
            await _handle_approval_async(
                requesting_agent    = agent,
                approving_agent     = signals["target_agent"],
                original_message    = original_task,
                requesting_response = response,
                channel_name        = "agentassignments",
                sender_name         = sender_name,
                use_dm              = signals["needs_dm"],
                hop                 = 1,
            )
        if signals["is_alert"]:
            display = AGENT_DISPLAY_NAMES.get(agent, agent)
            await _post_channel_async("agentalerts",
                f"<b>🔴 {display}</b><br><br>{response[:400]}")
    await asyncio.gather(*[call_one(agent) for agent in agents])
    update_task_status(task_id, "completed")


# ─── Async helpers ───────────────────────────────────────────────────────────── 
async def _post_channel_async(channel: str, message: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_executor, post_to_channel, channel, message)

async def _log_async(channel: str, sender: str, agent: str, message: str) -> None:
    loop = asyncio.get_event_loop()
    log  = (
        f"<b>[LOG]</b> #{channel} | From: {sender} | "
        f"Routed to: {agent} | {message[:150]}"
    )
    await loop.run_in_executor(_executor, post_to_channel, "agentlogs", log)

async def _post_alert_async(display_name: str, response: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        _executor, post_to_channel, "agentalerts",
        f"<b>🔴 ALERT from {display_name}</b><br><br>{response[:500]}"
    )
