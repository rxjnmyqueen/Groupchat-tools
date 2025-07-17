# RXJN my queen — noleave + forcename
# Selfbot: Use at your own risk. Made for group chats only.
# github.com/rxjnmyqueen | rxjn.xyz 🔜
#
#  commands:    .noleave @user
#               .noleavestop @user
#               .noleavestopall
#               .forcename "name" (must use quotation marks)
#               .forcenamestop
#               .rpc (toggles the rpc)
#               .rpcset "title" ()
#               .quit
#
# see readme for more details

import discord
import json
import asyncio
import logging
import re
import requests
from discord.ext import commands

# === Load token ===
with open("config.json") as f:
    config = json.load(f)

TOKEN = config.get("token")

# === Setup ===
bot = commands.Bot(command_prefix=".", self_bot=True, help_command=None)
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")

# === Global state ===
noleave_map = {}       # {gc_id: set(user_ids)}
force_name_map = {}    # {gc_id: forced_name}
current_rpc = None     # RPC status

# === Utils ===
def is_group_chat(channel):
    return hasattr(channel, "recipients")

async def reply_and_delete(ctx, text, delay=3):
    try:
        msg = await ctx.send(text)
        await asyncio.sleep(delay)
        await msg.delete()
    except:
        pass

# === Monitor Loop ===
async def monitor_loop():
    while True:
        try:
            for gc_id in set(noleave_map.keys()).union(force_name_map.keys()):
                res = requests.get(
                    f"https://discord.com/api/v9/channels/{gc_id}",
                    headers={"Authorization": TOKEN}
                )

                if res.status_code != 200:
                    logging.warning(f"[GC {gc_id}] Failed to fetch: {res.status_code}")
                    continue

                data = res.json()
                current_users = {m["id"] for m in data.get("recipients", [])}
                current_name = data.get("name")

                # === Handle noleave ===
                for user_id in noleave_map.get(gc_id, set()):
                    if user_id not in current_users:
                        logging.info(f"[GC {gc_id}] Re-adding user {user_id}")
                        add = requests.put(
                            f"https://discord.com/api/v9/channels/{gc_id}/recipients/{user_id}",
                            headers={"Authorization": TOKEN}
                        )
                        if add.status_code == 204:
                            logging.info(f"✅ Re-added {user_id}")
                        else:
                            logging.warning(f"❌ Failed to re-add {user_id}: {add.status_code}")

                # === Handle forcename ===
                locked_name = force_name_map.get(gc_id)
                if locked_name and current_name != locked_name:
                    logging.info(f"[GC {gc_id}] GC name changed to '{current_name}', reverting to '{locked_name}'")
                    patch = requests.patch(
                        f"https://discord.com/api/v9/channels/{gc_id}",
                        headers={"Authorization": TOKEN, "Content-Type": "application/json"},
                        json={"name": locked_name}
                    )
                    if patch.status_code == 200:
                        logging.info(f"✅ Renamed GC {gc_id} back to '{locked_name}'")
                    else:
                        logging.warning(f"❌ Rename failed: {patch.status_code} — {patch.text}")

        except Exception as e:
            logging.error(f"[Monitor Loop Error] {e}")

        await asyncio.sleep(1)

# === On Ready ===
@bot.event
async def on_ready():
    logging.info(f"Welcome back {bot.user} my queen ({bot.user.id})")
    bot.loop.create_task(monitor_loop())


# === Help ===

@bot.command()
async def help(ctx):
    await ctx.message.delete()

    text = (
        "> # rxjn \n\n"
        "> **NoLeave**\n"
        "`.noleave @user` — Keep user in GC\n"
        "`.noleavestop @user` — Stop tracking user\n"
        "`.noleavestopall` — Stop all users\n\n"
        ">  **ForceName**\n"
        "`.forcename \"Name\"` — Lock GC name\n"
        "`.forcenamestop` — Stop name lock\n\n"
        ">  **RPC Status**\n"
        "`.rpcset \"Title\"` — streaming RPC\n"
        "`.rpc` — Clear RPC\n\n"
        ">  **Exit**\n"
        "`.quit` — Shutdown the bot\n"
    )

    msg = await ctx.send(text)
    await asyncio.sleep(10)
    await msg.delete()

# === NOLEAVE ===

@bot.command()
async def noleave(ctx, *args):
    await ctx.message.delete()
    if not is_group_chat(ctx.channel):
        return await reply_and_delete(ctx, "> Gc's only.")

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
        await reply_and_delete(ctx, f"> Protecting: {', '.join(added)}")
    else:
        await reply_and_delete(ctx, "> mention a user or their user ID")

@bot.command()
async def noleavestop(ctx, *args):
    await ctx.message.delete()
    gc_id = str(ctx.channel.id)
    if gc_id not in noleave_map:
        return await reply_and_delete(ctx, "> No users are being protected.")

    removed = []
    for arg in args:
        match = re.match(r"<@!?(\d+)>", arg)
        user_id = match.group(1) if match else (arg if arg.isdigit() else None)
        if user_id and user_id in noleave_map[gc_id]:
            noleave_map[gc_id].discard(user_id)
            removed.append(f"<@{user_id}>")

    if removed:
        await reply_and_delete(ctx, f"> Stopped protecting: {', '.join(removed)}")
    else:
        await reply_and_delete(ctx, "> not being protected")

@bot.command()
async def noleavestopall(ctx):
    await ctx.message.delete()
    gc_id = str(ctx.channel.id)
    if gc_id in noleave_map:
        noleave_map[gc_id].clear()
        await reply_and_delete(ctx, "> Stopped protecting all users.")
    else:
        await reply_and_delete(ctx, "> No users are being protected.")

# === FORCENAME ===

@bot.command()
async def forcename(ctx, *, arg):
    await ctx.message.delete()
    if not is_group_chat(ctx.channel):
        return await reply_and_delete(ctx, "> ❌ Group DMs only.")

    match = re.match(r'"(.*?)"', arg)
    if not match:
        return await reply_and_delete(ctx, '> Use quotes: `.forcename "Your Group Name"`')

    gc_id = str(ctx.channel.id)
    locked = match.group(1)
    force_name_map[gc_id] = locked

    await reply_and_delete(ctx, f'> GC name locked to: "{locked}"')
    logging.info(f"[GC {gc_id}] Name locked to '{locked}'")

@bot.command()
async def forcenamestop(ctx):
    await ctx.message.delete()
    gc_id = str(ctx.channel.id)
    if gc_id in force_name_map:
        del force_name_map[gc_id]
        await reply_and_delete(ctx, "> GC forcename disabled.")
    else:
        await reply_and_delete(ctx, "> GC name isn't locked.")

# === RPC ===

@bot.command()
async def rpcset(ctx, *, arg):
    await ctx.message.delete()
    match = re.match(r'"(.*?)"', arg)
    if not match:
        return await reply_and_delete(ctx, '❗ Use quotes: `.rpcset "Your stream title"`')

    title = match.group(1)
    global current_rpc
    current_rpc = discord.Streaming(
        name=title,
        url="https://twitch.tv/rxjnnnn"
    )
    await bot.change_presence(activity=current_rpc)
    await reply_and_delete(ctx, f"> Streaming status set: `{title}`")

@bot.command()
async def rpc(ctx):
    await ctx.message.delete()
    global current_rpc
    if current_rpc:
        current_rpc = None
        await bot.change_presence(activity=None)
        await reply_and_delete(ctx, "> RPC cleared.")
    else:
        await reply_and_delete(ctx, "> No RPC is currently active.")

# === QUIT ===

@bot.command()
async def quit(ctx):
    await ctx.message.delete()
    msg = await ctx.send("> bye rxjn 👋")
    await asyncio.sleep(3)
    await msg.delete()
    await bot.close()

# === Error Handling ===

@bot.event
async def on_command_error(ctx, error):
    logging.warning(f"[Command Error] {error}")
    try:
        await reply_and_delete(ctx, f"⚠️ Error: {str(error)}")
    except:
        pass

# === Start Bot ===

try:
    bot.run(TOKEN)
except Exception as e:
    logging.critical(f"❌ Bot failed to start: {e}")

