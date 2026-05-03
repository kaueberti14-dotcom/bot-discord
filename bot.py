import discord
import random
import os
import asyncio
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


def pode_criar_fila(member):
    return tem_cargo(member, ["HOST", "Lider", "Sub-Lider"])


def pode_iniciar_partida(member):
    if member.id == criador_partida:
        return True
    return tem_cargo(member, ["Lider", "Sub-Lider"])


def pode_cancelar_fila(member):
    if member.id == criador_partida:
        return True
    return tem_cargo(member, ["Lider", "Sub-Lider"])


def pegar_codigo_roblox(link):
    try:
        query = parse_qs(urlparse(link).query)
        return query.get("privateServerLinkCode", ["Não encontrado"])[0]
    except:
        return "Não encontrado"


def texto_fila():
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
    metade = len(jogadores) // 2
    return jogadores[:metade], jogadores[metade:]


class PainelFila(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.green)
    async def entrar(self, interaction, button):
        if interaction.user.id in fila:
            await interaction.response.send_message("Você já está na partida!", ephemeral=True)
            return

        if len(fila) >= limite:
            await interaction.response.send_message("A partida já está cheia!", ephemeral=True)
            return

        fila.append(interaction.user.id)
        await interaction.response.edit_message(content=texto_fila(), view=self)

        if len(fila) >= limite:
            await iniciar_partida(interaction.guild)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.red)
    async def sair(self, interaction, button):
        if interaction.user.id not in fila:
            await interaction.response.send_message("Você não está nessa partida.", ephemeral=True)
            return

        fila.remove(interaction.user.id)
        await interaction.response.edit_message(content=texto_fila(), view=self)

    @discord.ui.button(label="Cancelar Partida", style=discord.ButtonStyle.gray)
    async def cancelar(self, interaction, button):
        global fila, criador_partida, link_partida

        if not pode_cancelar_fila(interaction.user):
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


class LinkServidorView(discord.ui.View):
    def __init__(self, link):
        super().__init__(timeout=300)
        self.add_item(discord.ui.Button(label="Entrar no servidor privado", url=link))


async def iniciar_partida(guild):
    global fila, criador_partida, link_partida, partida_ativa, painel_fila

    if partida_ativa:
        return

    if not link_partida:
        return

    if len(fila) < limite:
        return

    partida_ativa = True

    canal_partidas = discord.utils.get(guild.text_channels, name="partidas")
    if canal_partidas is None:
        partida_ativa = False
        return

    jogadores = fila[:limite]
    time_vermelho, time_azul = montar_times(jogadores)

    if painel_fila:
        await painel_fila.edit(content="🎮 **PARTIDA EM ANDAMENTO!**", view=None)

    codigo = pegar_codigo_roblox(link_partida)

    texto_times = "🎮 **PARTIDA EM ANDAMENTO!**\n\n"
    texto_times += "🟥 **TIME VERMELHO:**\n"
    texto_times += "\n".join([f"<@{j}>" for j in time_vermelho])
    texto_times += "\n\n🟦 **TIME AZUL:**\n"
    texto_times += "\n".join([f"<@{j}>" for j in time_azul])

    await canal_partidas.send(texto_times)

    for player_id in jogadores:
        user = await bot.fetch_user(player_id)
        try:
            await user.send(f"Partida começou!\nLink: {link_partida}")
        except:
            print(f"Erro ao enviar DM para {player_id}")

    msg_link = await canal_partidas.send(
        f"**Link do servidor privado:**\n{link_partida}\n\n"
        f"**Código para copiar:**\n```{codigo}```\n"
        f"⏳ Esse link ficará disponível por **5 minutos**.",
        view=LinkServidorView(link_partida)
    )

    for minutos in [4, 3, 2, 1]:
        await asyncio.sleep(60)
        await msg_link.edit(
            content=(
                f"**Link do servidor privado:**\n{link_partida}\n\n"
                f"**Código para copiar:**\n```{codigo}```\n"
                f"⏳ Esse link ficará disponível por **{minutos} minuto(s)**."
            ),
            view=LinkServidorView(link_partida)
        )

    await asyncio.sleep(60)
    await msg_link.edit(content="⏰ O tempo do link acabou.", view=None)

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
    global fila, limite, criador_partida, painel_fila, link_partida

    if message.author == bot.user:
        return

    if message.content.startswith("!criarfila"):
        if not pode_criar_fila(message.author):
            await message.reply(embed=embed_erro("Você não possui permissão para criar uma partida!"))
            return

        canal_partidas = discord.utils.get(message.guild.text_channels, name="partidas")

        if canal_partidas is None:
            await message.reply("Não achei o canal #partidas.")
            return

        partes = message.content.split(" ")

        if len(partes) < 2:
            await message.reply("Use assim: `!criarfila4 link_do_servidor_privado`")
            return

        comando = partes[0]
        link = partes[1]

        try:
            numero = int(comando.replace("!criarfila", ""))

            if numero not in [2, 4, 6, 8, 10]:
                await message.reply("Use apenas: `!criarfila2`, `!criarfila4`, `!criarfila6`, `!criarfila8` ou `!criarfila10`.")
                return
        except:
            await message.reply("Use assim: `!criarfila4 link_do_servidor_privado`")
            return

        fila = []
        limite = numero
        criador_partida = message.author.id
        link_partida = link

        duplas.clear()
        convites.clear()
        rivais.clear()

        painel_fila = await canal_partidas.send(texto_fila(), view=PainelFila())
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

    elif message.content.startswith("!start"):
        canal_comandos = discord.utils.get(message.guild.text_channels, name="comandos")

        if canal_comandos and message.channel.id != canal_comandos.id:
            await message.reply("Use esse comando no canal #comandos.")
            return

        if not pode_iniciar_partida(message.author):
            await message.reply(embed=embed_erro("Você não possui permissão para começar essa partida!"))
            return

        await iniciar_partida(message.guild)


bot.run(TOKEN)