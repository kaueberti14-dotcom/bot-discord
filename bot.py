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

CANAL_COMANDOS = "comandos-🤖"
CANAL_PARTIDAS = "partidas-🔫"
CANAL_EQUIPE = "equipe🤝"
CANAL_RANKING = "ranking🏆"
CANAL_MAPAS = "mapas🗺️"
CANAL_REGRAS = "📜│regras-host"
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


def pegar_codigo(link):
    try:
        return parse_qs(urlparse(link).query).get("privateServerLinkCode", ["Não encontrado"])[0]
    except:
        return "Não encontrado"


def get_channel(guild, *nomes):
    for nome in nomes:
        canal = discord.utils.get(guild.text_channels, name=nome)
        if canal:
            return canal
    return None


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

    embed.set_author(name=f"Hoster Responsável: {nome_host}", icon_url=host.display_avatar.url if host else None)
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
    return discord.Embed(title="❌ PARTIDA CANCELADA!", description="A partida foi cancelada.", color=discord.Color.red())


def montar_times(jogadores):
    random.shuffle(jogadores)
    vermelho, azul, usados = [], [], set()

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

        if len(fila) >= limite:
            await iniciar_partida(interaction.guild)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.red)
    async def sair(self, interaction, button):
        if interaction.user.id not in fila:
            return await interaction.response.send_message("Você não está na partida.", ephemeral=True)

        fila.remove(interaction.user.id)

        file = discord.File("procurando.png", filename="procurando.png")
        embed = embed_procurando(interaction.guild)

        await interaction.response.edit_message(embed=embed, view=self, attachments=[file])

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
    embed = discord.Embed(
        title=titulo,
        description=texto,
        color=discord.Color.dark_red()
    )
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
        if msg.channel.name != CANAL_COMANDOS:
            return await msg.reply(f"❌ Use este comando no canal #{CANAL_COMANDOS}")

        if not tem_cargo(msg.author):
            return await msg.reply(embed=embed_erro("Você não possui permissão para criar uma partida!"))

        canal = get_channel(msg.guild, CANAL_PARTIDAS, "🔫│partidas")
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
        if not tem_cargo(msg.author):
            return await msg.reply(embed=embed_erro("Você não possui permissão para finalizar essa partida!"))

        canal = get_channel(msg.guild, CANAL_PARTIDAS, "🔫│partidas")
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

        ganhos, perdas = [], []

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
        if msg.channel.name != CANAL_RANKING:
            return await msg.reply(f"❌ Use este comando no canal #{CANAL_RANKING}")

        if not aceitou_regras(msg.author.id):
            return await msg.reply("❌ Você precisa aceitar as regras antes de usar o ranking.")

        data = carregar_ranking()
        user = msg.mentions[0] if msg.mentions else msg.author
        player = data.get(str(user.id), {"wins": 0, "losses": 0, "streak": 0})

        wins = player["wins"]
        losses = player["losses"]
        streak = player["streak"]
        total = wins + losses
        winrate = int((wins / total) * 100) if total > 0 else 0

        embed = discord.Embed(title=f"📊 Ranking de {user.display_name}", color=discord.Color.gold())
        embed.add_field(name="🏆 Vitórias", value=str(wins), inline=True)
        embed.add_field(name="💀 Derrotas", value=str(losses), inline=True)
        embed.add_field(name="📈 Winrate", value=f"{winrate}%", inline=True)
        embed.add_field(name="🔥 Sequência", value=f"{streak} wins", inline=False)

        await msg.channel.send(embed=embed)

    elif msg.content == "!mapas":
        canal_mapas = get_channel(msg.guild, "mapas🗺️")
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

    elif msg.content.lower() == "!host":
        if not tem_cargo(msg.author):
            return await msg.reply(embed=embed_erro("Você não possui permissão para enviar as regras."))

        canal_regras = get_channel(msg.guild, CANAL_REGRAS)
        if canal_regras is None:
            return await msg.reply("Não achei o canal 📜│regras-host.")

        canal_partidas = get_channel(msg.guild, "🔫│partidas", CANAL_PARTIDAS)
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
        await msg.reply("Regras enviadas com menu!")


bot.run(TOKEN)