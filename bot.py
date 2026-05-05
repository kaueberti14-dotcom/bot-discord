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


def aceitou_regras(user_id):
    return str(user_id) in carregar_aceite()


def marcar_aceite(user_id):
    data = carregar_aceite()
    data[str(user_id)] = True
    salvar_aceite(data)


def get_player(data, uid):
    uid = str(uid)
    if uid not in data:
        data[uid] = {"wins": 0, "losses": 0, "streak": 0}
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


def embed_erro(texto):
    return discord.Embed(title="❌ Erro", description=texto, color=discord.Color.red())


def tem_cargo(member):
    return any(role.name in ["HOST", "Lider", "Sub-Lider"] for role in member.roles)


def eh_lider_ou_sub(member):
    return any(role.name in ["Lider", "Sub-Lider"] for role in member.roles)


def eh_host(member):
    return any(role.name == "HOST" for role in member.roles)


def get_channel(guild, *nomes):
    for nome in nomes:
        canal = discord.utils.get(guild.text_channels, name=nome)
        if canal:
            return canal
    return None


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

    embed.add_field(name="👥 JOGADORES", value=lista_jogadores(), inline=False)

    embed.add_field(
        name="📋 INFO",
        value=f"MODO: `{limite//2}v{limite//2}`\nJOGADORES: `{len(fila)}/{limite}`\nHOST: `{nome_host}`",
        inline=False
    )

    embed.set_image(url="attachment://procurando.png")
    embed.set_footer(text="AR2 Brasil [BR] • Procurando partida")
    return embed


def embed_cancelada():
    return discord.Embed(
        title="❌ PARTIDA CANCELADA!",
        description="A partida foi cancelada.",
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


class Painel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.green)
    async def entrar(self, interaction, button):
        if not aceitou_regras(interaction.user.id):
            return await interaction.response.send_message(
                "❌ Você precisa aceitar as regras antes de entrar em partidas.",
                ephemeral=True
            )

        if interaction.user.id in fila:
            return await interaction.response.send_message("Você já entrou na partida.", ephemeral=True)

        if len(fila) >= limite:
            return await interaction.response.send_message("Partida cheia.", ephemeral=True)

        fila.append(interaction.user.id)

        file = discord.File("procurando.png", filename="procurando.png")
        embed = embed_procurando(interaction.guild)

        await interaction.response.edit_message(embed=embed, view=self, attachments=[file])

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.red)
    async def sair(self, interaction, button):
        if interaction.user.id not in fila:
            return await interaction.response.send_message("Você não está na partida.", ephemeral=True)

        fila.remove(interaction.user.id)

        file = discord.File("procurando.png", filename="procurando.png")
        embed = embed_procurando(interaction.guild)

        await interaction.response.edit_message(embed=embed, view=self, attachments=[file])

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
        global criador_partida, link_partida, painel_partida

        if interaction.user.id != criador_partida and eh_host(interaction.user) and not eh_lider_ou_sub(interaction.user):
            return await interaction.response.send_message(
                embed=embed_erro("Você não possui permissão para cancelar partida de outros Host"),
                ephemeral=True
            )

        if interaction.user.id != criador_partida and not eh_lider_ou_sub(interaction.user):
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

        await interaction.response.edit_message(embed=embed_cancelada(), view=None, attachments=[])


class ConviteView(discord.ui.View):
    def __init__(self, quem_chamou, convidado):
        super().__init__(timeout=60)
        self.quem_chamou = quem_chamou
        self.convidado = convidado

    @discord.ui.button(label="Aceitar Equipe", style=discord.ButtonStyle.green)
    async def aceitar(self, interaction, button):
        if interaction.user.id != self.convidado:
            return await interaction.response.send_message("Esse convite não é para você.", ephemeral=True)

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
            return await interaction.response.send_message("Esse convite não é para você.", ephemeral=True)

        rivais.add(tuple(sorted((self.quem_chamou, self.convidado))))
        convites.pop(self.convidado, None)

        await interaction.response.edit_message(
            content=f"❌ <@{self.convidado}> recusou a equipe de <@{self.quem_chamou}>!",
            view=None
        )


class RegrasView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=None)
        self.pages = pages
        self.index = 0
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()

        if self.index > 0:
            self.add_item(BotaoVoltar(self))

        if self.index < len(self.pages) - 1:
            self.add_item(BotaoProximo(self))

        if self.index == len(self.pages) - 1:
            self.add_item(BotaoAceitar())

    async def update_message(self, interaction):
        self.update_buttons()
        embed = self.pages[self.index]
        file = discord.File("regras.png", filename="regras.png")

        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)


class BotaoProximo(discord.ui.Button):
    def __init__(self, view_ref):
        super().__init__(label="➡️ Próximo", style=discord.ButtonStyle.gray)
        self.view_ref = view_ref

    async def callback(self, interaction):
        self.view_ref.index += 1
        await self.view_ref.update_message(interaction)


class BotaoVoltar(discord.ui.Button):
    def __init__(self, view_ref):
        super().__init__(label="⬅️ Voltar", style=discord.ButtonStyle.gray)
        self.view_ref = view_ref

    async def callback(self, interaction):
        self.view_ref.index -= 1
        await self.view_ref.update_message(interaction)


class BotaoAceitar(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Aceitar Regras", style=discord.ButtonStyle.green)

    async def callback(self, interaction):
        if aceitou_regras(interaction.user.id):
            return await interaction.response.send_message("✅ Você já aceitou as regras.", ephemeral=True)

        marcar_aceite(interaction.user.id)

        cargo = discord.utils.get(interaction.guild.roles, name=CARGO_MEMBRO)

        if cargo:
            try:
                await interaction.user.add_roles(cargo)
            except:
                pass

        try:
            dono = await interaction.client.fetch_user(DONO_ID)
            await dono.send(f"{interaction.user.mention} aceitou as regras.")
        except:
            pass

        await interaction.response.send_message(
            "✅ Você aceitou as regras e recebeu o cargo Membro!",
            ephemeral=True
        )


def criar_pagina_regras(titulo, texto, pagina):
    embed = discord.Embed(title=titulo, description=texto, color=discord.Color.dark_red())
    embed.set_image(url="attachment://regras.png")
    embed.set_footer(text=f"Página {pagina}/7 • Sistema Ranqueado")
    return embed


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

    embed.set_author(name=f"Hoster Responsável: {nome_host}", icon_url=host.display_avatar.url if host else None)
    embed.add_field(name="🟦 TIME AZUL", value="\n".join([f"<@{x}>" for x in azul]) if azul else "Vazio", inline=True)
    embed.add_field(name="🟥 TIME VERMELHO", value="\n".join([f"<@{x}>" for x in vermelho]) if vermelho else "Vazio", inline=True)
    embed.add_field(name="📋 INFO", value=f"MODO: `{ultimo_modo}`\nHOST: `{nome_host}`", inline=False)

    file = discord.File("partida.png", filename="partida.png")
    embed.set_image(url="attachment://partida.png")
    embed.set_footer(text="AR2 Brasil [BR] • Partida iniciada")

    if painel_partida:
        await painel_partida.edit(embed=embed, view=None, attachments=[file])

    for player_id in jogadores:
        user = await bot.fetch_user(player_id)

        try:
            embed_dm = discord.Embed(
                title="🎮 Só falta você para começar!",
                description=f"[Clique aqui para entrar no servidor privado]({link_partida})",
                color=discord.Color.dark_red()
            )
            embed_dm.set_footer(text="Boa partida!")
            await user.send(embed=embed_dm)
        except:
            pass

    fila.clear()


@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")


@bot.event
async def on_member_join(member):
    cargo = discord.utils.get(member.guild.roles, name=CARGO_MEMBRO)
    if cargo:
        try:
            await member.add_roles(cargo)
        except:
            pass


@bot.event
async def on_member_remove(member):
    data = carregar_aceite()
    if str(member.id) in data:
        del data[str(member.id)]
        salvar_aceite(data)


@bot.event
async def on_message(msg):
    global limite, criador_partida, link_partida, painel_partida

    if msg.author.bot:
        return

    if msg.content.startswith("!partida"):
        if msg.channel.name != CANAL_COMANDOS_PARTIDAS:
            return await msg.reply(f"❌ Use este comando no canal #{CANAL_COMANDOS_PARTIDAS}")

        if not tem_cargo(msg.author):
            return await msg.reply(embed=embed_erro("Você não possui permissão para criar uma partida!"))

        canal = get_channel(msg.guild, CANAL_PARTIDAS)
        if canal is None:
            return await msg.reply("Não achei o canal de partidas.")

        partes = msg.content.split()

        if len(partes) < 2:
            return await msg.reply("Use: `!partida4 link_do_servidor_privado`")

        try:
            numero = int(partes[0].replace("!partida", ""))
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
        link_partida = partes[1]

        file = discord.File("procurando.png", filename="procurando.png")
        embed = embed_procurando(msg.guild)

        painel_partida = await canal.send(embed=embed, view=Painel(), file=file)

        await msg.reply("Partida criada!")

    elif msg.content.startswith("!equipe"):
        if msg.channel.name != CANAL_EQUIPE:
            return await msg.reply(f"❌ Use este comando no canal #{CANAL_EQUIPE}")

        mencionado = msg.mentions[0] if msg.mentions else None

        if not mencionado:
            return await msg.reply("Use: `!equipe @jogador`")

        if mencionado.id == msg.author.id:
            return await msg.reply("Você não pode chamar você mesmo.")

        if msg.author.id not in fila or mencionado.id not in fila:
            return await msg.reply("Os dois jogadores precisam estar na partida.")

        canal_equipes = get_channel(msg.guild, CANAL_EQUIPE)

        convites[mencionado.id] = msg.author.id

        await canal_equipes.send(
            f"{mencionado.mention}, {msg.author.mention} está chamando você para equipe.",
            view=ConviteView(msg.author.id, mencionado.id)
        )

        await msg.reply("Convite enviado!")

    elif msg.content.lower().startswith("!vitória"):
        if msg.channel.name != CANAL_COMANDOS_PARTIDAS:
            return await msg.reply(f"❌ Use este comando no canal #{CANAL_COMANDOS_PARTIDAS}")

        if not tem_cargo(msg.author):
            return await msg.reply(embed=embed_erro("Você não possui permissão para finalizar essa partida!"))

        canal = get_channel(msg.guild, CANAL_PARTIDAS)
        if canal is None:
            return await msg.reply("Não achei o canal de partidas.")

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

        ganhos = []
        perdas = []

        for jogador in vencedores:
            adicionar_vitoria(jogador)
            ganhos.append(f"<@{jogador}> ➜ +1 Vitória 🏆")

        for jogador in perdedores:
            adicionar_derrota(jogador)
            perdas.append(f"<@{jogador}> ➜ +1 Derrota 💀")

        host = msg.guild.get_member(ultimo_host)
        nome_host = host.display_name if host else "Host"

        embed = discord.Embed(title="🏆 PARTIDA FINALIZADA", description=f"Vitória do {nome_time}!", color=cor)
        embed.set_author(name=f"Finalizada por: {msg.author.display_name}", icon_url=msg.author.display_avatar.url)
        embed.add_field(name="🏆 VENCEDORES", value="\n".join(ganhos), inline=False)
        embed.add_field(name="💀 PERDEDORES", value="\n".join(perdas), inline=False)
        embed.add_field(name="📋 INFO", value=f"HOST: `{nome_host}`\nMODO: `{ultimo_modo}`", inline=False)

        file = discord.File(imagem, filename=imagem)
        embed.set_image(url=f"attachment://{imagem}")

        await canal.send(embed=embed, file=file)

    elif msg.content.startswith("!ranking"):
        if msg.channel.name != CANAL_COMANDOS_GERAL:
            return await msg.reply(f"❌ Use este comando no canal #{CANAL_COMANDOS_GERAL}")

        if not aceitou_regras(msg.author.id):
            return await msg.reply("❌ Você precisa aceitar as regras antes de usar o ranking.")

        data = carregar_ranking()
        user = msg.mentions[0] if msg.mentions else msg.author
        player = data.get(str(user.id), {"wins": 0, "losses": 0, "streak": 0})

        wins = player.get("wins", 0)
        losses = player.get("losses", 0)
        streak = player.get("streak", 0)

        total = wins + losses
        winrate = int((wins / total) * 100) if total > 0 else 0

        embed = discord.Embed(title=f"📊 Ranking de {user.display_name}", color=discord.Color.gold())
        embed.add_field(name="🏆 Vitórias", value=str(wins), inline=True)
        embed.add_field(name="💀 Derrotas", value=str(losses), inline=True)
        embed.add_field(name="📈 Winrate", value=f"{winrate}%", inline=True)
        embed.add_field(name="🔥 Sequência", value=f"{streak} wins", inline=False)

        await msg.channel.send(embed=embed)

    elif msg.content == "!topwins":
        if msg.channel.name != CANAL_COMANDOS_GERAL:
            return await msg.reply(f"❌ Use este comando no canal #{CANAL_COMANDOS_GERAL}")

        data = carregar_ranking()
        ranking = sorted(data.items(), key=lambda x: x[1].get("wins", 0), reverse=True)

        texto = ""
        medalhas = ["🥇", "🥈", "🥉"]

        for i, (uid, stats) in enumerate(ranking[:10]):
            pos = medalhas[i] if i < 3 else f"`{i+1}.`"
            texto += f"{pos} <@{uid}> — 🏆 {stats.get('wins', 0)} vitórias\n"

        embed = discord.Embed(
            title="🏆 Top 10 Jogadores com Mais Vitórias",
            description=texto or "Sem dados.",
            color=discord.Color.blue()
        )

        await msg.channel.send(embed=embed)

    elif msg.content == "!toploss":
        if msg.channel.name != CANAL_COMANDOS_GERAL:
            return await msg.reply(f"❌ Use este comando no canal #{CANAL_COMANDOS_GERAL}")

        data = carregar_ranking()
        ranking = sorted(data.items(), key=lambda x: x[1].get("losses", 0), reverse=True)

        texto = ""
        medalhas = ["🥇", "🥈", "🥉"]

        for i, (uid, stats) in enumerate(ranking[:10]):
            pos = medalhas[i] if i < 3 else f"`{i+1}.`"
            texto += f"{pos} <@{uid}> — 💀 {stats.get('losses', 0)} derrotas\n"

        embed = discord.Embed(
            title="💀 Top 10 Jogadores com Mais Derrotas",
            description=texto or "Sem dados.",
            color=discord.Color.red()
        )

        await msg.channel.send(embed=embed)

    elif msg.content.startswith("!perfil"):
        if msg.channel.name != CANAL_COMANDOS_GERAL:
            return await msg.reply(f"❌ Use este comando no canal #{CANAL_COMANDOS_GERAL}")

        data = carregar_ranking()
        user = msg.mentions[0] if msg.mentions else msg.author
        player = data.get(str(user.id), {"wins": 0, "losses": 0, "streak": 0})

        wins = player.get("wins", 0)
        losses = player.get("losses", 0)
        streak = player.get("streak", 0)
        total = wins + losses
        winrate = int((wins / total) * 100) if total > 0 else 0

        embed = discord.Embed(title=f"📊 Perfil de {user.display_name}", color=discord.Color.blue())
        embed.add_field(name="🏆 Vitórias", value=str(wins), inline=True)
        embed.add_field(name="💀 Derrotas", value=str(losses), inline=True)
        embed.add_field(name="📈 Winrate", value=f"{winrate}%", inline=True)
        embed.add_field(name="🔥 Sequência", value=f"{streak} wins", inline=False)

        await msg.channel.send(embed=embed)

    elif msg.content.startswith("!vs"):
        if msg.channel.name != CANAL_COMANDOS_GERAL:
            return await msg.reply(f"❌ Use este comando no canal #{CANAL_COMANDOS_GERAL}")

        if not msg.mentions:
            return await msg.reply("Use: `!vs @jogador`")

        data = carregar_ranking()
        user1 = msg.author
        user2 = msg.mentions[0]

        p1 = data.get(str(user1.id), {"wins": 0, "losses": 0, "streak": 0})
        p2 = data.get(str(user2.id), {"wins": 0, "losses": 0, "streak": 0})

        embed = discord.Embed(title="⚔️ Comparação", color=discord.Color.purple())

        embed.add_field(
            name=user1.display_name,
            value=f"🏆 Vitórias: `{p1.get('wins', 0)}`\n💀 Derrotas: `{p1.get('losses', 0)}`\n🔥 Sequência: `{p1.get('streak', 0)}`",
            inline=True
        )

        embed.add_field(
            name=user2.display_name,
            value=f"🏆 Vitórias: `{p2.get('wins', 0)}`\n💀 Derrotas: `{p2.get('losses', 0)}`\n🔥 Sequência: `{p2.get('streak', 0)}`",
            inline=True
        )

        await msg.channel.send(embed=embed)

    elif msg.content == "!bot":
        if msg.channel.name != CANAL_COMANDOS_GERAL:
            return await msg.reply(f"❌ Use este comando no canal #{CANAL_COMANDOS_GERAL}")

        canal_comandos = get_channel(msg.guild, CANAL_COMANDOS_GERAL)
        canal_funcoes = get_channel(msg.guild, CANAL_COMANDOS_FUNCOES)
        canal_avisos = get_channel(msg.guild, "🚨│avisos-comandos")

        if canal_funcoes is None:
            return await msg.reply("Não achei o canal ⚙🤖│comandos-funções.")

        if canal_avisos is None:
            return await msg.reply("Não achei o canal 🚨│avisos-comandos.")

        comandos_mention = canal_comandos.mention if canal_comandos else "#🤖│comandos"

        embed = discord.Embed(
            title="🤖 Comandos Disponíveis",
            description=f"Comandos liberados no canal {comandos_mention}",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="`!ranking`",
            value="Mostra suas estatísticas.\n**(Todos Cargos Possuem Permissão Para Usar Esse Comando)**",
            inline=False
        )

        embed.add_field(
            name="`!topwins`",
            value="Top 10 vitórias.\n**(Todos Cargos Possuem Permissão Para Usar Esse Comando)**",
            inline=False
        )

        embed.add_field(
            name="`!toploss`",
            value="Top 10 derrotas.\n**(Todos Cargos Possuem Permissão Para Usar Esse Comando)**",
            inline=False
        )

        embed.add_field(
            name="`!perfil @jogador`",
            value="Perfil de jogador.\n**(Todos Cargos Possuem Permissão Para Usar Esse Comando)**",
            inline=False
        )

        embed.add_field(
            name="`!vs @jogador`",
            value="Comparação.\n**(Todos Cargos Possuem Permissão Para Usar Esse Comando)**",
            inline=False
        )

        await canal_funcoes.send(embed=embed)

        aviso = discord.Embed(
            title="🚨 Aviso Sobre Uso Indevido De Comandos",
            description=(
                f"Caso algum membro utilize indevidamente qualquer comando mencionado no canal {comandos_mention}, "
                "estará sujeito a advertência e poderá ser banido do servidor pelo período de **1 dia**.\n\n"
                "**Observação:** Será tolerado o limite máximo de **5 advertências**."
            ),
            color=discord.Color.red()
        )

        await canal_avisos.send(embed=aviso)
        await msg.reply("Mensagem de comandos e aviso enviados!")

    elif msg.content == "!mapas":
        canal_mapas = get_channel(msg.guild, CANAL_MAPAS)

        if canal_mapas is None:
            return await msg.reply("Não achei o canal #mapas🗺️.")

        embed_titulo = discord.Embed(
            title="🗺️ Rotação De Mapas",
            description="Confira os mapas disponíveis para as partidas.",
            color=discord.Color.dark_red()
        )

        await canal_mapas.send(embed=embed_titulo)

        mapas = [
            ("Airport Terminal", "mapa1.png"),
            ("Dueling Oil Rigs", "mapa2.png"),
            ("Huntington", "mapa3.png"),
            ("Lockport", "mapa4.png"),
            ("University", "mapa5.png"),
        ]

        for nome, arquivo in mapas:
            file = discord.File(arquivo, filename=arquivo)

            embed = discord.Embed(title=f"🗺️ {nome}", color=discord.Color.dark_red())
            embed.set_image(url=f"attachment://{arquivo}")
            embed.set_footer(text="AR2 Brasil [BR]")

            await canal_mapas.send(embed=embed, file=file)

        await msg.reply("Rotação enviada no canal #mapas🗺️!")

    elif msg.content.lower() == "!regras":
        if msg.channel.name != CANAL_COMANDOS_GERAL:
            return await msg.reply(f"❌ Use este comando no canal #{CANAL_COMANDOS_GERAL}")

        canal = get_channel(msg.guild, CANAL_REGRAS)

        if canal is None:
            return await msg.reply("Não achei o canal 📋│regras.")

        embed = discord.Embed(
            title="📋 Regras do Servidor",
            description="Leia atentamente todas as regras abaixo. O descumprimento poderá resultar em punições.",
            color=discord.Color.dark_red()
        )

        embed.add_field(name="👥│Respeito aos Membros do Servidor", value="Todos os membros devem ser tratados com respeito. Não serão toleradas ofensas, bullying ou qualquer forma de discriminação.", inline=False)
        embed.add_field(name="🚫│Preconceito", value="Atitudes como racismo, xenofobia ou qualquer outro tipo de preconceito resultarão em banimento imediato.", inline=False)
        embed.add_field(name="📛│Proibição de Spam", value="É vedado o envio repetitivo e intencional de mensagens, caracterizando spam.", inline=False)
        embed.add_field(name="🔞│Conteúdo Impróprio", value="Não é permitido compartilhar conteúdos inadequados, como pornografia ou materiais ofensivos.", inline=False)
        embed.add_field(name="📜│Diretrizes do Discord", value="Todos os membros devem seguir as diretrizes oficiais do Discord, além das regras deste servidor.", inline=False)
        embed.add_field(name="⚖️│Conduta em Relação a Outros Membros", value="Não é permitido desmerecer ou ridicularizar outros membros, especialmente por desempenho em partidas.", inline=False)
        embed.add_field(name="⚠️│Observação", value="Serão toleradas, no máximo, três ocorrências de reclamações relacionadas a ofensas direcionadas à habilidade de outros membros. Após isso, o membro será expulso do servidor.", inline=False)

        embed.set_footer(text="Servidor Oficial • Regras Gerais")

        await canal.send(embed=embed)
        await msg.reply("Regras enviadas no canal 📋│regras!")

    elif msg.content.lower() == "!host":
        if msg.channel.name != CANAL_COMANDOS_GERAL:
            return await msg.reply(f"❌ Use este comando no canal #{CANAL_COMANDOS_GERAL}")

        if not tem_cargo(msg.author):
            return await msg.reply(embed=embed_erro("Você não possui permissão para enviar as regras."))

        canal_regras = get_channel(msg.guild, CANAL_REGRAS_HOST)

        if canal_regras is None:
            return await msg.reply("Não achei o canal 📜│regras-host.")

        canal_partidas = get_channel(msg.guild, CANAL_PARTIDAS)
        canal_reconexao = get_channel(msg.guild, "🌐│reconexão")
        canal_ticket = get_channel(msg.guild, "🎟️│ticket")

        partidas = canal_partidas.mention if canal_partidas else "#partidas"
        reconexao = canal_reconexao.mention if canal_reconexao else "#reconexão"
        ticket = canal_ticket.mention if canal_ticket else "#ticket"

        pages = [
            criar_pagina_regras(
                "📜 Regras do Sistema Ranqueado",
                "Estas diretrizes foram estabelecidas para garantir um ambiente competitivo, justo e organizado.\nO descumprimento de qualquer regra poderá resultar em penalidades.",
                1
            ),
            criar_pagina_regras(
                "🎮 1. Modo de Jogo",
                f"As partidas seguem o formato PvP em equipes (2v2, 3v3, 4v4 ou 5v5), no canal {partidas}.\nCada rodada terá duração de 3 ou 5 minutos.\nA vitória será concedida à equipe que alcançar primeiro 5 vitórias.\nAs regras do modo são fixas e não podem ser alteradas.",
                2
            ),
            criar_pagina_regras(
                "📴 2. AFK, Abandono e Desconexão",
                f"Não é permitido permanecer AFK de forma intencional ou abandonar a partida.\nEm caso de desconexão, avise no canal {reconexao} e retorne rapidamente.\n\nPunições: derrota automática, perda de ranking/vitórias, suspensão temporária e banimento em casos graves.",
                3
            ),
            criar_pagina_regras(
                "👾 3. Uso de Cheats",
                f"É proibido o uso de ferramentas de terceiros que ofereçam vantagem indevida: Aimbot, Wallhack, Speed Hack, ESP, injeções externas ou modificações não autorizadas.\n\nCaso haja suspeita, informe um superior pelo canal {ticket}.",
                4
            ),
            criar_pagina_regras(
                "🛠️ 4. Macros, Scripts e Automação",
                "O uso de macros, scripts ou alterações que proporcionem vantagem injusta não é permitido.\nExemplos: no-recoil, automação de ações ou softwares auxiliares de input.\n\nPunições: suspensão temporária, reset de ranking/vitórias e banimento dependendo da gravidade.",
                5
            ),
            criar_pagina_regras(
                "🚨 5. Denúncias Falsas",
                f"As denúncias devem ser feitas após a partida no canal {ticket}, com motivo “Denúncias”, e serão analisadas pela liderança.\n\nDenúncias falsas ou de má-fé resultarão em punições, podendo levar ao banimento.",
                6
            ),
            criar_pagina_regras(
                "👥 6. Contas Alternativas",
                "É proibido criar ou usar contas alternativas para evitar punições, manipular ranking ou obter vantagens indevidas.\n\nPunições: banimento de todas as contas envolvidas, bloqueio permanente no sistema ranqueado e possível banimento por IP.",
                7
            ),
        ]

        file = discord.File("regras.png", filename="regras.png")

        await canal_regras.send(embed=pages[0], file=file, view=RegrasView(pages))

        embed_armas = discord.Embed(
            title="🚫│Armas Proibidas nas Partidas",
            description="**(O uso dessas armas implicará em punições)**",
            color=discord.Color.dark_red()
        )

        await canal_regras.send(embed=embed_armas)

        armas = [
            ("M1918 Tankgewehr", "arma1.png"),
            ("Santa's Pig", "arma2.png"),
            ("Trooper M1919A6", "arma3.png"),
        ]

        for nome, arquivo in armas:
            file_arma = discord.File(arquivo, filename=arquivo)

            embed = discord.Embed(title=f"🚫 {nome}", color=discord.Color.dark_red())
            embed.set_image(url=f"attachment://{arquivo}")
            embed.set_footer(text="Arma proibida nas partidas ranqueadas")

            await canal_regras.send(embed=embed, file=file_arma)

        await msg.reply("Regras e armas proibidas enviadas!")


bot.run(TOKEN)