import discord
import random
import os
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
partida_ativa = False
painel_partida = None

convites = {}
duplas = {}
rivais = set()


def embed_erro(texto):
    return discord.Embed(
        title="❌ Erro",
        description=texto,
        color=discord.Color.red()
    )


def tem_cargo(member, nomes):
    return any(role.name in nomes for role in member.roles)


def pode_criar(member):
    return tem_cargo(member, ["HOST", "Lider", "Sub-Lider"])


def pode_cancelar(member):
    if member.id == criador_partida:
        return True
    return tem_cargo(member, ["Lider", "Sub-Lider"])


def pegar_codigo_roblox(link):
    try:
        query = parse_qs(urlparse(link).query)
        return query.get("privateServerLinkCode", ["Não encontrado"])[0]
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


class Painel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.green)
    async def entrar(self, interaction, button):
        if interaction.user.id in fila:
            return await interaction.response.send_message("Você já entrou!", ephemeral=True)

        if len(fila) >= limite:
            return await interaction.response.send_message("Partida cheia!", ephemeral=True)

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
            return await interaction.response.send_message("Você não está na partida.", ephemeral=True)

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
        global criador_partida, link_partida, partida_ativa, painel_partida

        if not pode_cancelar(interaction.user):
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
        partida_ativa = False
        painel_partida = None

        await interaction.response.edit_message(
            embed=embed_cancelada(),
            view=None,
            attachments=[]
        )


class ConviteView(discord.ui.View):
    def __init__(self, quem_chamou, convidado):
        super().__init__(timeout=60)
        self.quem_chamou = quem_chamou
        self.convidado = convidado

    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.green)
    async def aceitar(self, interaction, button):
        if interaction.user.id != self.convidado:
            return await interaction.response.send_message("Esse convite não é para você.", ephemeral=True)

        duplas[self.quem_chamou] = self.convidado
        duplas[self.convidado] = self.quem_chamou
        convites.pop(self.convidado, None)

        await interaction.response.edit_message(
            content=f"✅ <@{self.convidado}> aceitou! Vai cair no mesmo time de <@{self.quem_chamou}>.",
            view=None
        )

    @discord.ui.button(label="Recusar", style=discord.ButtonStyle.red)
    async def recusar(self, interaction, button):
        if interaction.user.id != self.convidado:
            return await interaction.response.send_message("Esse convite não é para você.", ephemeral=True)

        rivais.add(tuple(sorted((self.quem_chamou, self.convidado))))
        convites.pop(self.convidado, None)

        await interaction.response.edit_message(
            content=f"❌ <@{self.convidado}> recusou! Vai cair contra <@{self.quem_chamou}>.",
            view=None
        )


async def iniciar_partida(guild):
    global criador_partida, link_partida, partida_ativa, painel_partida

    if partida_ativa or not link_partida or len(fila) < limite:
        return

    partida_ativa = True

    jogadores = fila[:limite]
    vermelho, azul = montar_times(jogadores)

    host = guild.get_member(criador_partida)
    nome_host = host.display_name if host else "Host"
    id_partida = random.randint(100, 9999)
    codigo = pegar_codigo_roblox(link_partida)

    embed = discord.Embed(
        title="⚔️ PARTIDA EM ANDAMENTO",
        description=f"A partida **#{id_partida}** foi criada! Link enviado na DM.",
        color=discord.Color.dark_red()
    )

    embed.set_author(
        name=f"Hoster Responsável: {nome_host}",
        icon_url=host.display_avatar.url if host else None
    )

    embed.add_field(
        name="🟦 TIME AZUL",
        value="\n".join([f"<@{j}>" for j in azul]) if azul else "Vazio",
        inline=True
    )

    embed.add_field(
        name="🟥 TIME VERMELHO",
        value="\n".join([f"<@{j}>" for j in vermelho]) if vermelho else "Vazio",
        inline=True
    )

    embed.add_field(
        name="📋 INFO",
        value=(
            f"ID: `#{id_partida}`\n"
            f"MODO: `{limite//2}v{limite//2}`\n"
            f"HOST: `{nome_host}`"
        ),
        inline=False
    )

    embed.set_footer(text="AR2 Brasil [BR] • Partida iniciada")

    if painel_partida:
        await painel_partida.edit(embed=embed, view=None, attachments=[])

    for player_id in jogadores:
        user = await bot.fetch_user(player_id)
        try:
            await user.send(
                f"🎮 **Partida começou!**\n\n"
                f"**Link do servidor privado:**\n{link_partida}\n\n"
                f"**Código:**\n```{codigo}```"
            )
        except:
            print(f"Erro ao enviar DM para {player_id}")

    fila.clear()
    duplas.clear()
    convites.clear()
    rivais.clear()

    criador_partida = None
    link_partida = None
    partida_ativa = False
    painel_partida = None


@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")


@bot.event
async def on_message(message):
    global limite, criador_partida, link_partida, painel_partida

    if message.author == bot.user:
        return

    if message.content.startswith("!criarfila"):
        if not pode_criar(message.author):
            return await message.reply(
                embed=embed_erro("Você não possui permissão para criar uma partida!")
            )

        canal = discord.utils.get(message.guild.text_channels, name="partidas")

        if canal is None:
            return await message.reply("Não achei o canal #partidas.")

        partes = message.content.split(" ")

        if len(partes) < 2:
            return await message.reply("Use: `!criarfila4 link_do_servidor_privado`")

        comando = partes[0]
        link = partes[1]

        try:
            numero = int(comando.replace("!criarfila", ""))
        except:
            return await message.reply("Use: `!criarfila2`, `!criarfila4`, `!criarfila6`, `!criarfila8` ou `!criarfila10`.")

        if numero not in [2, 4, 6, 8, 10]:
            return await message.reply("Use apenas: `!criarfila2`, `!criarfila4`, `!criarfila6`, `!criarfila8` ou `!criarfila10`.")

        fila.clear()
        duplas.clear()
        convites.clear()
        rivais.clear()

        limite = numero
        criador_partida = message.author.id
        link_partida = link

        file = discord.File("procurando.png", filename="procurando.png")
        embed = embed_procurando(message.guild)

        painel_partida = await canal.send(
            embed=embed,
            view=Painel(),
            file=file
        )

        await message.reply("Partida criada!")

    elif message.content.startswith("!equipe"):
        mencionado = message.mentions.users.first()

        if not mencionado:
            return await message.reply("Use: `!equipe @jogador`")

        if mencionado.id == message.author.id:
            return await message.reply("Você não pode chamar você mesmo.")

        if message.author.id not in fila or mencionado.id not in fila:
            return await message.reply("Os dois jogadores precisam estar na partida.")

        convites[mencionado.id] = message.author.id

        await message.channel.send(
            f"{mencionado.mention}, {message.author.mention} quer cair no seu time.",
            view=ConviteView(message.author.id, mencionado.id)
        )


bot.run(TOKEN)