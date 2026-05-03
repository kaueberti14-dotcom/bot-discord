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


async def iniciar_partida(guild):
    global fila, criador_partida, link_partida, partida_ativa, painel_fila

    if partida_ativa or not link_partida or len(fila) < limite:
        return

    partida_ativa = True

    canal = discord.utils.get(guild.text_channels, name="partidas")

    jogadores = fila[:limite]
    t1, t2 = montar_times(jogadores)

    if painel_fila:
        await painel_fila.edit(content="🎮 **PARTIDA EM ANDAMENTO!**", view=None)

    codigo = pegar_codigo_roblox(link_partida)

    texto = "🎮 **PARTIDA EM ANDAMENTO!**\n\n"
    texto += "🟥 **TIME VERMELHO:**\n" + "\n".join([f"<@{j}>" for j in t1])
    texto += "\n\n🟦 **TIME AZUL:**\n" + "\n".join([f"<@{j}>" for j in t2])

    await canal.send(texto)

    # 🔥 LINK SOMENTE NO PRIVADO
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
    global fila, limite, criador_partida, painel_fila, link_partida

    if message.author == bot.user:
        return

    if message.content.startswith("!criarfila"):
        if not pode_criar_fila(message.author):
            await message.reply(embed=embed_erro("Você não possui permissão para criar uma partida!"))
            return

        canal = discord.utils.get(message.guild.text_channels, name="partidas")

        partes = message.content.split(" ")
        if len(partes) < 2:
            await message.reply("Use: !criarfila4 link")
            return

        comando = partes[0]
        link = partes[1]

        try:
            numero = int(comando.replace("!criarfila", ""))
        except:
            return

        fila = []
        limite = numero
        criador_partida = message.author.id
        link_partida = link

        painel_fila = await canal.send(texto_fila(), view=PainelFila())
        await message.reply("Partida criada!")


bot.run(TOKEN)