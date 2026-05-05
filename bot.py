import discord
import random
import os
import json

TOKEN = os.getenv("TOKEN")
DONO_ID = 1425943327580360836

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Client(intents=intents)

CANAL_PARTIDAS = "🔫│partidas"
CANAL_RANKING = "🏆│ranking"
CARGO_MEMBRO = "Membro"

fila = []
limite = 4
criador_partida = None

ultimo_time_azul = []
ultimo_time_vermelho = []

# ================= JSON =================
def carregar(nome):
    try:
        with open(nome, "r") as f:
            return json.load(f)
    except:
        return {}

def salvar(nome, data):
    with open(nome, "w") as f:
        json.dump(data, f, indent=4)

# ================= REGRAS =================
def aceitou(user_id):
    return str(user_id) in carregar("aceitou.json")

def marcar(user_id):
    data = carregar("aceitou.json")
    data[str(user_id)] = True
    salvar("aceitou.json", data)

# ================= RANK =================
def add_win(uid):
    data = carregar("ranking.json")
    uid = str(uid)

    if uid not in data:
        data[uid] = {"wins":0,"losses":0}

    data[uid]["wins"] += 1
    salvar("ranking.json", data)

def add_loss(uid):
    data = carregar("ranking.json")
    uid = str(uid)

    if uid not in data:
        data[uid] = {"wins":0,"losses":0}

    data[uid]["losses"] += 1
    salvar("ranking.json", data)

# ================= BOTÕES =================
class Painel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.green)
    async def entrar(self, interaction, button):
        if not aceitou(interaction.user.id):
            return await interaction.response.send_message("Aceite as regras primeiro.", ephemeral=True)

        if interaction.user.id in fila:
            return await interaction.response.send_message("Já entrou.", ephemeral=True)

        fila.append(interaction.user.id)
        await interaction.response.send_message("Entrou na fila!", ephemeral=True)

    @discord.ui.button(label="Começar", style=discord.ButtonStyle.blurple)
    async def comecar(self, interaction, button):
        if interaction.user.id != criador_partida:
            return await interaction.response.send_message("Só o host pode iniciar.", ephemeral=True)

        await iniciar_partida(interaction.guild)
        await interaction.response.send_message("Partida iniciada!")

# ================= PARTIDA =================
async def iniciar_partida(guild):
    global ultimo_time_azul, ultimo_time_vermelho

    jogadores = fila.copy()
    random.shuffle(jogadores)

    meio = len(jogadores)//2
    ultimo_time_azul = jogadores[:meio]
    ultimo_time_vermelho = jogadores[meio:]

    for p in jogadores:
        try:
            user = await bot.fetch_user(p)
            await user.send("🎮 Só falta você para começar!")
        except:
            pass

    fila.clear()

# ================= EVENTOS =================
@bot.event
async def on_ready():
    print("Bot online")

@bot.event
async def on_member_join(member):
    cargo = discord.utils.get(member.guild.roles, name=CARGO_MEMBRO)
    if cargo:
        await member.add_roles(cargo)

# ================= COMANDOS =================
@bot.event
async def on_message(msg):
    global criador_partida

    if msg.author.bot:
        return

    # ================= PARTIDA =================
    if msg.content.startswith("!partida"):
        if msg.channel.name != CANAL_PARTIDAS:
            return await msg.reply(f"Use no canal {CANAL_PARTIDAS}")

        criador_partida = msg.author.id
        await msg.channel.send("Partida criada!", view=Painel())

    # ================= VITÓRIA =================
    elif msg.content.lower().startswith("!vitória"):
        if msg.channel.name != CANAL_PARTIDAS:
            return await msg.reply(f"Use no canal {CANAL_PARTIDAS}")

        if "azul" in msg.content:
            for p in ultimo_time_azul:
                add_win(p)
            for p in ultimo_time_vermelho:
                add_loss(p)

            await msg.channel.send("Vitória Azul!")

        elif "vermelho" in msg.content:
            for p in ultimo_time_vermelho:
                add_win(p)
            for p in ultimo_time_azul:
                add_loss(p)

            await msg.channel.send("Vitória Vermelha!")

    # ================= RANK =================
    elif msg.content.startswith("!ranking"):
        if msg.channel.name != CANAL_RANKING:
            return await msg.reply(f"Use no canal {CANAL_RANKING}")

        data = carregar("ranking.json")
        user = str(msg.author.id)

        stats = data.get(user, {"wins":0,"losses":0})
        wins = stats["wins"]
        losses = stats["losses"]

        await msg.channel.send(
            f"🏆 Vitórias: {wins}\n💀 Derrotas: {losses}"
        )

bot.run(TOKEN)