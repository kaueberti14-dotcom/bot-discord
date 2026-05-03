import discord
import random
import os
import json
from urllib.parse import urlparse, parse_qs

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Client(intents=intents)

fila = []
limite = 4
criador_partida = None
link_partida = None
painel_partida = None

ultimo_time_azul = []
ultimo_time_vermelho = []
ultimo_host = None
ultimo_modo = None


# ===== RANKING =====
def carregar_ranking():
    try:
        with open("ranking.json", "r") as f:
            return json.load(f)
    except:
        return {}

def salvar_ranking(data):
    with open("ranking.json", "w") as f:
        json.dump(data, f, indent=4)

def adicionar_vitoria(uid):
    data = carregar_ranking()
    uid = str(uid)
    data[uid] = data.get(uid, 0) + 1
    salvar_ranking(data)

def remover_vitoria(uid):
    data = carregar_ranking()
    uid = str(uid)
    if uid in data:
        data[uid] = max(0, data[uid] - 1)
    salvar_ranking(data)


# ===== UTILS =====
def embed_erro(txt):
    return discord.Embed(title="❌ Erro", description=txt, color=discord.Color.red())

def tem_cargo(member):
    return any(r.name in ["HOST", "Lider", "Sub-Lider"] for r in member.roles)

def pegar_codigo(link):
    try:
        return parse_qs(urlparse(link).query).get("privateServerLinkCode", ["?"])[0]
    except:
        return "?"


# ===== EMBED PROCURANDO =====
def embed_procurando(guild):
    host = guild.get_member(criador_partida)
    nome = host.display_name if host else "Host"

    embed = discord.Embed(
        title="🔎 PROCURANDO PARTIDA...",
        description="Aguardando jogadores...",
        color=discord.Color.dark_red()
    )

    embed.set_author(name=f"Host: {nome}")

    lista = "\n".join([f"`{i+1}.` <@{j}>" for i,j in enumerate(fila)]) or "Nenhum"

    embed.add_field(name="👥 Jogadores", value=lista, inline=False)
    embed.add_field(
        name="📋 Info",
        value=f"MODO: `{limite//2}v{limite//2}`\nJOGADORES: `{len(fila)}/{limite}`",
        inline=False
    )

    embed.set_image(url="attachment://procurando.png")
    return embed


# ===== TIMES =====
def montar_times(j):
    random.shuffle(j)
    metade = len(j)//2
    return j[:metade], j[metade:]


# ===== BOTÕES =====
class Painel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.green)
    async def entrar(self, i, b):
        if i.user.id in fila:
            return await i.response.send_message("Já entrou", ephemeral=True)

        fila.append(i.user.id)

        file = discord.File("procurando.png", filename="procurando.png")
        embed = embed_procurando(i.guild)

        await i.response.edit_message(embed=embed, view=self, attachments=[file])

        if len(fila) >= limite:
            await iniciar_partida(i.guild)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.red)
    async def sair(self, i, b):
        if i.user.id not in fila:
            return

        fila.remove(i.user.id)

        file = discord.File("procurando.png", filename="procurando.png")
        embed = embed_procurando(i.guild)

        await i.response.edit_message(embed=embed, view=self, attachments=[file])


# ===== INICIAR PARTIDA =====
async def iniciar_partida(guild):
    global ultimo_time_azul, ultimo_time_vermelho, ultimo_host, ultimo_modo

    canal = discord.utils.get(guild.text_channels, name="partidas")

    azul, vermelho = montar_times(fila.copy())

    ultimo_time_azul = azul
    ultimo_time_vermelho = vermelho
    ultimo_host = criador_partida
    ultimo_modo = f"{limite//2}v{limite//2}"

    embed = discord.Embed(
        title="⚔️ PARTIDA EM ANDAMENTO",
        color=discord.Color.dark_red()
    )

    embed.add_field(name="🟦 Azul", value="\n".join([f"<@{x}>" for x in azul]))
    embed.add_field(name="🟥 Vermelho", value="\n".join([f"<@{x}>" for x in vermelho]))

    await painel_partida.edit(embed=embed, view=None, attachments=[])

    for p in fila:
        user = await bot.fetch_user(p)
        try:
            await user.send(f"Link: {link_partida}\nCódigo: {pegar_codigo(link_partida)}")
        except:
            pass

    fila.clear()


# ===== EVENTOS =====
@bot.event
async def on_ready():
    print("Online")


@bot.event
async def on_message(msg):
    global limite, criador_partida, link_partida, painel_partida

    if msg.author.bot:
        return

    # criar partida
    if msg.content.startswith("!criarfila"):
        if not tem_cargo(msg.author):
            return await msg.reply(embed=embed_erro("Sem permissão"))

        canal = discord.utils.get(msg.guild.text_channels, name="partidas")

        partes = msg.content.split()
        numero = int(partes[0].replace("!criarfila",""))

        fila.clear()
        limite = numero
        criador_partida = msg.author.id
        link_partida = partes[1]

        file = discord.File("procurando.png", filename="procurando.png")
        embed = embed_procurando(msg.guild)

        painel_partida = await canal.send(embed=embed, view=Painel(), file=file)

        await msg.reply("Criado")

    # vitória
    elif msg.content.startswith("!vitória"):
        cmd = msg.content.lower()

        if "azul" in cmd:
            vencedores = ultimo_time_azul
            perdedores = ultimo_time_vermelho
            img = "vitoria_azul.png"
            cor = discord.Color.blue()

        elif "vermelho" in cmd:
            vencedores = ultimo_time_vermelho
            perdedores = ultimo_time_azul
            img = "vitoria_vermelho.png"
            cor = discord.Color.red()

        else:
            return

        for v in vencedores:
            adicionar_vitoria(v)

        for p in perdedores:
            remover_vitoria(p)

        embed = discord.Embed(
            title="🏆 PARTIDA FINALIZADA",
            color=cor
        )

        embed.add_field(name="🏆 Vencedores", value="\n".join([f"<@{x}>" for x in vencedores]))
        embed.add_field(name="💀 Perdedor", value="\n".join([f"<@{x}>" for x in perdedores]))
        embed.add_field(name="Modo", value=ultimo_modo)

        file = discord.File(img, filename=img)
        embed.set_image(url=f"attachment://{img}")

        await msg.channel.send(embed=embed, file=file)

    # ranking
    elif msg.content == "!ranking":
        data = carregar_ranking()

        top = sorted(data.items(), key=lambda x: x[1], reverse=True)

        texto = ""
        for i,(uid,pts) in enumerate(top[:10],1):
            texto += f"{i}. <@{uid}> - {pts}\n"

        embed = discord.Embed(title="🏆 Ranking", description=texto or "Vazio", color=discord.Color.gold())
        await msg.channel.send(embed=embed)


bot.run(TOKEN)