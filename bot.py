import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import csv
from dotenv import load_dotenv
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

EMOTIONS = {
    "joie":    {"emoji": "😄", "image": "images/humeurs/joie.png", "role": "Joie"},
    "tristesse": {"emoji": "😢", "image": "images/humeurs/tristesse.png", "role": "Tristesse"},
    "peur":    {"emoji": "😱", "image": "images/humeurs/peur.png", "role": "Peur"},
    "colere":  {"emoji": "😡", "image": "images/humeurs/colere.png", "role": "Colère"},
    "degout":  {"emoji": "🤢", "image": "images/humeurs/degout.png", "role": "Dégoût"},
    "anxiete": {"emoji": "😬", "image": "images/humeurs/anxiete.png", "role": "Anxiété"},
    "ennui":   {"emoji": "😐", "image": "images/humeurs/ennui.png", "role": "Ennui"},
    "embarras": {"emoji": "😳", "image": "images/humeurs/embarras.png", "role": "Embarras"},
}

CSV_FILE = "humeurs.csv"
TOILETTE_CSV = "toilettes.csv"
EAU_CSV = "eau.csv"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
scheduler = AsyncIOScheduler()

def save_humeur(user_id, humeur):
    now = datetime.now()
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([now.isoformat(), user_id, humeur])

def save_toilette(user_id, type_passage):
    now = datetime.now()
    with open(TOILETTE_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([now.isoformat(), user_id, type_passage])

def save_eau(user_id, quantite_ml):
    now = datetime.now()
    with open(EAU_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([now.isoformat(), user_id, quantite_ml])

class HumeurView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=60*30)
        self.user_id = user_id

        for humeur, data in EMOTIONS.items():
            self.add_item(HumeurButton(humeur, data["emoji"], user_id))

class HumeurButton(discord.ui.Button):
    def __init__(self, humeur, emoji, user_id):
        super().__init__(style=discord.ButtonStyle.primary, label=humeur.capitalize(), emoji=emoji, custom_id=humeur)
        self.humeur = humeur
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Tu ne peux répondre qu'à ton propre sondage d'humeur !", ephemeral=True)
            return

        humeur_data = EMOTIONS[self.humeur]

        # Enregistrement humeur
        save_humeur(interaction.user.id, self.humeur)

        # Envoi image
        if os.path.exists(humeur_data["image"]):
            file = discord.File(humeur_data["image"])
        else:
            file = None
        await interaction.response.send_message(
            f"{humeur_data['emoji']} Ton humeur du jour : **{self.humeur.capitalize()}** !",
            file=file,
            ephemeral=True
        )

        # Gestion des rôles
        guild = interaction.guild
        member = interaction.user
        roles_to_remove = [discord.utils.get(guild.roles, name=data["role"]) for data in EMOTIONS.values()]
        await member.remove_roles(*filter(None, roles_to_remove))
        role = discord.utils.get(guild.roles, name=humeur_data["role"])
        if not role:
            role = await guild.create_role(name=humeur_data["role"], colour=discord.Colour.random())
        await member.add_roles(role)

        # Modification du pseudo
        base_name = member.name
        # On retire l'ancien préfixe emoji s'il existe
        if member.display_name.startswith("[") and "] " in member.display_name:
            base_name = member.display_name.split("] ", 1)[1]
        new_nick = f"[{humeur_data['emoji']}] {base_name}"
        try:
            await member.edit(nick=new_nick)
        except discord.Forbidden:
            pass  # Le bot n'a pas les permissions, on ignore

@bot.event
async def on_ready():
    print(f"{bot.user} connecté !")
    scheduler.start()
    scheduler.add_job(send_humeur_message, 'cron', hour=8, minute=0)
    scheduler.add_job(send_humeur_message, 'cron', hour=12, minute=0)

async def send_humeur_message():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        for member in channel.members:
            if not member.bot:
                view = HumeurView(user_id=member.id)
                await channel.send(
                    f"Bonjour {member.mention} ! Quelle est ton humeur du jour ?",
                    view=view
                )

@bot.command()
async def humeurstats(ctx, periode="semaine"):
    """
    !humeurstats semaine ou !humeurstats mois
    """
    user_id = ctx.author.id
    now = datetime.now()
    if periode == "semaine":
        since = now - timedelta(days=7)
    elif periode == "mois":
        since = now - timedelta(days=30)
    else:
        await ctx.send("Période non reconnue. Utilise `semaine` ou `mois`.")
        return

    stats = {h: 0 for h in EMOTIONS}
    if not os.path.exists(CSV_FILE):
        await ctx.send("Aucune donnée pour le moment !")
        return

    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            date, uid, humeur = row
            try:
                date_dt = datetime.fromisoformat(date)
            except:
                continue
            if int(uid) == user_id and date_dt >= since:
                if humeur in stats:
                    stats[humeur] += 1

    # Génération graphique
    labels = [EMOTIONS[h]["emoji"] + " " + h.capitalize() for h in EMOTIONS]
    values = [stats[h] for h in EMOTIONS]
    plt.figure(figsize=(8,4))
    plt.bar(labels, values)
    plt.title(f"Humeur de {ctx.author.display_name} ({periode})")
    plt.ylabel("Nombre de fois")
    plt.tight_layout()
    plt.savefig("stat_humeur.png")
    plt.close()
    file = discord.File("stat_humeur.png")
    await ctx.send(f"Voici tes statistiques d'humeur sur la {periode} :", file=file)

@bot.command()
async def pipi(ctx):
    """Enregistre un passage aux toilettes (petite commission)."""
    save_toilette(ctx.author.id, "pipi")
    await ctx.send(f"💦 Noté, {ctx.author.mention} !")

@bot.command()
async def caca(ctx):
    """Enregistre un passage aux toilettes (grosse commission)."""
    save_toilette(ctx.author.id, "caca")
    await ctx.send(f"💩 Noté, {ctx.author.mention} !")

@bot.command()
async def toilettestats(ctx, periode="semaine"):
    """
    !toilettestats jour, semaine ou mois
    """
    user_id = ctx.author.id
    now = datetime.now()
    if periode == "jour":
        since = now - timedelta(days=1)
    elif periode == "semaine":
        since = now - timedelta(days=7)
    elif periode == "mois":
        since = now - timedelta(days=30)
    else:
        await ctx.send("Période non reconnue. Utilise `jour`, `semaine` ou `mois`.")
        return

    stats = {"pipi": 0, "caca": 0}
    if not os.path.exists(TOILETTE_CSV):
        await ctx.send("Aucune donnée pour le moment !")
        return

    with open(TOILETTE_CSV, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            date, uid, type_passage = row
            try:
                date_dt = datetime.fromisoformat(date)
            except:
                continue
            if int(uid) == user_id and date_dt >= since and type_passage in stats:
                stats[type_passage] += 1

    labels = ["💦 Pipi", "💩 Caca"]
    values = [stats["pipi"], stats["caca"]]
    plt.figure(figsize=(6, 4))
    plt.bar(labels, values, color=["#3498db", "#8B5A2B"])
    plt.title(f"Toilettes de {ctx.author.display_name} ({periode})")
    plt.ylabel("Nombre de passages")
    plt.tight_layout()
    plt.savefig("stat_toilette.png")
    plt.close()
    file = discord.File("stat_toilette.png")
    await ctx.send(f"Voici tes statistiques toilettes sur le/la {periode} :", file=file)

@bot.command()
async def eau(ctx, quantite: int = 250):
    """!eau [quantité en ml, défaut 250]"""
    save_eau(ctx.author.id, quantite)
    await ctx.send(f"💧 {quantite} ml enregistrés pour {ctx.author.mention} !")

@bot.command()
async def eaujour(ctx):
    """Affiche le total d'eau bue aujourd'hui."""
    user_id = ctx.author.id
    today = datetime.now().date()
    total = 0
    if os.path.exists(EAU_CSV):
        with open(EAU_CSV, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 3:
                    continue
                date, uid, quantite = row
                try:
                    date_dt = datetime.fromisoformat(date)
                except:
                    continue
                if int(uid) == user_id and date_dt.date() == today:
                    total += int(quantite)
    await ctx.send(f"💧 {ctx.author.mention} a bu **{total} ml** aujourd'hui.")

@bot.command()
async def eaustats(ctx, periode="semaine"):
    """
    !eaustats semaine ou mois — quantité d'eau bue par jour
    """
    user_id = ctx.author.id
    now = datetime.now()
    if periode == "semaine":
        nb_jours = 7
    elif periode == "mois":
        nb_jours = 30
    else:
        await ctx.send("Période non reconnue. Utilise `semaine` ou `mois`.")
        return

    since = now - timedelta(days=nb_jours)
    par_jour = {}
    if os.path.exists(EAU_CSV):
        with open(EAU_CSV, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 3:
                    continue
                date, uid, quantite = row
                try:
                    date_dt = datetime.fromisoformat(date)
                except:
                    continue
                if int(uid) == user_id and date_dt >= since:
                    jour = date_dt.date()
                    par_jour[jour] = par_jour.get(jour, 0) + int(quantite)

    if not par_jour:
        await ctx.send("Aucune donnée pour le moment !")
        return

    jours_tries = sorted(par_jour.keys())
    labels = [j.strftime("%d/%m") for j in jours_tries]
    values = [par_jour[j] for j in jours_tries]

    plt.figure(figsize=(8, 4))
    plt.bar(labels, values, color="#3498db")
    plt.axhline(y=1500, color="green", linestyle="--", label="Objectif 1.5L")
    plt.title(f"Eau bue par {ctx.author.display_name} ({periode})")
    plt.ylabel("ml")
    plt.legend()
    plt.tight_layout()
    plt.savefig("stat_eau.png")
    plt.close()
    file = discord.File("stat_eau.png")
    await ctx.send(f"Voici tes statistiques d'eau sur la {periode} :", file=file)

bot.run(TOKEN)
