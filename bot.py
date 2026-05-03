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


# ===== EMBED ERRO =====
def embed_erro(texto):
    return discord.Embed(
        title="❌ Erro",
        description=texto,
        color=discord.Color.red()
    )


# ===== PERMISSÕES =====
def tem_cargo(member, nomes):
    return any(role.name in nomes for role in member.roles)


def pode_criar(member):
    return tem_cargo(member, ["HOST", "Lider", "Sub-Lider"])


def pode_cancelar(member):
    if member.id == criador_partida:
        return True
    return tem_cargo(member, ["Lider", "Sub-Lider"])


# ===== ROBLOX =====
def pegar_codigo_roblox(link):
    try:
        query = parse_qs(urlparse(link).query)
        return query.get("privateServerLinkCode", ["Não encontrado"])[0]
    except:
        return "Não encontrado"


# ===== TEXTO =====
def texto_partida():
    jogadores = "\n".join([f"{i+1}. <@{j}>" for i, j in enumerate(fila)]) if fila else "Nenhum jogador."
    criador = f"<@{criador_partida}>" if criador_partida else "Nenhum"

    return (
        f"🎮 **PROCURANDO PARTIDA...**\n\n"
        f"👑 Criador: {criador}\n"
        f"👥 Jogadores: **{len(fila)}/{limite}**\n\n"
        f"{jogadores}"
    )


# ===== TIMES =====
def montar_times(jogadores):
    random.shuffle(jogadores)
    metade = len(jogadores) // 2
    return jogadores[:metade], jogadores[metade:]


# ===== BOTÕES =====
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
        await interaction.response.edit_message(content=texto_partida(), view=self)

        if len(fila) >= limite:
            await iniciar_partida(interaction.guild)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.red)
    async def sair(self, interaction, button):
        if interaction.user.id not in fila:
            return await interaction.response.send_message("Você não está na partida.", ephemeral=True)

        fila.remove(interaction.user.id)
        await interaction.response.edit_message(content=texto_partida(), view=self)

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.gray)
    async def cancelar(self, interaction, button):
        global fila, criador_partida, link_partida

        if not pode_cancelar(interaction.user):
            return await interaction.response.send_message(
                embed=embed_erro("Você não possui permissão para cancelar essa partida!"),
                ephemeral=True
            )

        fila.clear()
        criador_partida = None
        link_partida = None

        await interaction.response.edit_message(
            content="❌ **PARTIDA CANCELADA!**",
            view=None
        )


# ===== INICIAR PARTIDA =====
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

    host = guild.get_member(criador_partida)
    nome_host = host.display_name if host else "Host"

    id_partida = random.randint(100, 9999)
    codigo = pegar_codigo_roblox(link_partida)

    embed = discord.Embed(
        title="⚔️ PARTIDA EM ANDAMENTO",
        description=f"A partida **#{id_partida}** foi criada! Link na DM.",
        color=discord.Color.dark_red()
    )

    embed.set_author(
        name=f"Hoster Responsável: {nome_host}",
        icon_url=host.display_avatar.url if host else None
    )

    embed.add_field(
        name="🟦 TIME AZUL",
        value="\n".join([f"<@{j}>" for j in t2]),
        inline=True
    )

    embed.add_field(
        name="🟥 TIME VERMELHO",
        value="\n".join([f"<@{j}>" for j in t1]),
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

    # 🔥 SUA IMAGEM (BANNER)
    embed.set_image(
        url="https://assets.grok.com/users/146b3868-5f96-4065-839b-e505888ecbaa/generated/46a070ef-ee23-421d-acb7-a7b228078557/image.png"
    )

    embed.set_footer(text="AR2 Brasil [BR] • Partida iniciada")

    await canal.send(embed=embed)

    # 🔒 LINK SOMENTE NO PRIVADO
    for p in jogadores:
        user = await bot.fetch_user(p)
        try:
            await user.send(
                f"🎮 **Partida começou!**\n\n"
                f"Link:\n{link_partida}\n\n"
                f"Código:\n```{codigo}```"
            )
        except:
            pass

    fila.clear()
    criador_partida = None
    link_partida = None
    partida_ativa = False
    painel_fila = None


# ===== EVENTOS =====
@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")


@bot.event
async def on_message(message):
    global fila, limite, criador_partida, link_partida, painel_fila

    if message.author == bot.user:
        return

    if message.content.startswith("!criarfila"):
        if not pode_criar(message.author):
            return await message.reply(embed=embed_erro("Você não possui permissão para criar uma partida!"))

        canal = discord.utils.get(message.guild.text_channels, name="partidas")

        partes = message.content.split(" ")
        if len(partes) < 2:
            return await message.reply("Use: !criarfila4 link")

        comando = partes[0]
        link = partes[1]

        try:
            numero = int(comando.replace("!criarfila", ""))
        except:
            return

        fila.clear()
        limite = numero
        criador_partida = message.author.id
        link_partida = link

        painel_fila = await canal.send(texto_partida(), view=Painel())
        await message.reply("Partida criada!")


bot.run(TOKEN)