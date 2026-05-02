import discord
import random
import os

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


def texto_fila():
    if fila:
        jogadores = "\n".join([f"{i+1}. <@{j}>" for i, j in enumerate(fila)])
    else:
        jogadores = "Nenhum jogador na fila."

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
    async def entrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in fila:
            await interaction.response.send_message("Você já está na fila!", ephemeral=True)
            return

        if len(fila) >= limite:
            await interaction.response.send_message("A fila já está cheia!", ephemeral=True)
            return

        fila.append(interaction.user.id)
        await interaction.response.edit_message(content=texto_fila(), view=self)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.red)
    async def sair(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in fila:
            await interaction.response.send_message("Você não está na fila.", ephemeral=True)
            return

        fila.remove(interaction.user.id)
        await interaction.response.edit_message(content=texto_fila(), view=self)


class ConviteView(discord.ui.View):
    def __init__(self, quem_chamou, convidado):
        super().__init__(timeout=60)
        self.quem_chamou = quem_chamou
        self.convidado = convidado

    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.green)
    async def aceitar(self, interaction: discord.Interaction, button: discord.ui.Button):
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
    async def recusar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.convidado:
            await interaction.response.send_message("Esse convite não é para você.", ephemeral=True)
            return

        rivais.add(tuple(sorted((self.quem_chamou, self.convidado))))
        convites.pop(self.convidado, None)

        await interaction.response.edit_message(
            content=f"❌ <@{self.convidado}> recusou! Vai cair no time adversário de <@{self.quem_chamou}>.",
            view=None
        )


class LimiteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    async def definir_limite(self, interaction, valor):
        global limite, fila

        limite = valor
        fila = []

        await interaction.response.edit_message(
            content=f"Limite definido para **{limite} jogadores**.\nA fila foi resetada.",
            view=None
        )

    @discord.ui.button(label="2", style=discord.ButtonStyle.blurple)
    async def limite_2(self, interaction, button):
        await self.definir_limite(interaction, 2)

    @discord.ui.button(label="4", style=discord.ButtonStyle.blurple)
    async def limite_4(self, interaction, button):
        await self.definir_limite(interaction, 4)

    @discord.ui.button(label="6", style=discord.ButtonStyle.blurple)
    async def limite_6(self, interaction, button):
        await self.definir_limite(interaction, 6)

    @discord.ui.button(label="8", style=discord.ButtonStyle.blurple)
    async def limite_8(self, interaction, button):
        await self.definir_limite(interaction, 8)

    @discord.ui.button(label="10", style=discord.ButtonStyle.blurple)
    async def limite_10(self, interaction, button):
        await self.definir_limite(interaction, 10)


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
    global fila

    if message.author == bot.user:
        return

    if message.content == "!criarfila":
        canal_partidas = discord.utils.get(message.guild.text_channels, name="partidas")

        if canal_partidas is None:
            await message.reply("Não achei o canal #partidas.")
            return

        await canal_partidas.send(texto_fila(), view=PainelFila())
        await message.reply("Fila criada no canal #partidas!")

    elif message.content == "!limite":
        if not message.author.guild_permissions.administrator:
            await message.reply("Só administrador pode mudar o limite.")
            return

        await message.channel.send("Escolha o limite da fila:", view=LimiteView())

    elif message.content.startswith("!equipe"):
        mencionado = message.mentions.users.first()

        if not mencionado:
            await message.reply("Use: !equipe @jogador")
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
        args = message.content.split(" ")

        if len(args) < 2:
            await message.reply("Use: !start link_do_servidor")
            return

        link = args[1]

        if len(fila) < limite:
            await message.reply(f"A fila ainda não encheu! ({len(fila)}/{limite})")
            return

        jogadores = fila[:limite]
        time1, time2 = montar_times(jogadores)

        for player_id in jogadores:
            user = await bot.fetch_user(player_id)
            try:
                await user.send(f"Partida começou!\nLink: {link}")
            except:
                print(f"Erro ao enviar DM para {player_id}")

        texto = "**Partida iniciada!**\n\n"
        texto += "**Time 1:**\n" + "\n".join([f"<@{j}>" for j in time1])
        texto += "\n\n**Time 2:**\n" + "\n".join([f"<@{j}>" for j in time2])
        texto += "\n\nO link foi enviado na DM."

        await message.channel.send(texto)

        fila = fila[limite:]
        duplas.clear()
        convites.clear()
        rivais.clear()


bot.run(TOKEN)