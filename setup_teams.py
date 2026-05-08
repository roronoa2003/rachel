"""
Run this ONCE after deploying to Railway to get your Team ID and Channel IDs.
Then add them as environment variables in Railway.

Usage:
    python setup_teams.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from teams import get_team_and_channel_ids
import json

def main():
    print("Fetching Teams info from Microsoft Graph...\n")
    data = get_team_and_channel_ids()

    if not data:
        print("No teams found. Make sure your credentials are correct.")
        return

    for team_name, info in data.items():
        print(f"Team: {team_name}")
        print(f"  TEAM_ID = {info['team_id']}")
        print(f"  Channels:")
        for ch_name, ch_id in info["channels"].items():
            env_key = f"CHANNEL_{ch_name.upper().replace('-','').replace(' ','')}"
            print(f"    {env_key} = {ch_id} ({ch_name})")
        print()

    print("─" * 60)
    print("Add these to Railway as environment variables:")
    print("─" * 60)
    for team_name, info in data.items():
        if "practus" in team_name.lower() or "agent" in team_name.lower():
            print(f"TEAM_ID={info['team_id']}")
            for ch_name, ch_id in info["channels"].items():
                clean = ch_name.upper().replace("-","").replace(" ","").replace("#","")
                print(f"CHANNEL_{clean}={ch_id}")

if __name__ == "__main__":
    main()
