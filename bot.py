import discord
from discord.ext import commands
import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask
import threading

# === Configuration du bot ===
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# === Fichier local et variables GitHub ===
DATA_FILE = Path(__file__).parent / "data.json"
GIST_ID = os.getenv("GIST_ID")
GITHUB_GIST_TOKEN = os.getenv("GITHUB_GIST_TOKEN")

# === Données en mémoire ===
user_data = {}

# === Flask pour garder le bot en ligne ===
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot Discord actif et en ligne."

def run_flask():
    app.run(host='0.0.0.0', port=8080)

threading.Thread(target=run_flask).start()

# === Chargement et sauvegarde des données ===
def load_data():
    """Charge les données depuis GitHub Gist ou le fichier local."""
    global user_data
    if not GIST_ID or not GITHUB_GIST_TOKEN:
        print("⚠️ Variables d'environnement GIST_ID ou GITHUB_GIST_TOKEN manquantes.")
        if DATA_FILE.exists():
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                user_data = json.load(f)
            print("📂 Données chargées depuis le fichier local.")
        return

    try:
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GITHUB_GIST_TOKEN}"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        gist_data = response.json()
        content = list(gist_data["files"].values())[0]["content"]
        user_data = json.loads(content)
        print("✅ Données chargées depuis le Gist GitHub")
    except Exception as e:
        print(f"❌ Erreur lors du chargement : {e}")
        user_data = {}

def save_data():
    """Sauvegarde les données localement et sur GitHub Gist."""
    global user_data
    try:
        # Sauvegarde locale
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(user_data, f, indent=4, ensure_ascii=False)
        print("💾 Données sauvegardées localement.")

        # Sauvegarde Gist
        if not GIST_ID or not GITHUB_GIST_TOKEN:
            print("⚠️ Impossible de sauvegarder sur GitHub (variables manquantes).")
            return

        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GITHUB_GIST_TOKEN}"}
        payload = {
            "files": {
                "data.json": {
                    "content": json.dumps(user_data, indent=4, ensure_ascii=False)
                }
            }
        }

        response = requests.patch(url, headers=headers, json=payload)
        if response.status_code == 200:
            print("☁️ Données sauvegardées sur GitHub Gist avec succès.")
        else:
            print(f"⚠️ Erreur de sauvegarde Gist : {response.status_code} - {response.text[:200]}")

    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde : {e}")

# === Utilitaire : obtenir les données utilisateur ===
def get_user_data(user_id: int):
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {
            "points": 0,
            "lastClaim": None
        }
    return user_data[str(user_id)]

# === Événements ===
@bot.event
async def on_ready():
    load_data()
    print(f"🤖 Bot connecté en tant que {bot.user}")
    print("✅ Prêt et fonctionnel sur Render avec Flask actif !")

# === Commandes ===
@bot.command(name="claim")
async def claim_command(ctx):
    """Permet de réclamer des points toutes les 24h."""
    user = get_user_data(ctx.author.id)
    now = datetime.now()

    if user["lastClaim"]:
        last_claim = datetime.fromisoformat(user["lastClaim"])
        time_diff = now - last_claim
        if time_diff < timedelta(hours=24):
            remaining = timedelta(hours=24) - time_diff
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            await ctx.reply(f"⏰ Tu dois encore attendre **{hours}h {minutes}m** avant de reclaim.")
            return

    points_earned = 10
    user["points"] += points_earned
    user["lastClaim"] = now.isoformat()

    save_data()

    await ctx.reply(f"🎁 Tu as gagné **{points_earned} points** ! Total : **{user['points']} points**.")
    print(f"✅ {ctx.author} a claim {points_earned} points.")

@bot.command(name="points")
async def points_command(ctx):
    """Affiche les points de l'utilisateur."""
    user = get_user_data(ctx.author.id)
    await ctx.reply(f"🏆 Tu as actuellement **{user['points']} points**.")

@bot.command(name="backup")
@commands.has_permissions(administrator=True)
async def backup_command(ctx):
    """Force la sauvegarde manuelle des données."""
    save_data()
    await ctx.author.send("💾 Sauvegarde manuelle effectuée avec succès sur le Gist GitHub !")

@bot.command(name="embed")
@commands.has_permissions(manage_messages=True)
async def embed_command(ctx, *, message: str = None):
    """Envoie un message embed via le bot, sans mention d’auteur."""
    if not message:
        await ctx.reply("❌ Merci de préciser le texte de l’embed. Exemple : `!embed Bienvenue sur le serveur !`")
        return

    embed = discord.Embed(
        description=message,
        color=discord.Color.blurple()  # couleur bleue, tu peux changer si tu veux
    )

    await ctx.send(embed=embed)
    await ctx.message.delete()  # supprime la commande de l’utilisateur pour garder l’anonymat

    print(f"💬 Embed envoyé anonymement : {message}")

### 🔨 Commandes de modération ###

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_command(ctx, member: discord.Member, *, reason: str = "Aucune raison spécifiée"):
    """Bannit un membre du serveur."""
    try:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 {member.mention} a été **banni** pour : {reason}")
        print(f"🔨 {member} banni par {ctx.author} — raison : {reason}")
    except Exception as e:
        await ctx.send(f"❌ Impossible de bannir {member.mention} : {e}")

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban_command(ctx, *, username: str):
    """Débannit un membre du serveur (nom#tag)."""
    banned_users = await ctx.guild.bans()
    name, discriminator = username.split("#")

    for ban_entry in banned_users:
        user = ban_entry.user
        if (user.name, user.discriminator) == (name, discriminator):
            await ctx.guild.unban(user)
            await ctx.send(f"✅ {user.mention} a été **débanni**.")
            print(f"♻️ {user} débanni par {ctx.author}")
            return

    await ctx.send(f"❌ Utilisateur `{username}` introuvable dans la liste des bannis.")

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_command(ctx, member: discord.Member, *, reason: str = "Aucune raison spécifiée"):
    """Expulse un membre du serveur."""
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 {member.mention} a été **exclu** pour : {reason}")
        print(f"👢 {member} exclu par {ctx.author} — raison : {reason}")
    except Exception as e:
        await ctx.send(f"❌ Impossible d’exclure {member.mention} : {e}")

@bot.command(name="mute")
@commands.has_permissions(manage_roles=True)
async def mute_command(ctx, member: discord.Member, *, reason: str = "Aucune raison spécifiée"):
    """Mute un membre (lui retire la permission d’écrire)."""
    guild = ctx.guild
    mute_role = discord.utils.get(guild.roles, name="Muted")

    if not mute_role:
        # Crée le rôle s’il n’existe pas
        mute_role = await guild.create_role(name="Muted", reason="Création automatique du rôle de mute")
        for channel in guild.channels:
            await channel.set_permissions(mute_role, send_messages=False, speak=False)

    await member.add_roles(mute_role, reason=reason)
    await ctx.send(f"🤫 {member.mention} a été **muté** pour : {reason}")
    print(f"🤫 {member} muté par {ctx.author} — raison : {reason}")

### 🔨 Commandes de modération ###

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_command(ctx, member: discord.Member, *, reason: str = "Aucune raison spécifiée"):
    """Bannit un membre du serveur."""
    try:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 {member.mention} a été **banni** pour : {reason}")
        print(f"🔨 {member} banni par {ctx.author} — raison : {reason}")
    except Exception as e:
        await ctx.send(f"❌ Impossible de bannir {member.mention} : {e}")

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban_command(ctx, *, username: str):
    """Débannit un membre du serveur (nom#tag)."""
    banned_users = await ctx.guild.bans()
    name, discriminator = username.split("#")

    for ban_entry in banned_users:
        user = ban_entry.user
        if (user.name, user.discriminator) == (name, discriminator):
            await ctx.guild.unban(user)
            await ctx.send(f"✅ {user.mention} a été **débanni**.")
            print(f"♻️ {user} débanni par {ctx.author}")
            return

    await ctx.send(f"❌ Utilisateur `{username}` introuvable dans la liste des bannis.")

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_command(ctx, member: discord.Member, *, reason: str = "Aucune raison spécifiée"):
    """Expulse un membre du serveur."""
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 {member.mention} a été **exclu** pour : {reason}")
        print(f"👢 {member} exclu par {ctx.author} — raison : {reason}")
    except Exception as e:
        await ctx.send(f"❌ Impossible d’exclure {member.mention} : {e}")

@bot.command(name="mute")
@commands.has_permissions(manage_roles=True)
async def mute_command(ctx, member: discord.Member, *, reason: str = "Aucune raison spécifiée"):
    """Mute un membre (lui retire la permission d’écrire)."""
    guild = ctx.guild
    mute_role = discord.utils.get(guild.roles, name="Muted")

    if not mute_role:
        # Crée le rôle s’il n’existe pas
        mute_role = await guild.create_role(name="Muted", reason="Création automatique du rôle de mute")
        for channel in guild.channels:
            await channel.set_permissions(mute_role, send_messages=False, speak=False)

    await member.add_roles(mute_role, reason=reason)
    await ctx.send(f"🤫 {member.mention} a été **muté** pour : {reason}")
    print(f"🤫 {member} muté par {ctx.author} — raison : {reason}")

# === Lancement du bot ===
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ ERREUR : DISCORD_TOKEN manquant dans les variables d'environnement.")
    else:
        bot.run(TOKEN)
