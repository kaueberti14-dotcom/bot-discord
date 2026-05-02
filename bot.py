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
convites = {}
duplas = {}
rivais = set()
painel_fila = None


def pegar_codigo_roblox(link):
    try:
        query = parse_qs(urlparse(link).query)
        if "privateServerLinkCode" in query:
            return query["privateServerLinkCode"][0]
    except:
        pass
    return "Não consegui pegar o código automaticamente."


def texto_fila():
    jogadores = "\n".join([f"{i+1}. <@{j}>" for i, j in enumerate(fila)]) if fila else "Nenhum jogador na fila."

    return (
        f"**Fila da Partida**\n"
        f"Limite: **{limite} jogadores**\n"
        f"Jogadores: **{len(fila)}/{limite}**\n\n"
        f"{jogadores}"
    )


class PainelFila(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.green)
    async def entrar(self, interaction, button):
        if interaction.user.id in fila:
            await interaction.response.send_message("Você já está na fila!", ephemeral=True)
            return

        if len(fila) >= limite:
            await interaction.response.send_message("A fila já está cheia!", ephemeral=True)
            return

        fila.append(interaction.user.id)
        await interaction.response.edit_message(content=texto_fila(), view=self)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.red)
    async def sair(self, interaction, button):
        if interaction.user.id not in fila:
            await interaction.response.send_message("Você não está na fila.", ephemeral=True)
            return

        fila.remove(interaction.user.id)
        await interaction.response.edit_message(content=texto_fila(), view=self)


class LinkServidorView(discord.ui.View):
    def __init__(self, link):
        super().__init__(timeout=300)
        self.add_item(discord.ui.Button(label="Entrar no servidor privado", url=link))


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


def montar_times(jogadores):
    random.shuffle(jogadores)

    time1 = []
    time2 = []
    usados = set()

    for jogador in jogadores:
        if jogador in usados:
            continue

        parceiro = duplas.get(jogador)

        if parceiro and parceiro in jogadores and parceiro not in usados:
            if len(time1) <= len(time2):
                time1.extend([jogador, parceiro])
            else:
                time2.extend([jogador, parceiro])

            usados.add(jogador)
            usados.add(parceiro)
        else:
            if len(time1) <= len(time2):
                time1.append(jogador)
            else:
                time2.append(jogador)

            usados.add(jogador)

    for a, b in rivais:
        if a in jogadores and b in jogadores:
            if a in time1 and b in time1:
                time1.remove(b)
                time2.append(b)
            elif a in time2 and b in time2:
                time2.remove(b)
                time1.append(b)

    return time1, time2


@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")


@bot.event
async def on_message(message):
    global fila, limite, painel_fila

    if message.author == bot.user:
        return

    if message.content.startswith("!criarfila"):
        canal_partidas = discord.utils.get(message.guild.text_channels, name="partidas")

        if canal_partidas is None:
            await message.reply("Não achei o canal #partidas.")
            return

        try:
            numero = int(message.content.replace("!criarfila", ""))

            if numero not in [2, 4, 6, 8, 10]:
                await message.reply("Use: `!criarfila2`, `!criarfila4`, `!criarfila6`, `!criarfila8` ou `!criarfila10`.")
                return
        except:
            await message.reply("Use: `!criarfila2`, `!criarfila4`, `!criarfila6`, `!criarfila8` ou `!criarfila10`.")
            return

        fila = []
        limite = numero
        duplas.clear()
        convites.clear()
        rivais.clear()

        painel_fila = await canal_partidas.send(texto_fila(), view=PainelFila())
        await message.reply(f"Fila criada com limite de **{limite} jogadores** no canal #partidas!")

    elif message.content.startswith("!equipe"):
        mencionado = message.mentions.users.first()

        if not mencionado:
            await message.reply("Use: `!equipe @jogador`")
            return

        if mencionado.id == message.author.id:
            await message.reply("Você não pode chamar você mesmo.")
            return

        if message.author.id not in fila or mencionado.id not in fila:
            await message.reply("Os dois jogadores precisam estar na fila.")
            return

        convites[mencionado.id] = message.author.id

        await message.channel.send(
            f"{mencionado.mention}, {message.author.mention} quer cair no seu time.",
            view=ConviteView(message.author.id, mencionado.id)
        )

    elif message.content.startswith("!start"):
        canal_comandos = discord.utils.get(message.guild.text_channels, name="comandos")
        canal_partidas = discord.utils.get(message.guild.text_channels, name="partidas")

        if canal_comandos and message.channel.id != canal_comandos.id:
            await message.reply("Use esse comando no canal #comandos.")
            return

        if canal_partidas is None:
            await message.reply("Não achei o canal #partidas.")
            return

        args = message.content.split(" ")

        if len(args) < 2:
            await message.reply("Use: `!start link_do_servidor_privado`")
            return

        link = args[1]

        if len(fila) < limite:
            await message.reply(f"A fila ainda não encheu! ({len(fila)}/{limite})")
            return

        jogadores = fila[:limite]
        time1, time2 = montar_times(jogadores)
        codigo = pegar_codigo_roblox(link)

        if painel_fila:
            await painel_fila.edit(content="**PARTIDA EM ANDAMENTO!**", view=None)

        for player_id in jogadores:
            user = await bot.fetch_user(player_id)
            try:
                await user.send(f"Partida começou!\nLink: {link}")
            except:
                print(f"Erro ao enviar DM para {player_id}")

        texto_times = "**PARTIDA EM ANDAMENTO!**\n\n"
        texto_times += "**Time 1:**\n" + "\n".join([f"<@{j}>" for j in time1])
        texto_times += "\n\n**Time 2:**\n" + "\n".join([f"<@{j}>" for j in time2])

        await canal_partidas.send(texto_times)

        msg_link = await canal_partidas.send(
            f"**Link do servidor privado:**\n{link}\n\n"
            f"**Código para copiar:**\n```{codigo}```\n"
            f"⏳ Esse link ficará disponível por **5 minutos**.",
            view=LinkServidorView(link)
        )

        for minutos in [4, 3, 2, 1]:
            await asyncio.sleep(60)
            await msg_link.edit(
                content=(
                    f"**Link do servidor privado:**\n{link}\n\n"
                    f"**Código para copiar:**\n```{codigo}```\n"
                    f"⏳ Esse link ficará disponível por **{minutos} minuto(s)**."
                ),
                view=LinkServidorView(link)
            )

        await asyncio.sleep(60)
        await msg_link.edit(content="⏰ O tempo do link acabou.", view=None)

        fila = fila[limite:]
        duplas.clear()
        convites.clear()
        rivais.clear()


bot.run(TOKEN)