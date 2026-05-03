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

convites = {}
duplas = {}
rivais = set()
painel_fila = None


def embed_erro(texto):
    return discord.Embed(
        title="❌ Erro",
        description=texto,
        color=discord.Color.red()
    )


def tem_cargo(member, nomes):
    return any(role.name in nomes for role in member.roles)


def pode_criar_partida(member):
    return tem_cargo(member, ["HOST", "Lider", "Sub-Lider"])


def pode_cancelar_partida(member):
    if member.id == criador_partida:
        return True
    return tem_cargo(member, ["Lider", "Sub-Lider"])


def pegar_codigo_roblox(link):
    try:
        query = parse_qs(urlparse(link).query)
        return query.get("privateServerLinkCode", ["Não encontrado"])[0]
    except:
        return "Não encontrado"


def texto_partida():
    jogadores = "\n".join([f"{i+1}. <@{j}>" for i, j in enumerate(fila)]) if fila else "Nenhum jogador."
    criador = f"<@{criador_partida}>" if criador_partida else "Nenhum"

    return (
        f"🎮 **PROCURANDO PARTIDA...**\n\n"
        f"👑 Criador: {criador}\n"
        f"👥 Jogadores: **{len(fila)}/{limite}**\n\n"
        f"{jogadores}"
    )


def montar_times(jogadores):
    random.shuffle(jogadores)

    time_vermelho = []
    time_azul = []
    usados = set()

    for jogador in jogadores:
        if jogador in usados:
            continue

        parceiro = duplas.get(jogador)

        if parceiro and parceiro in jogadores and parceiro not in usados:
            if len(time_vermelho) <= len(time_azul):
                time_vermelho.extend([jogador, parceiro])
            else:
                time_azul.extend([jogador, parceiro])

            usados.add(jogador)
            usados.add(parceiro)
        else:
            if len(time_vermelho) <= len(time_azul):
                time_vermelho.append(jogador)
            else:
                time_azul.append(jogador)

            usados.add(jogador)

    for a, b in rivais:
        if a in jogadores and b in jogadores:
            if a in time_vermelho and b in time_vermelho:
                time_vermelho.remove(b)
                time_azul.append(b)
            elif a in time_azul and b in time_azul:
                time_azul.remove(b)
                time_vermelho.append(b)

    return time_vermelho, time_azul


class PainelPartida(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.green)
    async def entrar(self, interaction, button):
        if interaction.user.id in fila:
            await interaction.response.send_message("Você já entrou!", ephemeral=True)
            return

        if len(fila) >= limite:
            await interaction.response.send_message("Partida cheia!", ephemeral=True)
            return

        fila.append(interaction.user.id)
        await interaction.response.edit_message(content=texto_partida(), view=self)

        if len(fila) >= limite:
            await iniciar_partida(interaction.guild)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.red)
    async def sair(self, interaction, button):
        if interaction.user.id not in fila:
            await interaction.response.send_message("Você não está na partida.", ephemeral=True)
            return

        fila.remove(interaction.user.id)
        await interaction.response.edit_message(content=texto_partida(), view=self)

    @discord.ui.button(label="Cancelar Partida", style=discord.ButtonStyle.gray)
    async def cancelar(self, interaction, button):
        global fila, criador_partida, link_partida, painel_fila, partida_ativa

        if not pode_cancelar_partida(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro("Você não possui permissão para cancelar essa partida!"),
                ephemeral=True
            )
            return

        fila = []
        duplas.clear()
        convites.clear()
        rivais.clear()

        criador_partida = None
        link_partida = None
        painel_fila = None
        partida_ativa = False

        await interaction.response.edit_message(
            content="❌ **PARTIDA CANCELADA!**",
            view=None
        )


class ConviteView(discord.ui.View):
    def __init__(self, quem_chamou, convidado):
        super().__init__(timeout=60)
        self.quem_chamou = quem_chamou
        self.convidado = convidado

    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.green)
    async def aceitar(self, interaction, button):
        if interaction.user.id != self.convidado:
            await interaction.response.send_message("Esse convite não é para você.", ephemeral=True)
            return

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
            await interaction.response.send_message("Esse convite não é para você.", ephemeral=True)
            return

        rivais.add(tuple(sorted((self.quem_chamou, self.convidado))))
        convites.pop(self.convidado, None)

        await interaction.response.edit_message(
            content=f"❌ <@{self.convidado}> recusou! Vai cair no time adversário de <@{self.quem_chamou}>.",
            view=None
        )


async def iniciar_partida(guild):
    global fila, criador_partida, link_partida, partida_ativa, painel_fila

    if partida_ativa or not link_partida or len(fila) < limite:
        return

    partida_ativa = True

    canal_partidas = discord.utils.get(guild.text_channels, name="partidas")
    if canal_partidas is None:
        partida_ativa = False
        return

    jogadores = fila[:limite]
    time_vermelho, time_azul = montar_times(jogadores)
    codigo = pegar_codigo_roblox(link_partida)

    if painel_fila:
        await painel_fila.edit(content="🎮 **PARTIDA EM ANDAMENTO!**", view=None)

    host = guild.get_member(criador_partida)
    nome_host = host.display_name if host else "Host"

    embed = discord.Embed(
        title="⚔️ PARTIDA EM ANDAMENTO!",
        description="A partida foi criada! Link enviado na DM.",
        color=discord.Color.dark_red()
    )

    embed.set_author(name=f"Host Responsável: {nome_host}")

    embed.add_field(
        name="🟥 TIME VERMELHO",
        value="\n".join([f"<@{j}>" for j in time_vermelho]) if time_vermelho else "Vazio",
        inline=True
    )

    embed.add_field(
        name="🟦 TIME AZUL",
        value="\n".join([f"<@{j}>" for j in time_azul]) if time_azul else "Vazio",
        inline=True
    )

    embed.add_field(
        name="📋 INFO",
        value=(
            f"ID: `#{random.randint(100, 9999)}`\n"
            f"MODO: `{limite//2}v{limite//2}`\n"
            f"HOST: <@{criador_partida}>"
        ),
        inline=False
    )

    embed.set_image(
        url="https://assets.grok.com/users/146b3868-5f96-4065-839b-e505888ecbaa/generated/46a070ef-ee23-421d-acb7-a7b228078557/image.png"
    )

    embed.set_footer(text="AR2 Brasil [BR] • Partida iniciada")

    await canal_partidas.send(embed=embed)

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

    fila = []
    duplas.clear()
    convites.clear()
    rivais.clear()

    criador_partida = None
    link_partida = None
    partida_ativa = False
    painel_fila = None


@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")


@bot.event
async def on_message(message):
    global fila, limite, criador_partida, link_partida, painel_fila

    if message.author == bot.user:
        return

    if message.content.startswith("!criarfila"):
        if not pode_criar_partida(message.author):
            await message.reply(embed=embed_erro("Você não possui permissão para criar uma partida!"))
            return

        canal_partidas = discord.utils.get(message.guild.text_channels, name="partidas")

        if canal_partidas is None:
            await message.reply("Não achei o canal #partidas.")
            return

        partes = message.content.split(" ")

        if len(partes) < 2:
            await message.reply("Use: `!criarfila4 link_do_servidor_privado`")
            return

        comando = partes[0]
        link = partes[1]

        try:
            numero = int(comando.replace("!criarfila", ""))
        except:
            await message.reply("Use: `!criarfila2`, `!criarfila4`, `!criarfila6`, `!criarfila8` ou `!criarfila10`.")
            return

        if numero not in [2, 4, 6, 8, 10]:
            await message.reply("Use apenas: `!criarfila2`, `!criarfila4`, `!criarfila6`, `!criarfila8` ou `!criarfila10`.")
            return

        fila = []
        limite = numero
        criador_partida = message.author.id
        link_partida = link

        duplas.clear()
        convites.clear()
        rivais.clear()

        painel_fila = await canal_partidas.send(texto_partida(), view=PainelPartida())
        await message.reply(f"Partida criada com limite de **{limite} jogadores** no canal #partidas!")

    elif message.content.startswith("!equipe"):
        mencionado = message.mentions.users.first()

        if not mencionado:
            await message.reply("Use: `!equipe @jogador`")
            return

        if mencionado.id == message.author.id:
            await message.reply("Você não pode chamar você mesmo.")
            return

        if message.author.id not in fila or mencionado.id not in fila:
            await message.reply("Os dois jogadores precisam estar na partida.")
            return

        convites[mencionado.id] = message.author.id

        await message.channel.send(
            f"{mencionado.mention}, {message.author.mention} quer cair no seu time.",
            view=ConviteView(message.author.id, mencionado.id)
        )


bot.run(TOKEN)