import discord
import json
import os

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

CANAL_COMANDOS = "🤖│comandos"
CANAL_RANKING = "🏆│ranking"
CANAL_AVISOS = "🚨│avisos-comandos"

# ================= JSON =================
def carregar():
    try:
        with open("ranking.json", "r") as f:
            return json.load(f)
    except:
        return {}

# ================= EVENTO =================
@bot.event
async def on_ready():
    print("Bot online")

# ================= COMANDOS =================
@bot.event
async def on_message(msg):
    if msg.author.bot:
        return

    # ================= !bot =================
    elif msg.content.lower() == "!bot":
        canal_cmd = discord.utils.get(msg.guild.text_channels, name=CANAL_COMANDOS)
        canal_avisos = discord.utils.get(msg.guild.text_channels, name=CANAL_AVISOS)

        embed = discord.Embed(
            title="🤖 Comandos Disponíveis",
            description=f"Comandos liberados no canal {canal_cmd.mention}",
            color=discord.Color.blue()
        )

        comandos = [
            ("!ranking", "Mostra suas estatísticas"),
            ("!topwins", "Top 10 vitórias"),
            ("!toploss", "Top 10 derrotas"),
            ("!perfil @jogador", "Perfil de jogador"),
            ("!historico", "Seu histórico"),
            ("!vs @jogador", "Comparação"),
            ("!streak", "Sequência de vitórias")
        ]

        for nome, desc in comandos:
            embed.add_field(
                name=f"{nome}",
                value=f"{desc}\n**(Todos Cargos Possuem Permissão Para Usar Esse Comando)**",
                inline=False
            )

        await canal_cmd.send(embed=embed)

        aviso = discord.Embed(
            title="🚨 Aviso",
            description=(
                f"Caso algum membro utilize indevidamente comandos no canal {canal_cmd.mention}, "
                f"poderá ser punido.\n\n"
                "**Observação:** Máximo de 5 advertências."
            ),
            color=discord.Color.red()
        )

        await canal_avisos.send(embed=aviso)

    # ================= !ranking =================
    elif msg.content == "!ranking":
        if msg.channel.name != CANAL_RANKING:
            return await msg.reply(f"Use no canal {CANAL_RANKING}")

        data = carregar()
        user = str(msg.author.id)
        stats = data.get(user, {"wins":0,"losses":0})

        await msg.channel.send(
            f"🏆 Vitórias: {stats['wins']}\n💀 Derrotas: {stats['losses']}"
        )

    # ================= !topwins =================
    elif msg.content == "!topwins":
        data = carregar()
        ranking = sorted(data.items(), key=lambda x: x[1].get("wins",0), reverse=True)

        texto = ""
        for i, (uid, stats) in enumerate(ranking[:10]):
            texto += f"`{i+1}.` <@{uid}> — 🏆 {stats['wins']}\n"

        embed = discord.Embed(
            title="🏆 Top 10 Vitórias",
            description=texto,
            color=discord.Color.blue()
        )

        await msg.channel.send(embed=embed)

    # ================= !toploss =================
    elif msg.content == "!toploss":
        data = carregar()
        ranking = sorted(data.items(), key=lambda x: x[1].get("losses",0), reverse=True)

        texto = ""
        for i, (uid, stats) in enumerate(ranking[:10]):
            texto += f"`{i+1}.` <@{uid}> — 💀 {stats['losses']}\n"

        embed = discord.Embed(
            title="💀 Top 10 Derrotas",
            description=texto,
            color=discord.Color.red()
        )

        await msg.channel.send(embed=embed)

    # ================= !perfil =================
    elif msg.content.startswith("!perfil"):
        data = carregar()
        user = msg.mentions[0] if msg.mentions else msg.author
        stats = data.get(str(user.id), {"wins":0,"losses":0})

        embed = discord.Embed(
            title=f"📊 Perfil de {user.display_name}",
            color=discord.Color.blue()
        )

        embed.add_field(name="Vitórias", value=stats["wins"])
        embed.add_field(name="Derrotas", value=stats["losses"])

        await msg.channel.send(embed=embed)

    # ================= !historico =================
    elif msg.content == "!historico":
        data = carregar()
        stats = data.get(str(msg.author.id), {"wins":0,"losses":0})

        await msg.channel.send(
            f"Vitórias: {stats['wins']} | Derrotas: {stats['losses']}"
        )

    # ================= !vs =================
    elif msg.content.startswith("!vs"):
        if not msg.mentions:
            return await msg.reply("Use: !vs @jogador")

        data = carregar()

        p1 = data.get(str(msg.author.id), {"wins":0,"losses":0})
        p2 = data.get(str(msg.mentions[0].id), {"wins":0,"losses":0})

        embed = discord.Embed(title="⚔️ VS", color=discord.Color.purple())

        embed.add_field(name=msg.author.display_name, value=f"{p1['wins']}W / {p1['losses']}L")
        embed.add_field(name=msg.mentions[0].display_name, value=f"{p2['wins']}W / {p2['losses']}L")

        await msg.channel.send(embed=embed)

    # ================= !streak =================
    elif msg.content == "!streak":
        data = carregar()
        ranking = sorted(data.items(), key=lambda x: x[1].get("streak",0), reverse=True)

        texto = ""
        for i, (uid, stats) in enumerate(ranking[:10]):
            texto += f"`{i+1}.` <@{uid}> — 🔥 {stats.get('streak',0)}\n"

        embed = discord.Embed(
            title="🔥 Top Streak",
            description=texto,
            color=discord.Color.orange()
        )

        await msg.channel.send(embed=embed)

bot.run(TOKEN)