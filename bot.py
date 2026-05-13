import discord
import random
import os
import json
from urllib.parse import urlparse, parse_qs

TOKEN = os.getenv("TOKEN")
DONO_ID = 1425943327580360836

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Client(intents=intents)

CANAL_COMANDOS_GERAL = "🤖│comandos"
CANAL_COMANDOS_FUNCOES = "⚙🤖│comandos-funções"
CANAL_COMANDOS_PARTIDAS = "🔫│comandos-partidas"

CANAL_PARTIDAS = "🔫│partidas"
CANAL_EQUIPE = "equipe🤝"
CANAL_MAPAS = "mapas🗺️"
CANAL_REGRAS_HOST = "📜│regras-host"
CANAL_REGRAS = "📋│regras"

CARGO_MEMBRO = "Membro"

fila = []
limite = 4
criador_partida = None
link_partida = None
painel_partida = None

ultimo_time_azul = []
ultimo_time_vermelho = []
ultimo_host = None
ultimo_modo = None

convites = {}
duplas = {}
rivais = set()

# ================= JSON =================

def carregar_json(nome):
    try:
        with open(nome, "r") as f:
            return json.load(f)
    except:
        return {}

def salvar_json(nome, data):
    with open(nome, "w") as f:
        json.dump(data, f, indent=4)

def carregar_ranking():
    return carregar_json("ranking.json")

def salvar_ranking(data):
    salvar_json("ranking.json", data)

def carregar_aceite():
    return carregar_json("aceitou.json")

def salvar_aceite(data):
    salvar_json("aceitou.json", data)

# ================= SISTEMA =================

def aceitou_regras(user_id):
    return str(user_id) in carregar_aceite()

def marcar_aceite(user_id):
    data = carregar_aceite()
    data[str(user_id)] = True
    salvar_aceite(data)

def get_player(data, uid):
    uid = str(uid)

    if uid not in data:
        data[uid] = {
            "wins": 0,
            "losses": 0,
            "streak": 0
        }

    return data[uid]

def adicionar_vitoria(uid):
    data = carregar_ranking()
    p = get_player(data, uid)

    p["wins"] += 1
    p["streak"] += 1

    salvar_ranking(data)

def adicionar_derrota(uid):
    data = carregar_ranking()
    p = get_player(data, uid)

    p["losses"] += 1
    p["streak"] = 0

    salvar_ranking(data)

# ================= PERMISSÕES =================

def tem_cargo(member):
    return any(role.name in ["HOST", "Lider", "Sub-Lider"] for role in member.roles)

def eh_lider_ou_sub(member):
    return any(role.name in ["Lider", "Sub-Lider"] for role in member.roles)

def eh_host(member):
    return any(role.name == "HOST" for role in member.roles)

# ================= UTILS =================

def get_channel(guild, *nomes):
    for nome in nomes:
        canal = discord.utils.get(guild.text_channels, name=nome)

        if canal:
            return canal

    return None

def embed_erro(texto):
    return discord.Embed(
        title="❌ Erro",
        description=texto,
        color=discord.Color.red()
    )

def lista_jogadores():
    if not fila:
        return "Nenhum jogador."

    return "\n".join([
        f"`{i+1}.` <@{j}>"
        for i, j in enumerate(fila)
    ])

# ================= EMBEDS =================

def embed_procurando(guild):
    host = guild.get_member(criador_partida)
    nome_host = host.display_name if host else "Host"

    embed = discord.Embed(
        title="🔎 PROCURANDO PARTIDA...",
        description="Aguardando jogadores entrarem na partida.",
        color=discord.Color.dark_red()
    )

    embed.set_author(
        name=f"Hoster Responsável: {nome_host}",
        icon_url=host.display_avatar.url if host else None
    )

    embed.add_field(
        name="👥 JOGADORES",
        value=lista_jogadores(),
        inline=False
    )

    embed.add_field(
        name="📋 INFO",
        value=(
            f"MODO: `{limite//2}v{limite//2}`\n"
            f"JOGADORES: `{len(fila)}/{limite}`\n"
            f"HOST: `{nome_host}`"
        ),
        inline=False
    )

    embed.set_image(url="attachment://procurando.png")

    embed.set_footer(
        text="AR2 Brasil [BR] • Procurando partida"
    )

    return embed

def embed_cancelada():
    return discord.Embed(
        title="❌ PARTIDA CANCELADA!",
        description="A partida foi cancelada.",
        color=discord.Color.red()
    )

# ================= TIMES =================

def montar_times(jogadores):
    random.shuffle(jogadores)

    meio = len(jogadores)//2

    azul = jogadores[:meio]
    vermelho = jogadores[meio:]

    return vermelho, azul

# ================= BOTÕES =================

class Painel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.green)
    async def entrar(self, interaction, button):

        if not aceitou_regras(interaction.user.id):
            return await interaction.response.send_message(
                "❌ Você precisa aceitar as regras.",
                ephemeral=True
            )

        if interaction.user.id in fila:
            return await interaction.response.send_message(
                "Você já entrou.",
                ephemeral=True
            )

        if len(fila) >= limite:
            return await interaction.response.send_message(
                "Partida cheia.",
                ephemeral=True
            )

        fila.append(interaction.user.id)

        file = discord.File("procurando.png", filename="procurando.png")

        await interaction.response.edit_message(
            embed=embed_procurando(interaction.guild),
            view=self,
            attachments=[file]
        )

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.red)
    async def sair(self, interaction, button):

        if interaction.user.id not in fila:
            return await interaction.response.send_message(
                "Você não está na partida.",
                ephemeral=True
            )

        fila.remove(interaction.user.id)

        file = discord.File("procurando.png", filename="procurando.png")

        await interaction.response.edit_message(
            embed=embed_procurando(interaction.guild),
            view=self,
            attachments=[file]
        )

    @discord.ui.button(label="Começar", style=discord.ButtonStyle.blurple)
    async def comecar(self, interaction, button):

        if interaction.user.id != criador_partida and not eh_lider_ou_sub(interaction.user):
            return await interaction.response.send_message(
                embed=embed_erro("Você não possui permissão para começar essa partida!"),
                ephemeral=True
            )

        if len(fila) < limite:
            return await interaction.response.send_message(
                f"❌ A partida ainda não está cheia. `{len(fila)}/{limite}`",
                ephemeral=True
            )

        await interaction.response.defer()

        await iniciar_partida(interaction.guild)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.gray)
    async def cancelar(self, interaction, button):

        global criador_partida
        global link_partida
        global painel_partida

        if interaction.user.id != criador_partida and eh_host(interaction.user) and not eh_lider_ou_sub(interaction.user):
            return await interaction.response.send_message(
                embed=embed_erro(
                    "Você não possui permissão para cancelar partida de outros Host"
                ),
                ephemeral=True
            )

        if interaction.user.id != criador_partida and not eh_lider_ou_sub(interaction.user):
            return await interaction.response.send_message(
                embed=embed_erro(
                    "Você não possui permissão para cancelar essa partida!"
                ),
                ephemeral=True
            )

        fila.clear()

        criador_partida = None
        link_partida = None
        painel_partida = None

        await interaction.response.edit_message(
            embed=embed_cancelada(),
            view=None,
            attachments=[]
        )

# ================= INICIAR =================

async def iniciar_partida(guild):

    global ultimo_time_azul
    global ultimo_time_vermelho
    global ultimo_host
    global ultimo_modo

    jogadores = fila.copy()

    vermelho, azul = montar_times(jogadores)

    ultimo_time_azul = azul
    ultimo_time_vermelho = vermelho
    ultimo_host = criador_partida
    ultimo_modo = f"{limite//2}v{limite//2}"

    host = guild.get_member(criador_partida)
    nome_host = host.display_name if host else "Host"

    embed = discord.Embed(
        title="⚔️ PARTIDA EM ANDAMENTO",
        description="Link enviado no privado dos jogadores.",
        color=discord.Color.dark_red()
    )

    embed.set_author(
        name=f"Hoster Responsável: {nome_host}",
        icon_url=host.display_avatar.url if host else None
    )

    embed.add_field(
        name="🟦 TIME AZUL",
        value="\n".join([f"<@{x}>" for x in azul]),
        inline=True
    )

    embed.add_field(
        name="🟥 TIME VERMELHO",
        value="\n".join([f"<@{x}>" for x in vermelho]),
        inline=True
    )

    file = discord.File("partida.png", filename="partida.png")

    embed.set_image(url="attachment://partida.png")

    if painel_partida:
        await painel_partida.edit(
            embed=embed,
            view=None,
            attachments=[file]
        )

    for player_id in jogadores:
        try:
            user = await bot.fetch_user(player_id)

            embed_dm = discord.Embed(
                title="🎮 Só falta você para começar!",
                description=f"[Clique aqui para entrar no servidor privado]({link_partida})",
                color=discord.Color.dark_red()
            )

            await user.send(embed=embed_dm)

        except:
            pass

    fila.clear()

# ================= EVENTOS =================

@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")

@bot.event
async def on_member_join(member):
    cargo = discord.utils.get(
        member.guild.roles,
        name=CARGO_MEMBRO
    )

    if cargo:
        try:
            await member.add_roles(cargo)
        except:
            pass

# ================= COMANDOS =================

@bot.event
async def on_message(msg):

    global limite
    global criador_partida
    global link_partida
    global painel_partida

    if msg.author.bot:
        return

    # ================= PARTIDA =================

    if msg.content.startswith("!partida"):

        if msg.channel.name != CANAL_COMANDOS_PARTIDAS:
            return await msg.reply(
                f"❌ Use este comando no canal #{CANAL_COMANDOS_PARTIDAS}"
            )

        if not tem_cargo(msg.author):
            return await msg.reply(
                embed=embed_erro(
                    "Você não possui permissão para criar uma partida!"
                )
            )

        canal = get_channel(msg.guild, CANAL_PARTIDAS)

        partes = msg.content.split()

        if len(partes) < 2:
            return await msg.reply(
                "Use: `!partida4 link_do_servidor_privado`"
            )

        numero = int(
            partes[0].replace("!partida", "")
        )

        limite = numero
        criador_partida = msg.author.id
        link_partida = partes[1]

        fila.clear()

        file = discord.File(
            "procurando.png",
            filename="procurando.png"
        )

        painel_partida = await canal.send(
            embed=embed_procurando(msg.guild),
            view=Painel(),
            file=file
        )

        await msg.reply("Partida criada!")

    # ================= VITÓRIA =================

    elif msg.content.lower().startswith("!vitória"):

        if msg.channel.name != CANAL_COMANDOS_PARTIDAS:
            return await msg.reply(
                f"❌ Use este comando no canal #{CANAL_COMANDOS_PARTIDAS}"
            )

        canal = get_channel(msg.guild, CANAL_PARTIDAS)

        comando = msg.content.lower()

        if "azul" in comando:

            vencedores = ultimo_time_azul
            perdedores = ultimo_time_vermelho

            imagem = "vitoria_azul.png"

            cor = discord.Color.blue()

            nome_time = "🟦 TIME AZUL"

        else:

            vencedores = ultimo_time_vermelho
            perdedores = ultimo_time_azul

            imagem = "vitoria_vermelho.png"

            cor = discord.Color.red()

            nome_time = "🟥 TIME VERMELHO"

        ganhos = []
        perdas = []

        for jogador in vencedores:
            adicionar_vitoria(jogador)

            ganhos.append(
                f"<@{jogador}> ➜ +1 Vitória 🏆"
            )

        for jogador in perdedores:
            adicionar_derrota(jogador)

            perdas.append(
                f"<@{jogador}> ➜ +1 Derrota 💀"
            )

        embed = discord.Embed(
            title="🏆 PARTIDA FINALIZADA",
            description=f"Vitória do {nome_time}",
            color=cor
        )

        embed.add_field(
            name="🏆 VENCEDORES",
            value="\n".join(ganhos),
            inline=False
        )

        embed.add_field(
            name="💀 PERDEDORES",
            value="\n".join(perdas),
            inline=False
        )

        file = discord.File(imagem, filename=imagem)

        embed.set_image(
            url=f"attachment://{imagem}"
        )

        await canal.send(
            embed=embed,
            file=file
        )

    # ================= RANKING =================

    elif msg.content.startswith("!ranking"):

        if msg.channel.name != CANAL_COMANDOS_GERAL:
            return await msg.reply(
                f"❌ Use este comando no canal #{CANAL_COMANDOS_GERAL}"
            )

        data = carregar_ranking()

        user = msg.author

        player = data.get(
            str(user.id),
            {
                "wins": 0,
                "losses": 0,
                "streak": 0
            }
        )

        wins = player["wins"]
        losses = player["losses"]
        streak = player["streak"]

        total = wins + losses

        winrate = int((wins / total) * 100) if total > 0 else 0

        embed = discord.Embed(
            title=f"📊 Ranking de {user.display_name}",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="🏆 Vitórias",
            value=str(wins),
            inline=True
        )

        embed.add_field(
            name="💀 Derrotas",
            value=str(losses),
            inline=True
        )

        embed.add_field(
            name="📈 Winrate",
            value=f"{winrate}%",
            inline=True
        )

        embed.add_field(
            name="🔥 Sequência",
            value=f"{streak} wins",
            inline=False
        )

        await msg.channel.send(embed=embed)

    # ================= TOPWINS =================

    elif msg.content == "!topwins":

        data = carregar_ranking()

        ranking = sorted(
            data.items(),
            key=lambda x: x[1]["wins"],
            reverse=True
        )

        texto = ""

        for i, (uid, stats) in enumerate(ranking[:10]):

            texto += (
                f"`{i+1}.` <@{uid}> — 🏆 "
                f"{stats['wins']} vitórias\n"
            )

        embed = discord.Embed(
            title="🏆 Top 10 Jogadores com Mais Vitórias",
            description=texto,
            color=discord.Color.blue()
        )

        await msg.channel.send(embed=embed)

    # ================= TOPLOSS =================

    elif msg.content == "!toploss":

        data = carregar_ranking()

        ranking = sorted(
            data.items(),
            key=lambda x: x[1]["losses"],
            reverse=True
        )

        texto = ""

        for i, (uid, stats) in enumerate(ranking[:10]):

            texto += (
                f"`{i+1}.` <@{uid}> — 💀 "
                f"{stats['losses']} derrotas\n"
            )

        embed = discord.Embed(
            title="💀 Top 10 Jogadores com Mais Derrotas",
            description=texto,
            color=discord.Color.red()
        )

        await msg.channel.send(embed=embed)

    # ================= PERFIL =================

    elif msg.content.startswith("!perfil"):

        data = carregar_ranking()

        user = msg.mentions[0] if msg.mentions else msg.author

        stats = data.get(
            str(user.id),
            {
                "wins": 0,
                "losses": 0,
                "streak": 0
            }
        )

        wins = stats["wins"]
        losses = stats["losses"]
        streak = stats["streak"]

        total = wins + losses

        winrate = int((wins / total) * 100) if total > 0 else 0

        embed = discord.Embed(
            title=f"📊 Perfil de {user.display_name}",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="🏆 Vitórias",
            value=wins
        )

        embed.add_field(
            name="💀 Derrotas",
            value=losses
        )

        embed.add_field(
            name="📈 Winrate",
            value=f"{winrate}%"
        )

        embed.add_field(
            name="🔥 Sequência",
            value=f"{streak} wins",
            inline=False
        )

        await msg.channel.send(embed=embed)

    # ================= VS =================

    elif msg.content.startswith("!vs"):

        if not msg.mentions:
            return await msg.reply(
                "Use: !vs @jogador"
            )

        data = carregar_ranking()

        user1 = msg.author
        user2 = msg.mentions[0]

        p1 = data.get(
            str(user1.id),
            {"wins":0,"losses":0}
        )

        p2 = data.get(
            str(user2.id),
            {"wins":0,"losses":0}
        )

        embed = discord.Embed(
            title="⚔️ Comparação",
            color=discord.Color.purple()
        )

        embed.add_field(
            name=user1.display_name,
            value=f"🏆 {p1['wins']} | 💀 {p1['losses']}",
            inline=True
        )

        embed.add_field(
            name=user2.display_name,
            value=f"🏆 {p2['wins']} | 💀 {p2['losses']}",
            inline=True
        )

        await msg.channel.send(embed=embed)

    # ================= BOT =================

    elif msg.content == "!bot":

        canal_funcoes = get_channel(
            msg.guild,
            CANAL_COMANDOS_FUNCOES
        )

        canal_avisos = get_channel(
            msg.guild,
            "🚨│avisos-comandos"
        )

        embed = discord.Embed(
            title="🤖 Comandos Disponíveis",
            description=(
                f"Comandos liberados no canal "
                f"{msg.channel.mention}"
            ),
            color=discord.Color.blue()
        )

        comandos = [
            ("!ranking", "Mostra suas estatísticas"),
            ("!topwins", "Top 10 vitórias"),
            ("!toploss", "Top 10 derrotas"),
            ("!perfil @jogador", "Perfil de jogador"),
            ("!vs @jogador", "Comparação")
        ]

        for nome, desc in comandos:

            embed.add_field(
                name=nome,
                value=(
                    f"{desc}\n"
                    f"**(Todos Cargos Possuem Permissão Para Usar Esse Comando)**"
                ),
                inline=False
            )

        await canal_funcoes.send(embed=embed)

        aviso = discord.Embed(
            title="🚨 Aviso",
            description=(
                f"Caso algum membro utilize indevidamente qualquer comando mencionado "
                f"no canal {msg.channel.mention}, estará sujeito a advertência e poderá "
                f"ser banido do servidor pelo período de 1 dia.\n\n"
                f"**Observação:** Será tolerado o limite máximo de 5 advertências."
            ),
            color=discord.Color.red()
        )

        await canal_avisos.send(embed=aviso)

# ================= RUN =================

bot.run(TOKEN)