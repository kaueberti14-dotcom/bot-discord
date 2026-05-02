import discord
import random

import os
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)

fila = []
limite = 10
partida_ativa = False

@bot.event
async def on_ready():
    print(f'Bot online: {bot.user}')

@bot.event
async def on_message(message):
    global fila, limite, partida_ativa

    if message.author == bot.user:
        return

    # entrar na fila
    if message.content == '!fila':
        if message.author.id in fila:
            await message.reply('Você já está na fila!')
            return

        if len(fila) >= limite:
            await message.reply('A fila já está cheia!')
            return

        fila.append(message.author.id)
        await message.reply(f'Entrou na fila ({len(fila)}/{limite})')

    # iniciar partida
    if message.content.startswith('!start'):
        if partida_ativa:
            await message.reply('Já tem uma partida acontecendo!')
            return

        args = message.content.split(' ')
        if len(args) < 3:
            await message.reply('Use: !start link quantidade')
            return

        link = args[1]
        limite = int(args[2])

        if len(fila) < limite:
            await message.reply('A fila ainda não encheu!')
            return

        partida_ativa = True

        random.shuffle(fila)

        time1 = []
        time2 = []

        for i, player in enumerate(fila):
            if i % 2 == 0:
                time1.append(player)
            else:
                time2.append(player)

        # mandar DM
        for player_id in fila:
            user = await bot.fetch_user(player_id)
            try:
                await user.send(f'Partida começou!\nLink: {link}')
            except:
                print('Erro ao enviar DM')

        await message.channel.send('Partida iniciada! Confira sua DM!')

        fila = []
        partida_ativa = False

bot.run(TOKEN)