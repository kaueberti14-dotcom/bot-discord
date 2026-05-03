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


def embed_erro(txt):
    return discord.Embed(title="❌ Erro", description=txt, color=discord.Color.red())


def tem_cargo(member):
    return any(r.name in ["HOST", "Lider", "Sub-Lider"] for r in member.roles)


def pegar_codigo(link):
    try:
        return parse_qs(urlparse(link).query).get("privateServerLinkCode", ["?"])[0]
    except:
        return "?"


def lista_jogadores():
    if not fila:
        return "Nenhum jogador."
    return "\n".join([f"`{i+1}.` <@{j}>" for i, j in enumerate(fila)])


def embed_procurando(guild):
    host = guild.get_member(criador_partida)
    nome = host.display_name if host else "Host"

    embed = discord.Embed(
        title="🔎 PROCURANDO PARTIDA...",
        description="Aguardando jogadores...",
        color=discord.Color.dark_red()
    )

    embed.set_author(name=f"Host: {nome}")
    embed.add_field(name="👥 Jogadores", value=lista_jogadores(), inline=False)
    embed.add_field(
        name="📋 Info",
        value=f"MODO: `{limite//2}v{limite//2}`\nJOGADORES: `{len(fila)}/{limite}`",
        inline=False
    )

    embed.set_image(url="attachment://procurando.png")
    return embed


def montar_times(jogadores):
    random.shuffle(jogadores)
    metade = len(jogadores) // 2
    return jogadores[:metade], jogadores[metade:]


class Painel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.green)
    async def entrar(self, i, b):
        if i.user.id in fila:
            return await i.response.send_message("Você já entrou.", ephemeral=True)

        if len(fila) >= limite:
            return await i.response.send_message("Partida cheia.", ephemeral=True)

        fila.append(i.user.id)

        file = discord.File("procurando.png", filename="procurando.png")
        embed = embed_procurando(i.guild)

        await i.response.edit_message(embed=embed, view=self, attachments=[file])

        if len(fila) >= limite:
            await iniciar_partida(i.guild)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.red)
    async def sair(self, i, b):
        if i.user.id not in fila:
            return await i.response.send_message("Você não está na partida.", ephemeral=True)

        fila.remove(i.user.id)

        file = discord.File("procurando.png", filename="procurando.png")
        embed = embed_procurando(i.guild)

        await i.response.edit_message(embed=embed, view=self, attachments=[file])

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.gray)
    async def cancelar(self, i, b):
        global criador_partida, link_partida, painel_partida

        lider_ou_sub = any(r.name in ["Lider", "Sub-Lider"] for r in i.user.roles)

        if i.user.id != criador_partida and not lider_ou_sub:
            return await i.response.send_message(
                embed=embed_erro("Você não possui permissão para cancelar essa partida!"),
                ephemeral=True
            )

        fila.clear()
        criador_partida = None
        link_partida = None
        painel_partida = None

        embed = discord.Embed(
            title="❌ PARTIDA CANCELADA!",
            description="A partida foi cancelada.",
            color=discord.Color.red()
        )

        await i.response.edit_message(embed=embed, view=None, attachments=[])


async def iniciar_partida(guild):
    global ultimo_time_azul, ultimo_time_vermelho, ultimo_host, ultimo_modo
    global criador_partida, link_partida, painel_partida

    jogadores = fila.copy()

    azul, vermelho = montar_times(jogadores)

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

    embed.set_author(name=f"Hoster Responsável: {nome_host}")

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
        value=f"MODO: `{ultimo_modo}`\nHOST: `{nome_host}`",
        inline=False
    )

    if painel_partida:
        await painel_partida.edit(embed=embed, view=None, attachments=[])

    codigo = pegar_codigo(link_partida)

    for p in jogadores:
        user = await bot.fetch_user(p)
        try:
            await user.send(
                f"🎮 **Partida começou!**\n\n"
                f"**Link do servidor privado:**\n{link_partida}\n\n"
                f"**Código:**\n```{codigo}```"
            )
        except:
            pass

    fila.clear()


@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")


@bot.event
async def on_message(msg):
    global limite, criador_partida, link_partida, painel_partida

    if msg.author.bot:
        return

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
            return await msg.reply("Use: `!partida2`, `!partida4`, `!partida6`, `!partida8` ou `!partida10`.")

        if numero not in [2, 4, 6, 8, 10]:
            return await msg.reply("Use apenas: `!partida2`, `!partida4`, `!partida6`, `!partida8` ou `!partida10`.")

        fila.clear()
        duplas.clear()
        convites.clear()
        rivais.clear()

        limite = numero
        criador_partida = msg.author.id
        link_partida = link

        file = discord.File("procurando.png", filename="procurando.png")
        embed = embed_procurando(msg.guild)

        painel_partida = await canal.send(embed=embed, view=Painel(), file=file)

        await msg.reply("Partida criada!")

    elif msg.content.lower().startswith("!vitória"):
        if not tem_cargo(msg.author):
            return await msg.reply(
                embed=embed_erro("Você não possui permissão para finalizar essa partida!")
            )

        canal = discord.utils.get(msg.guild.text_channels, name="partidas")

        if canal is None:
            return await msg.reply("Não achei o canal #partidas.")

        cmd = msg.content.lower()

        if "azul" in cmd:
            vencedores = ultimo_time_azul
            perdedores = ultimo_time_vermelho
            img = "vitoria_azul.png"
            cor = discord.Color.blue()
            time_nome = "🟦 TIME AZUL"

        elif "vermelho" in cmd:
            vencedores = ultimo_time_vermelho
            perdedores = ultimo_time_azul
            img = "vitoria_vermelho.png"
            cor = discord.Color.red()
            time_nome = "🟥 TIME VERMELHO"

        else:
            return await msg.reply("Use: `!vitória azul` ou `!vitória vermelho`.")

        if not vencedores:
            return await msg.reply("Nenhuma partida registrada ainda.")

        for v in vencedores:
            adicionar_vitoria(v)

        for p in perdedores:
            remover_vitoria(p)

        host = msg.guild.get_member(ultimo_host)
        nome_host = host.display_name if host else "Host"

        embed = discord.Embed(
            title="🏆 PARTIDA FINALIZADA",
            description=f"Vitória do {time_nome}!",
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
            value=f"HOST: `{nome_host}`\nMODO: `{ultimo_modo}`",
            inline=False
        )

        file = discord.File(img, filename=img)
        embed.set_image(url=f"attachment://{img}")

        await canal.send(embed=embed, file=file)

    elif msg.content == "!ranking":
        data = carregar_ranking()

        top = sorted(data.items(), key=lambda x: x[1], reverse=True)

        texto = ""
        for i, (uid, pts) in enumerate(top[:10], 1):
            texto += f"**{i}.** <@{uid}> — {pts} vitória(s)\n"

        embed = discord.Embed(
            title="🏆 Ranking",
            description=texto or "Ranking vazio.",
            color=discord.Color.gold()
        )

        await msg.channel.send(embed=embed)


bot.run(TOKEN)