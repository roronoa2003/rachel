import schedule
import time
import threading
from datetime import datetime

from managed_agent import call_managed_agent
from teams import post_to_channel
from config import AGENT_DISPLAY_NAMES


def _post_daily_kpis():
    today = datetime.now().strftime("%B %d, %Y")
    print(f"[scheduler] daily KPIs — {today}")
    for agent in ["simon", "rachel", "victoria", "michael"]:
        prompt = (
            f"Today is {today}. Post your daily KPI update to #agntkpidaily. "
            f"Use your standard KPI format with all current metrics."
        )
        try:
            response     = call_managed_agent(agent, prompt)
            display_name = AGENT_DISPLAY_NAMES.get(agent, agent)
            post_to_channel("agntkpidaily", f"<b>{display_name}</b><br><br>{response}")
            time.sleep(5)
        except Exception as e:
            print(f"[scheduler] KPI failed for {agent}: {e}")


def _post_ceo_dashboard():
    today = datetime.now().strftime("%B %d, %Y")
    print(f"[scheduler] CEO dashboard — {today}")
    prompt = (
        f"Today is {today}. Compile and post the daily CEO brief to #ceodashboard. "
        f"Format: 3 greens (on track), 3 ambers (needs attention), 3 reds (needs Michael's decision). "
        f"Signal only — no noise. Include owners and deadlines for action items."
    )
    try:
        response = call_managed_agent("victoria", prompt)
        display  = AGENT_DISPLAY_NAMES.get("victoria", "victoria")
        post_to_channel("ceodashboard", f"<b>{display}</b><br><br>{response}")
    except Exception as e:
        print(f"[scheduler] CEO dashboard failed: {e}")


def _post_weekly_summaries():
    today = datetime.now().strftime("%B %d, %Y")
    print(f"[scheduler] weekly summaries — {today}")
    for agent in ["simon", "rachel", "victoria"]:
        prompt = (
            f"Today is Friday {today}. Post your weekly summary to #ceodashboard. "
            f"Use your standard weekly summary format with all KPIs, wins, risks, next week priorities."
        )
        try:
            response     = call_managed_agent(agent, prompt)
            display_name = AGENT_DISPLAY_NAMES.get(agent, agent)
            post_to_channel("ceodashboard", f"<b>{display_name} — WEEKLY SUMMARY</b><br><br>{response}")
            time.sleep(5)
        except Exception as e:
            print(f"[scheduler] weekly summary failed for {agent}: {e}")


def _check_commit_log():
    print("[scheduler] Victoria checking commit log")
    prompt = (
        "Today is Thursday. Check CommitLog for commitments due tomorrow (Friday) or overdue. "
        "Follow up with relevant agents or flag to Michael if anything is at risk. "
        "Post your follow-up summary to #agentcollab."
    )
    try:
        response = call_managed_agent("victoria", prompt)
        display  = AGENT_DISPLAY_NAMES.get("victoria", "victoria")
        post_to_channel("agentcollab", f"<b>{display} — Thursday Follow-up</b><br><br>{response}")
    except Exception as e:
        print(f"[scheduler] commit log check failed: {e}")


def start_scheduler():
    # Daily KPIs — 9:00 AM IST = 3:30 AM UTC
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        getattr(schedule.every(), day).at("03:30").do(_post_daily_kpis)

    # CEO Dashboard — 8:00 PM IST = 2:30 PM UTC
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        getattr(schedule.every(), day).at("14:30").do(_post_ceo_dashboard)

    # Weekly summaries — Friday 5:30 PM IST = 12:00 PM UTC
    schedule.every().friday.at("12:00").do(_post_weekly_summaries)

    # Thursday commit log — 10:00 AM IST = 4:30 AM UTC
    schedule.every().thursday.at("04:30").do(_check_commit_log)

    print("[scheduler] all jobs scheduled")

    def run():
        while True:
            schedule.run_pending()
            time.sleep(30)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    print("[scheduler] background thread started")
