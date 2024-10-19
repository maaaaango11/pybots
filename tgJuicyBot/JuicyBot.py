from telebot.async_telebot import AsyncTeleBot
from telebot import formatting
import sqlite3
import random
import asyncio

API_TOKEN = 'TOKEN'


bot = AsyncTeleBot(API_TOKEN)

connection = sqlite3.connect('juicydb.db')
cursor = connection.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS Quests (
id INTEGER PRIMARY KEY,
userid INTEGER NOT NULL,
task TEXT NOT NULL,
subscribers TEXT NOT NULL,
status BOOLEAN NOT NULL
)
''') 
#subscribers = EVERYONE / OTHERS / id;
connection.commit()
cursor.execute('''
CREATE TABLE IF NOT EXISTS Users (
uid INTEGER PRIMARY KEY,
firstname TEXT NOT NULL,
lastname TEXT NOT NULL
)
''') 
connection.commit()

@bot.message_handler(commands=['help', 'start'])
async def sendWelcome(message):
    try:
        with connection:
            cursor.execute('INSERT INTO Users (uid, firstname, lastname) VALUES (?,?,?)', (message.from_user.id, message.from_user.first_name, message.from_user.last_name))
    except sqlite3.Error as er:
        print(er)
        pass
    await bot.send_message(message.chat.id, formatting.hbold('Чтобы написать задание пиши /everyone *задание* или /others *задание*\nЧтобы получить задание пиши /quest'), parse_mode='HTML')

@bot.message_handler(commands=['everyone'])
async def createAllQuest(message):
    try:
        with connection:
            cursor.execute('INSERT INTO Quests (userid, task, subscribers, status) VALUES (?,?,?,?)', (message.from_user.id, message.text[message.text.find(" "):],'everyone', 'avalible')) #cut off /command
    except sqlite3.Error as er:
        print(er)
        pass
    #await bot.reply_to(message, "**Quest created!\nКвест создан!**")
    await bot.reply_to(message, formatting.hbold('Quest created\nКвест создан!'), parse_mode='HTML')

@bot.message_handler(commands=['others'])
async def createOthersQuest(message):
    try:
        with connection:
            cursor.execute('INSERT INTO Quests (userid, task, subscribers, status) VALUES (?,?,?,?)', (message.from_user.id, message.text[message.text.find(" "):],'others', 'avalible')) #cut off /command
    except sqlite3.Error as er:
        print(er)
        pass
    await bot.reply_to(message, formatting.hbold('Quest created!\nКвест создан!'), parse_mode='HTML')

@bot.message_handler(commands=['quest']) #set limit for antispam? do daily mail?
async def getQuest(message):
    try:
        with connection:
            cursor.execute('SELECT * FROM Quests WHERE status = "avalible" AND (subscribers = "everyone" OR (subscribers = "others" AND userid != ?))', (message.from_user.id,)) #????
            quests = cursor.fetchall()
            if(len(quests) > 0):
                rn = random.randint(0, len(quests)-1)
                print(rn)
                quest = quests[rn]
                cursor.execute('UPDATE Quests SET status = ? WHERE id = ?', (message.from_user.id, quest[0])) 
                #await bot.reply_to(message,"**Your quest:\nТвое задание:**\n```" + quest[2]+"```")
                await bot.send_message(message.chat.id,
                    formatting.format_text(
                        formatting.hbold('Your quest:\nТвое задание:'),
                        formatting.hcode(quest[2])
                    ), parse_mode='HTML'
                )
            else:
                await bot.send_message(message.chat.id, formatting.hbold('There are no quests avalible!\nДоступных заданий нет!'), parse_mode='HTML') 

    except sqlite3.Error as er:
        print(er)
        pass

# Handle all other messages with content_type 'text' (content_types defaults to ['text'])
@bot.message_handler(func=lambda message: True)
async def echo_message(message):
    await bot.reply_to(message, message.text)


asyncio.run(bot.polling())
connection.close()