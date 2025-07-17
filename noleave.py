# RXJN GC NOLEAVE BOT | discord.py-self version
# Selfbot: Use at your own risk. Made for group chats only.
# github.com/rxjnmyqueen | rxjn.xyz 🔜
#
#  commands:    .noleave @user
#               .noleavestop @user
#               .noleavestopall
#
# see readme for more details

import discord
import json
import asyncio
import re
import logging
import requests

# === Load token ===
with open("config.json") as f:
    config = json.load(f)

TOKEN = config.get("token")

# === Discord Selfbot Client ===
from discord.ext import commands
bot = commands.Bot(command_prefix=".", self_bot=True)

# === User tracking per group chat ===
noleave_map = {}  # {group_chat_id: set(user_ids)}

# === Logging Setup ===
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")

# === Util: Check if channel is a GC ===
def is_group_chat(channel):
    return hasattr(channel, "recipients")

# === Background Task: Monitor group chats and re-add users ===
async def monitor_loop():
    while True:
        try:
            for gc_id, users in noleave_map.items():
                try:
                    res = requests.get(
                        f"https://discord.com/api/v9/channels/{gc_id}",
                        headers={"Authorization": TOKEN}
                    )
                    if res.status_code != 200:
                        logging.warning(f"[GC {gc_id}] Failed to fetch members ({res.status_code})")
                        continue

                    data = res.json()
                    current_ids = {user["id"] for user in data.get("recipients", [])}

                    for user_id in list(users):
                        if user_id not in current_ids:
                            logging.info(f"[GC {gc_id}] Re-adding {user_id} to group chat...")
                            add_res = requests.put(
                                f"https://discord.com/api/v9/channels/{gc_id}/recipients/{user_id}",
                                headers={"Authorization": TOKEN}
                            )
                            if add_res.status_code == 204:
                                logging.info(f"✅ Re-added user {user_id} to GC {gc_id}")
                            else:
                                logging.warning(f"❌ Failed to re-add {user_id} ({add_res.status_code})")

                except Exception as inner_e:
                    logging.error(f"[Loop Inner Error] {inner_e}")

        except Exception as e:
            logging.error(f"[Loop Error] {e}")

        await asyncio.sleep(1) # 1 second delay u can change it if u want to make it faster or slower to avoid rate limiting.

# === Bot Ready ===
@bot.event
async def on_ready():
    logging.info(f"✅ Logged in as {bot.user} ({bot.user.id})")
    bot.loop.create_task(monitor_loop())

# === .noleave command ===
@bot.command()
async def noleave(ctx, *args):
    if not is_group_chat(ctx.channel):
        return await ctx.send("> ❌ This command only works in group chats (GCs).")

    gc_id = str(ctx.channel.id)
    if gc_id not in noleave_map:
        noleave_map[gc_id] = set()

    added = []
    for arg in args:
        match = re.match(r"<@!?(\d+)>", arg)
        user_id = match.group(1) if match else (arg if arg.isdigit() else None)

        if user_id:
            noleave_map[gc_id].add(user_id)
            added.append(f"<@{user_id}>")

    if added:
        await ctx.send(f"> now protected by **rxjn** {', '.join(added)}")
        logging.info(f"[GC {gc_id}] Monitoring users: {noleave_map[gc_id]}")
    else:
        await ctx.send("> Please mention users or provide valid IDs.")

# === .noleavestop ===
@bot.command()
async def noleavestop(ctx, *args):
    gc_id = str(ctx.channel.id)
    if gc_id not in noleave_map:
        return await ctx.send("> No users are being monitored in this chat.")

    removed = []
    for arg in args:
        match = re.match(r"<@!?(\d+)>", arg)
        user_id = match.group(1) if match else (arg if arg.isdigit() else None)

        if user_id and user_id in noleave_map[gc_id]:
            noleave_map[gc_id].remove(user_id)
            removed.append(f"<@{user_id}>")

    if removed:
        await ctx.send(f"🔓 Stopped keeping {', '.join(removed)} in the group.")
    else:
        await ctx.send("> Could not match any users being protected.")

# === .noleavestopall ===
@bot.command()
async def noleavestopall(ctx):
    gc_id = str(ctx.channel.id)
    if gc_id in noleave_map:
        noleave_map[gc_id].clear()
        await ctx.send("🧹 Cleared noleave list for this group chat.")
        logging.info(f"[GC {gc_id}] Cleared all monitored users.")
    else:
        await ctx.send("not monitoring anyone.")

# === Error Handler ===
@bot.event
async def on_command_error(ctx, error):
    logging.warning(f"[Command Error] {error}")
    try:
        await ctx.send(f"⚠️ Error: {str(error)}")
    except:
        pass

# === Start bot ===
try:
    bot.run(TOKEN)
except Exception as e:
    logging.critical(f"❌ Failed to start bot: {e}")
