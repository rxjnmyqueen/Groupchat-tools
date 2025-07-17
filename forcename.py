# RXJN GC FORCENAME BOT | discord.py-self version
# Selfbot use only — do not use with a bot token.
# github.com/rxjnmyqueen | rxjn.xyz 🔜
#
#  commands:    .forcename
#               .forcenamestop
#
# see readme for more details


import discord
import json
import asyncio
import logging
import requests
import re
from discord.ext import commands

# === Load token ===
with open("config.json") as f:
    config = json.load(f)

TOKEN = config.get("token")

# === Setup ===
bot = commands.Bot(command_prefix=".", self_bot=True)
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")

# === Force name storage ===
force_name_map = {}  # {group_chat_id: locked_name}

# === Check if it's a GC ===
def is_group_chat(channel):
    return hasattr(channel, "recipients")

# === Force rename loop ===
async def force_name_loop():
    while True:
        try:
            for gc_id, forced_name in force_name_map.items():
                try:
                    res = requests.get(
                        f"https://discord.com/api/v9/channels/{gc_id}",
                        headers={"Authorization": TOKEN}
                    )
                    if res.status_code != 200:
                        logging.warning(f"[GC {gc_id}] Failed to fetch name: {res.status_code}")
                        continue

                    current = res.json()
                    current_name = current.get("name")

                    if current_name != forced_name:
                        logging.info(f"[GC {gc_id}] Name changed to '{current_name}', reverting to '{forced_name}'")
                        patch = requests.patch(
                            f"https://discord.com/api/v9/channels/{gc_id}",
                            headers={
                                "Authorization": TOKEN,
                                "Content-Type": "application/json"
                            },
                            json={"name": forced_name}
                        )
                        if patch.status_code == 200:
                            logging.info(f"✅ Renamed GC {gc_id} back to '{forced_name}'")
                        else:
                            logging.warning(f"❌ Failed to rename GC {gc_id}: {patch.status_code} — {patch.text}")

                except Exception as e:
                    logging.error(f"[Loop inner error] {e}")

        except Exception as e:
            logging.error(f"[Loop outer error] {e}")

        await asyncio.sleep(3) # change it to 1 to make it superfast

# === Ready ===
@bot.event
async def on_ready():
    logging.info(f"✅ Logged in as {bot.user} ({bot.user.id})")
    bot.loop.create_task(force_name_loop())

# === .forcename "Your Name Here" ===
@bot.command()
async def forcename(ctx, *, arg):
    if not is_group_chat(ctx.channel):
        return await ctx.send("❌ This only works in group DMs.")

    match = re.match(r'"(.*?)"', arg)
    if not match:
        return await ctx.send('❗ Use quotes: `.forcename "Your Name Here"`')

    name_to_lock = match.group(1)
    gc_id = str(ctx.channel.id)
    force_name_map[gc_id] = name_to_lock

    await ctx.send(f'🔒 GC name locked to: "{name_to_lock}"')
    logging.info(f"[GC {gc_id}] Name locked to: {name_to_lock}")

# === .forcenamestop ===
@bot.command()
async def forcenamestop(ctx):
    gc_id = str(ctx.channel.id)
    if gc_id in force_name_map:
        del force_name_map[gc_id]
        await ctx.send("🛑 GC name lock disabled.")
        logging.info(f"[GC {gc_id}] Name lock removed.")
    else:
        await ctx.send("⚠️ No name is currently being enforced.")

# === Error handler ===
@bot.event
async def on_command_error(ctx, error):
    logging.warning(f"[Command Error] {error}")
    try:
        await ctx.send(f"⚠️ Error: {str(error)}")
    except:
        pass

# === Run Bot ===
try:
    bot.run(TOKEN)
except Exception as e:
    logging.critical(f"❌ Failed to start bot: {e}")
