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

LEVEL_FILE = "levels.json"

# Charger les données
def load_levels():
    try:
        with open(LEVEL_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Sauvegarder les données
def save_levels(data):
    with open(LEVEL_FILE, "w") as f:
        json.dump(data, f, indent=4)

levels = load_levels()

# Fichier pour stocker les salons de bienvenue et d'au revoir
WELCOME_FILE = "welcome_channels.json"

def load_welcome_channels():
    try:
        with open(WELCOME_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_welcome_channels(data):
    with open(WELCOME_FILE, "w") as f:
        json.dump(data, f, indent=4)

welcome_channels = load_welcome_channels()

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

@bot.command(name="dm")
@commands.has_permissions(administrator=True)
async def send_dm(ctx, users: commands.Greedy[commands.MemberConverter], *, message):
    """
    Envoie un message privé à un ou plusieurs utilisateurs.
    Utilisation : !dm @user1 @user2 ... ton message ici
    """
    if not users:
        await ctx.send("❌ Vous devez mentionner au moins un utilisateur.")
        return

    embed = discord.Embed(
        description=message,
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Message de {ctx.guild.name}")

    success = []
    failed = []

    for user in users:
        try:
            await user.send(embed=embed)
            success.append(user.display_name)
        except Exception as e:
            failed.append(user.display_name)

    response = ""
    if success:
        response += f"✅ Message envoyé à : {', '.join(success)}\n"
    if failed:
        response += f"❌ Impossible d'envoyer le message à : {', '.join(failed)}"

    await ctx.send(response)


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

# ---------------- COMMANDES ----------------

# Définir le salon de bienvenue
@bot.command(name="setwelcome")
@commands.has_permissions(administrator=True)
async def set_welcome(ctx, channel: commands.TextChannelConverter):
    welcome_channels[str(ctx.guild.id)] = welcome_channels.get(str(ctx.guild.id), {})
    welcome_channels[str(ctx.guild.id)]["welcome"] = channel.id
    save_welcome_channels(welcome_channels)
    await ctx.send(f"✅ Salon de bienvenue défini sur {channel.mention}")

# Définir le salon d’au revoir
@bot.command(name="setgoodbye")
@commands.has_permissions(administrator=True)
async def set_goodbye(ctx, channel: commands.TextChannelConverter):
    welcome_channels[str(ctx.guild.id)] = welcome_channels.get(str(ctx.guild.id), {})
    welcome_channels[str(ctx.guild.id)]["goodbye"] = channel.id
    save_welcome_channels(welcome_channels)
    await ctx.send(f"✅ Salon d’au revoir défini sur {channel.mention}")

# ---------------- ÉVÉNEMENTS ----------------

# Message de bienvenue
@bot.event
async def on_member_join(member):
    guild_id = str(member.guild.id)
    if guild_id in welcome_channels and "welcome" in welcome_channels[guild_id]:
        channel_id = welcome_channels[guild_id]["welcome"]
        channel = member.guild.get_channel(channel_id)
        if channel:
            await channel.send(f"👋 Bienvenue {member.mention} sur **{member.guild.name}** !")

# Message d’au revoir
@bot.event
async def on_member_remove(member):
    guild_id = str(member.guild.id)
    if guild_id in welcome_channels and "goodbye" in welcome_channels[guild_id]:
        channel_id = welcome_channels[guild_id]["goodbye"]
        channel = member.guild.get_channel(channel_id)
        if channel:
            await channel.send(f"👋 Au revoir {member.display_name}, nous espérons te revoir bientôt !")


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

@bot.command(name="activity")
@commands.has_permissions(administrator=True)
async def activity_command(ctx, status: str, activity_type: str, *, description: str):
    """
    Change l'activité et le statut du bot.
    Exemple : !activity online playing Jouer à Discord
    Statuts possibles : online, dnd, idle, invisible
    Types d'activités : playing, watching, listening, streaming
    """
    status_dict = {
        "online": discord.Status.online,
        "dnd": discord.Status.dnd,
        "idle": discord.Status.idle,
        "invisible": discord.Status.invisible
    }

    activity_dict = {
        "playing": discord.ActivityType.playing,
        "watching": discord.ActivityType.watching,
        "listening": discord.ActivityType.listening,
        "streaming": discord.ActivityType.streaming
    }

    if status.lower() not in status_dict:
        await ctx.send(f"❌ Statut invalide. Choisis parmi : {', '.join(status_dict.keys())}")
        return

    if activity_type.lower() not in activity_dict:
        await ctx.send(f"❌ Type d'activité invalide. Choisis parmi : {', '.join(activity_dict.keys())}")
        return

    try:
        activity = discord.Activity(type=activity_dict[activity_type.lower()], name=description)
        await bot.change_presence(status=status_dict[status.lower()], activity=activity)
        await ctx.send(f"✅ Activité du bot mise à jour : **{activity_type.capitalize()} {description}** avec le statut **{status}**")
        print(f"✅ Activité modifiée par {ctx.author}: {activity_type.capitalize()} {description} | Status: {status}")
    except Exception as e:
        await ctx.send(f"❌ Une erreur est survenue : {e}")

# ---------------- COMMANDES LEVEL----------------

# Ajouter un niveau à un utilisateur
@bot.command(name="addlevel")
@commands.has_permissions(administrator=True)
async def add_level(ctx, member: commands.MemberConverter, amount: int):
    user_id = str(member.id)
    levels[user_id] = levels.get(user_id, 0) + amount
    save_levels(levels)
    await ctx.send(f"✅ {amount} niveaux ajoutés à {member.display_name}. Nouveau niveau : {levels[user_id]}")

# Retirer un niveau à un utilisateur
@bot.command(name="removelevel")
@commands.has_permissions(administrator=True)
async def remove_level(ctx, member: commands.MemberConverter, amount: int):
    user_id = str(member.id)
    levels[user_id] = max(0, levels.get(user_id, 0) - amount)
    save_levels(levels)
    await ctx.send(f"⚠️ {amount} niveaux retirés à {member.display_name}. Nouveau niveau : {levels[user_id]}")

# Vérifier son niveau ou celui d'un autre
@bot.command(name="level")
async def check_level(ctx, member: commands.MemberConverter = None):
    member = member or ctx.author
    user_id = str(member.id)
    lvl = levels.get(user_id, 0)
    await ctx.send(f"🌟 {member.display_name} est au niveau {lvl}.")

# Afficher le top niveaux
@bot.command(name="toplevel")
async def top_level(ctx):
    if not levels:
        await ctx.send("Aucun niveau enregistré.")
        return
    # Trier par niveau décroissant
    top_users = sorted(levels.items(), key=lambda x: x[1], reverse=True)[:10]
    message = "🏆 **Top niveaux**:\n"
    for i, (user_id, lvl) in enumerate(top_users, start=1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"Utilisateur supprimé ({user_id})"
        message += f"{i}. {name} — Niveau {lvl}\n"
    await ctx.send(message)

@bot.command(name="dm")
@commands.has_permissions(administrator=True)
async def send_dm(ctx, user: commands.MemberConverter, *, message):
    """Envoie un message privé à l'utilisateur mentionné"""
    try:
        await user.send(message)
        await ctx.send(f"✅ Message envoyé à {user.display_name}")
    except Exception as e:
        await ctx.send(f"❌ Impossible d'envoyer le message : {e}")

@bot.command(name="help")
async def custom_help(ctx):
    embed = discord.Embed(
        title="📜 Aide du Bot",
        description="Voici la liste des commandes disponibles et leur utilisation :",
        color=discord.Color.green()
    )

    # Commandes d'administration
    embed.add_field(
        name="⚙️ Administration",
        value=(
            "`!ban @user [raison]` - Banni un membre.\n"
            "`!unban user#1234` - Débanni un membre.\n"
            "`!kick @user [raison]` - Exclut un membre.\n"
            "`!mute @user [temps]` - Mute un membre pour un temps donné.\n"
            "`!activity [type] [texte]` - Change l'activité du bot. Types : online, dnd, idle, watching, streaming.\n"
        ),
        inline=False
    )

    # Commandes de points / level
    embed.add_field(
        name="🏆 Points et Levels",
        value=(
            "`!addlevel @user [nombre]` - Ajoute des niveaux à un utilisateur.\n"
            "`!removelevel @user [nombre]` - Retire des niveaux à un utilisateur.\n"
            "`!level @user` - Affiche le niveau d'un utilisateur.\n"
            "`!toplevel` - Affiche le top des utilisateurs par niveau.\n"
        ),
        inline=False
    )

    # Commandes anonymes / message
    embed.add_field(
        name="✉️ Messages",
        value=(
            "`!dm @user1 @user2 ... [message]` - Envoie un MP anonyme aux utilisateurs mentionnés.\n"
            "`!say [message]` - Fait parler le bot anonymement dans le salon.\n"
        ),
        inline=False
    )

    # Commandes fun ou autres
    embed.add_field(
        name="🎉 Divers",
        value=(
            "`!reactionselect [emoji]` - Organise un petit jeu de réaction (admins seulement).\n"
        ),
        inline=False
    )

    embed.set_footer(text=f"Demandé par {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
    await ctx.send(embed=embed)

# === Lancement du bot ===
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ ERREUR : DISCORD_TOKEN manquant dans les variables d'environnement.")
    else:
        bot.run(TOKEN)
