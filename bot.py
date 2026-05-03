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

convites = {}
duplas = {}
rivais = set()


# ================= RANKING =================

def carregar_ranking():
    try:
        with open("ranking.json", "r") as f:
            return json.load(f)
    except:
        return {}


def salvar_ranking(data):
    with open("ranking.json", "w") as f:
        json.dump(data, f, indent=4)


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
    player = get_player(data, uid)

    player["wins"] += 1
    player["streak"] += 1

    salvar_ranking(data)


def adicionar_derrota(uid):
    data = carregar_ranking()
    player = get_player(data, uid)

    player["losses"] += 1
    player["streak"] = 0

    salvar_ranking(data)


# ================= FUNÇÕES =================

def embed_erro(texto):
    return discord.Embed(
        title="❌ Erro",
        description=texto,
        color=discord.Color.red()
    )


def tem_cargo(member):
    return any(role.name in ["HOST", "Lider", "Sub-Lider"] for role in member.roles)


def pegar_codigo(link):
    try:
        return parse_qs(urlparse(link).query).get("privateServerLinkCode", ["Não encontrado"])[0]
    except:
        return "Não encontrado"


def lista_jogadores():
    if not fila:
        return "Nenhum jogador."

    return "\n".join([f"`{i+1}.` <@{j}>" for i, j in enumerate(fila)])


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
    embed.set_footer(text="AR2 Brasil [BR] • Procurando partida")

    return embed


def embed_cancelada():
    return discord.Embed(
        title="❌ PARTIDA CANCELADA!",
        description="A partida foi cancelada pelo responsável.",
        color=discord.Color.red()
    )


def montar_times(jogadores):
    random.shuffle(jogadores)

    vermelho = []
    azul = []
    usados = set()

    for jogador in jogadores:
        if jogador in usados:
            continue

        parceiro = duplas.get(jogador)

        if parceiro and parceiro in jogadores and parceiro not in usados:
            if len(vermelho) <= len(azul):
                vermelho.extend([jogador, parceiro])
            else:
                azul.extend([jogador, parceiro])

            usados.add(jogador)
            usados.add(parceiro)

        else:
            if len(vermelho) <= len(azul):
                vermelho.append(jogador)
            else:
                azul.append(jogador)

            usados.add(jogador)

    for a, b in rivais:
        if a in jogadores and b in jogadores:
            if a in vermelho and b in vermelho:
                vermelho.remove(b)
                azul.append(b)

            elif a in azul and b in azul:
                azul.remove(b)
                vermelho.append(b)

    return vermelho, azul


# ================= PAINEL PARTIDA =================

class Painel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.green)
    async def entrar(self, interaction, button):
        if interaction.user.id in fila:
            return await interaction.response.send_message(
                "Você já entrou na partida.",
                ephemeral=True
            )

        if len(fila) >= limite:
            return await interaction.response.send_message(
                "Partida cheia.",
                ephemeral=True
            )

        fila.append(interaction.user.id)

        file = discord.File("procurando.png", filename="procurando.png")
        embed = embed_procurando(interaction.guild)

        await interaction.response.edit_message(
            embed=embed,
            view=self,
            attachments=[file]
        )

        if len(fila) >= limite:
            await iniciar_partida(interaction.guild)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.red)
    async def sair(self, interaction, button):
        if interaction.user.id not in fila:
            return await interaction.response.send_message(
                "Você não está na partida.",
                ephemeral=True
            )

        fila.remove(interaction.user.id)

        file = discord.File("procurando.png", filename="procurando.png")
        embed = embed_procurando(interaction.guild)

        await interaction.response.edit_message(
            embed=embed,
            view=self,
            attachments=[file]
        )

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.gray)
    async def cancelar(self, interaction, button):
        global criador_partida, link_partida, painel_partida

        lider_ou_sub = any(role.name in ["Lider", "Sub-Lider"] for role in interaction.user.roles)

        if interaction.user.id != criador_partida and not lider_ou_sub:
            return await interaction.response.send_message(
                embed=embed_erro("Você não possui permissão para cancelar essa partida!"),
                ephemeral=True
            )

        fila.clear()
        duplas.clear()
        convites.clear()
        rivais.clear()

        criador_partida = None
        link_partida = None
        painel_partida = None

        await interaction.response.edit_message(
            embed=embed_cancelada(),
            view=None,
            attachments=[]
        )


# ================= SISTEMA DE EQUIPE =================

class ConviteView(discord.ui.View):
    def __init__(self, quem_chamou, convidado):
        super().__init__(timeout=60)
        self.quem_chamou = quem_chamou
        self.convidado = convidado

    @discord.ui.button(label="Aceitar Equipe", style=discord.ButtonStyle.green)
    async def aceitar(self, interaction, button):
        if interaction.user.id != self.convidado:
            return await interaction.response.send_message(
                "Esse convite não é para você.",
                ephemeral=True
            )

        duplas[self.quem_chamou] = self.convidado
        duplas[self.convidado] = self.quem_chamou
        convites.pop(self.convidado, None)

        await interaction.response.edit_message(
            content=f"✅ <@{self.convidado}> aceitou a equipe de <@{self.quem_chamou}>!",
            view=None
        )

    @discord.ui.button(label="Recusar Equipe", style=discord.ButtonStyle.red)
    async def recusar(self, interaction, button):
        if interaction.user.id != self.convidado:
            return await interaction.response.send_message(
                "Esse convite não é para você.",
                ephemeral=True
            )

        rivais.add(tuple(sorted((self.quem_chamou, self.convidado))))
        convites.pop(self.convidado, None)

        await interaction.response.edit_message(
            content=f"❌ <@{self.convidado}> recusou a equipe de <@{self.quem_chamou}>!",
            view=None
        )


# ================= INICIAR PARTIDA =================

async def iniciar_partida(guild):
    global ultimo_time_azul, ultimo_time_vermelho, ultimo_host, ultimo_modo
    global criador_partida, link_partida, painel_partida

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
        value="\n".join([f"<@{x}>" for x in azul]) if azul else "Vazio",
        inline=True
    )

    embed.add_field(
        name="🟥 TIME VERMELHO",
        value="\n".join([f"<@{x}>" for x in vermelho]) if vermelho else "Vazio",
        inline=True
    )

    embed.add_field(
        name="📋 INFO",
        value=(
            f"MODO: `{ultimo_modo}`\n"
            f"HOST: `{nome_host}`"
        ),
        inline=False
    )

    if painel_partida:
        await painel_partida.edit(
            embed=embed,
            view=None,
            attachments=[]
        )

    codigo = pegar_codigo(link_partida)

    for player_id in jogadores:
        user = await bot.fetch_user(player_id)

        try:
            await user.send(
                f"🎮 **Partida começou!**\n\n"
                f"**Link do servidor privado:**\n{link_partida}\n\n"
                f"**Código:**\n```{codigo}```"
            )
        except:
            pass

    fila.clear()


# ================= EVENTOS =================

@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")


@bot.event
async def on_message(msg):
    global limite, criador_partida, link_partida, painel_partida

    if msg.author.bot:
        return

    # criar partida
    if msg.content.startswith("!partida"):
        if not tem_cargo(msg.author):
            return await msg.reply(
                embed=embed_erro("Você não possui permissão para criar uma partida!")
            )

        canal = discord.utils.get(msg.guild.text_channels, name="partidas")

        if canal is None:
            return await msg.reply("Não achei o canal #partidas.")

        partes = msg.content.split()

        if len(partes) < 2:
            return await msg.reply("Use: `!partida4 link_do_servidor_privado`")

        comando = partes[0]
        link = partes[1]

        try:
            numero = int(comando.replace("!partida", ""))
        except:
            return await msg.reply(
                "Use: `!partida2`, `!partida4`, `!partida6`, `!partida8` ou `!partida10`."
            )

        if numero not in [2, 4, 6, 8, 10]:
            return await msg.reply(
                "Use apenas: `!partida2`, `!partida4`, `!partida6`, `!partida8` ou `!partida10`."
            )

        fila.clear()
        duplas.clear()
        convites.clear()
        rivais.clear()

        limite = numero
        criador_partida = msg.author.id
        link_partida = link

        file = discord.File("procurando.png", filename="procurando.png")
        embed = embed_procurando(msg.guild)

        painel_partida = await canal.send(
            embed=embed,
            view=Painel(),
            file=file
        )

        await msg.reply("Partida criada!")

    # sistema equipe
    elif msg.content.startswith("!equipe"):
        mencionado = msg.mentions[0] if msg.mentions else None

        if not mencionado:
            return await msg.reply("Use: `!equipe @jogador`")

        if mencionado.id == msg.author.id:
            return await msg.reply("Você não pode chamar você mesmo.")

        if msg.author.id not in fila or mencionado.id not in fila:
            return await msg.reply("Os dois jogadores precisam estar na partida.")

        canal_equipes = discord.utils.get(msg.guild.text_channels, name="equipes")

        if canal_equipes is None:
            return await msg.reply("Não achei o canal #equipes.")

        convites[mencionado.id] = msg.author.id

        await canal_equipes.send(
            f"{mencionado.mention}, {msg.author.mention} está chamando você para equipe.",
            view=ConviteView(msg.author.id, mencionado.id)
        )

        await msg.reply("Convite enviado no canal #equipes!")

    # vitória
    elif msg.content.lower().startswith("!vitória"):
        if not tem_cargo(msg.author):
            return await msg.reply(
                embed=embed_erro("Você não possui permissão para finalizar essa partida!")
            )

        canal = discord.utils.get(msg.guild.text_channels, name="partidas")

        if canal is None:
            return await msg.reply("Não achei o canal #partidas.")

        comando = msg.content.lower()

        if "azul" in comando:
            vencedores = ultimo_time_azul
            perdedores = ultimo_time_vermelho
            imagem = "vitoria_azul.png"
            cor = discord.Color.blue()
            nome_time = "🟦 TIME AZUL"

        elif "vermelho" in comando:
            vencedores = ultimo_time_vermelho
            perdedores = ultimo_time_azul
            imagem = "vitoria_vermelho.png"
            cor = discord.Color.red()
            nome_time = "🟥 TIME VERMELHO"

        else:
            return await msg.reply("Use: `!vitória azul` ou `!vitória vermelho`.")

        if not vencedores:
            return await msg.reply("Nenhuma partida registrada ainda.")

        for jogador in vencedores:
            adicionar_vitoria(jogador)

        for jogador in perdedores:
            adicionar_derrota(jogador)

        host = msg.guild.get_member(ultimo_host)
        nome_host = host.display_name if host else "Host"

        embed = discord.Embed(
            title="🏆 PARTIDA FINALIZADA",
            description=f"Vitória do {nome_time}!",
            color=cor
        )

        embed.set_author(
            name=f"Finalizada por: {msg.author.display_name}",
            icon_url=msg.author.display_avatar.url
        )

        embed.add_field(
            name="🏆 VENCEDORES",
            value="\n".join([f"<@{x}>" for x in vencedores]) if vencedores else "Vazio",
            inline=False
        )

        embed.add_field(
            name="💀 PERDEDORES",
            value="\n".join([f"<@{x}>" for x in perdedores]) if perdedores else "Vazio",
            inline=False
        )

        embed.add_field(
            name="📋 INFO",
            value=(
                f"HOST: `{nome_host}`\n"
                f"MODO: `{ultimo_modo}`"
            ),
            inline=False
        )

        file = discord.File(imagem, filename=imagem)
        embed.set_image(url=f"attachment://{imagem}")

        await canal.send(embed=embed, file=file)

    # ranking pessoal
    elif msg.content.startswith("!ranking"):
        data = carregar_ranking()

        user = msg.mentions[0] if msg.mentions else msg.author
        uid = str(user.id)

        player = data.get(uid, {
            "wins": 0,
            "losses": 0,
            "streak": 0
        })

        wins = player["wins"]
        losses = player["losses"]
        streak = player["streak"]

        total = wins + losses
        winrate = int((wins / total) * 100) if total > 0 else 0

        embed = discord.Embed(
            title=f"📊 Ranking de {user.display_name}",
            color=discord.Color.gold()
        )

        embed.add_field(name="🏆 Vitórias", value=str(wins), inline=True)
        embed.add_field(name="💀 Derrotas", value=str(losses), inline=True)
        embed.add_field(name="📈 Winrate", value=f"{winrate}%", inline=True)
        embed.add_field(name="🔥 Sequência", value=f"{streak} wins", inline=False)

        await msg.channel.send(embed=embed)


bot.run(TOKEN)