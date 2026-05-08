import asyncio
import json
import os
from aiohttp import web
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity
from config import APP_ID, APP_SECRET, TENANT_ID
from orchestrator import route_message_async, route_dm_async
from scheduler import start_scheduler

# ─── Bot adapter — Single Tenant requires channel_auth_tenant ───────────────── 
settings = BotFrameworkAdapterSettings(APP_ID, APP_SECRET)
settings.channel_auth_tenant = TENANT_ID
adapter = BotFrameworkAdapter(settings)

async def on_error(context: TurnContext, error: Exception):
    print(f"[main] error: {error}")
    try:
        await context.send_activity("Something went wrong — the agents are on it.")
    except Exception as e:
        print(f"[main] error reply failed: {e}")

adapter.on_turn_error = on_error

# ─── Bot ────────────────────────────────────────────────────────────────────── 
class PractusBot:
    async def on_turn(self, turn_context: TurnContext):
        activity = turn_context.activity
        if activity.type == "message":
            await self._handle_message(turn_context)
        elif activity.type == "conversationUpdate":
            if activity.members_added:
                for member in activity.members_added:
                    if member.id != activity.recipient.id:
                        await turn_context.send_activity(
                            "👋 Practus AI Agents online — Michael, Simon, Victoria & Rachel ready.\n\n"
                            "Post in #agentassignments to assign work, or DM me directly."
                        )

    async def _handle_message(self, turn_context: TurnContext):
        activity = turn_context.activity
        message = (activity.text or "").strip()
        sender_name = activity.from_property.name if activity.from_property else "unknown"
        user_id = activity.from_property.id if activity.from_property else "unknown"

        # Strip @mention from message
        if activity.entities:
            for entity in activity.entities:
                if entity.type == "mention":
                    mention_text = entity.additional_properties.get("text", "")
                    message = message.replace(mention_text, "").strip()

        if not message:
            return

        conversation_type = (
            activity.conversation.conversation_type
            if activity.conversation else "channel"
        )

        if conversation_type == "personal":
            # DM — acknowledge immediately, process in background
            asyncio.create_task(
                self._process_dm(turn_context, user_id, sender_name, message)
            )
            await turn_context.send_activity("💬 Got it — one moment...")
        else:
            # Channel message — acknowledge immediately, process in background
            channel_name = _get_channel_name(activity)
            asyncio.create_task(
                self._process_channel(turn_context, channel_name, sender_name, message, user_id)
            )
            await turn_context.send_activity("✅ Received — routing to the right agent...")

    async def _process_channel(self, turn_context: TurnContext, channel_name: str,
                                sender_name: str, message: str, user_id: str):
        """Process channel message fully async — multiple can run in parallel."""
        try:
            response = await route_message_async(
                channel_name, sender_name, message, user_id, turn_context
            )
            await turn_context.send_activity(response)
        except Exception as e:
            print(f"[main] channel processing error: {e}")
            try:
                await turn_context.send_activity(
                    f"⚠️ Agent encountered an issue. Please try again."
                )
            except Exception:
                pass

    async def _process_dm(self, turn_context: TurnContext, user_id: str,
                           sender_name: str, message: str):
        """Process DM fully async."""
        try:
            response = await route_dm_async(user_id, sender_name, message)
            await turn_context.send_activity(response)
        except Exception as e:
            print(f"[main] DM processing error: {e}")
            try:
                await turn_context.send_activity("⚠️ Error — please try again.")
            except Exception:
                pass


def _get_channel_name(activity: Activity) -> str:
    from config import CHANNEL_IDS
    channel_id = ""
    if activity.channel_data:
        channel_info = activity.channel_data.get("channel", {})
        channel_id = channel_info.get("id", "")

    for name, cid in CHANNEL_IDS.items():
        if cid and channel_id == cid:
            return name

    # Fallback: match by channel name string
    if activity.channel_data:
        channel_name_raw = (
            activity.channel_data.get("channel", {})
            .get("name", "")
            .lower()
            .replace("-", "")
            .replace("_", "")
            .replace(" ", "")
            .replace("[", "")
            .replace("]", "")
        )
        name_map = {
            "agentassignmentsceoassignswork": "agentassignments",
            "agentassignments":               "agentassignments",
            "agentcollagentstalking":         "agentcollab",
            "agentcollab":                    "agentcollab",
            "agentlogs":                      "agentlogs",
            "agntkpidailyagentspostdailymetrics": "agntkpidaily",
            "agntkpidaily":                   "agntkpidaily",
            "ceodashboard":                   "ceodashboard",
            "agentalerts":                    "agentalerts",
        }
        for key, val in name_map.items():
            if key in channel_name_raw:
                return val

    return "agentcollab"


# ─── Web server ──────────────────────────────────────────────────────────────── 
bot = PractusBot()

async def messages(request: web.Request) -> web.Response:
    if request.content_type != "application/json":
        return web.Response(status=415)
    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")
    response = await adapter.process_activity(activity, auth_header, bot.on_turn)
    if response:
        return web.Response(
            status=response.status,
            body=json.dumps(response.body) if response.body else None,
            content_type="application/json",
        )
    return web.Response(status=200)

async def health(request: web.Request) -> web.Response:
    return web.Response(text="Practus Agents — online ✅", status=200)

def main():
    app = web.Application()
    app.router.add_post("/api/messages", messages)
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    start_scheduler()
    port = int(os.environ.get("PORT", 3978))
    print(f"[main] Practus Agents starting on port {port}")
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
