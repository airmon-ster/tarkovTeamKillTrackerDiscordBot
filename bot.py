# create table ttk(id TEXT primary key,offendingPlayer TEXT, reportingPlayer TEXT, confirmed BOOLEAN);
# create table users(discordName INTEGER primary key, tarkovName TEXT);

import os
import sqlite3 as sql
import signal
import sys
import uuid
import re
import discord
from discord.ext import commands
from dotenv import load_dotenv

# get hidden discord token
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# save/commit db changes if ctrl_C is pressed
def signal_handler(sig, frame):
    print('You pressed Ctrl+C! Saving and commiting...')
    sqlCon.commit()
    sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)


# open up the db for use
with sql.connect('ttk.db') as sqlCon:

    #allow discord to query user information
    intents = discord.Intents.all()
    intents.members = True

    #create bot object
    bot = commands.Bot(command_prefix='!ttk ', intents=intents)

    # get discord name from tarkov name
    async def tarkovToDiscordName(tarkovName):
        # select discordName from users where tarkovName = "vladimirspuppet";
        result = ()
        discordName = sqlCon.execute("SELECT discordName,tarkovName from users where tarkovName = ? COLLATE NOCASE", (tarkovName,))
        for id in discordName:
            result = id
        return result

    async def discordToTarkovName(discordName):
        # select discordName,tarkovName from users where discordName LIKE "234234";
        result = ()
        discordName = sqlCon.execute("SELECT discordName,tarkovName from users where discordName = ? COLLATE NOCASE", (discordName,))
        for id in discordName:
            result = id
        return result

    # used to confirm that a given uuid for confirm function is legit
    async def is_valid_uuid(val):
        try:
            uuid.UUID(str(val))
            return True
        except ValueError:
            return False


    # ============== REGISTER ================#
    # Register discord name with tarkov name
    @bot.command(name='register', help='!ttk register <Your tarkov name>: Links your Discord name to your Tarkov name.')
    async def register(ctx, tarkovName):
        try:
            userSubscriptionID = ctx.message.author.id #get the raw, global user id
            userSubscriptionObject = bot.get_user(int(userSubscriptionID)) #turn global user id into friendly discord id (e.g. username#1337)
            if re.match('^[a-zA-Z0-9_]+$',tarkovName):
                sqlCon.execute("INSERT INTO users(discordName, tarkovName) VALUES (?,?);", (userSubscriptionID, tarkovName))
                await ctx.send(f"```Registered Tarkov Name: {tarkovName} as Discord Name: {str(userSubscriptionObject)}.```")
            else:
                await ctx.send("```Please enter a valid input```")
        except:
            await ctx.send("```There was an error during registration. Please confirm information entered.```")
        sqlCon.commit()

    # ============== ADD/REPORT ================#
    # insert into ttk values('uuid1','player1','player2',true);

    #create bot command to report teamkills
    @bot.command(name='report', help='!ttk report <offendingPlayer>: Reports a TK and awaits confirmation.')
    async def report(ctx, offendingPlayer):
        try:
            originalReporter = ctx.message.author.id
            if re.match('^[a-zA-Z0-9_]+$', offendingPlayer): # input validate user input
                # make sure reporter and offender are in the db
                offendingDiscordID, offendingTarkovName = await tarkovToDiscordName(offendingPlayer)
                reportingDiscordID, reportingTarkovName = await discordToTarkovName(originalReporter)
                
                if not offendingDiscordID is None and not reportingDiscordID is None:

                    #first, lets make sure there isnt an outstanding request

                    result = ""
                    priorUnresolved = sqlCon.execute("select 1 from ttk where offendingPlayer=? and reportingPlayer=? and confirmed=0 COLLATE NOCASE;",(offendingTarkovName, reportingTarkovName))
                    for id in priorUnresolved:
                        result = id

                    if (result) and result[0] == 1:
                        await ctx.send(f"SPAM PREVENTION: Looks like you already have an outstanding issue with {offendingTarkovName}. Have them first accept or reject your last report.")
                        return

                    uuidGen = str(uuid.uuid4())
                    sqlCon.execute("INSERT INTO ttk values(?,?,?,0)",(uuidGen, offendingTarkovName, reportingTarkovName))
                    offendingDiscordUser = bot.get_user(int(offendingDiscordID)) #turn global user id into friendly discord id (e.g. username#1337)
                    await offendingDiscordUser.send(f"Tarkov User: {reportingTarkovName} said that you TK'ed them... You can confirm this by copying and pasting the following bot command:\n```!ttk confirm {uuidGen}```\nOr reject it by copying and pasting the following bot command:\n```!ttk reject {uuidGen}```")
                    await ctx.send(f"```Sending confirmation to {offendingTarkovName} before updating results...```")
                else: # name not found in db
                    await ctx.send(f"I didn't find {offendingPlayer} in the database. Tell them to register or check your spelling!")
            else:
                await ctx.send("```Please enter a valid input```")
        except Exception as e:
            print(e)
            await ctx.send("```There was an error with your request.```")
        sqlCon.commit()



    # ============== CONFIRM/UPDATE ================#
    # update ttk set confirmed = 1 where id = 'uuid4';
    @bot.command(name='confirm', help='!ttk confirm <uuid>: Confirms a given TK instance.')
    async def confirm(ctx, uuidGen):
 
        try:
            if (await is_valid_uuid(uuidGen)):
                username = ctx.message.author.id
                usernameDiscordID, usernameTarkovName = await discordToTarkovName(username)
                result = ""
                results = sqlCon.execute("SELECT offendingPlayer from ttk where id = ?;", (uuidGen,))
                for id in results:
                    result = id
                if (result) and (result[0] == usernameTarkovName):
                    sqlCon.execute("update ttk set confirmed = 1 where id = ?;", (uuidGen,))
                    await ctx.send(f"```Confirmed TK id: {uuidGen}```")
                else:
                    await ctx.send(f"Provided instance not found.")
            else:
                await ctx.send("```Please enter a valid input```")
        except:
            await ctx.send("```There was an error with your request.```")
        sqlCon.commit()

    # ============== REJECT/UNLOCK ================#
    # when message is rejected, it will allow new requests to come in
    @bot.command(name='reject', help='!ttk reject <uuid>: Rejects a given TK instance.')
    async def reject(ctx, uuidGen):
        try:
            if (await is_valid_uuid(uuidGen)):
                username = ctx.message.author.id
                usernameDiscordID, usernameTarkovName = await discordToTarkovName(username)
                result = ""
                results = sqlCon.execute("SELECT offendingPlayer from ttk where id = ?;", (uuidGen,))
                for id in results:
                    result = id
                if (result) and (result[0] == usernameTarkovName):
                    sqlCon.execute("delete from ttk where id = ?;", (uuidGen,))
                    await ctx.send(f"```Rejected TK id: {uuidGen}```")
                else:
                    await ctx.send(f"Provided instance not found.")
            else:
                await ctx.send("```Please enter a valid input```")
        except:
            await ctx.send("```There was an error with your request.```")
        sqlCon.commit()

    # ============== VIEW PLAYER ================#
    # select count() from tks where confirmed is true;
    @bot.command(name='viewplayer', help='!ttk viewplayer <offendingPlayer>: Shows a single players TK count.')
    async def viewSingle(ctx, offendingPlayer):
        try:
            if re.match('^[a-zA-Z0-9_]+$', offendingPlayer): # input validate user input
                offendingDiscordID, offendingTarkovName = await tarkovToDiscordName(offendingPlayer)
                if not offendingDiscordID is None:
                    data = sqlCon.execute("SELECT count() from ttk where confirmed = 1 and offendingPlayer = ? COLLATE NOCASE;", (offendingTarkovName,))
                    for result in data:
                        await ctx.send(f"```{offendingTarkovName} has {result[0]} TK(s).```")
                else:
                    await ctx.send(f"```I didn't find {offendingPlayer} in the database. Tell them to register or check your spelling!```")
            else:
                await ctx.send("```Please enter a valid input```")
        except:
            await ctx.send("```There was an error with your request.```")
        sqlCon.commit()

    # ============== VIEW SERVER ================#
    @bot.command(name='viewserver', help='!ttk viewserver: Shows all TKs of players in this server.')
    async def viewServer(ctx):
        try:
            members = []

            for member in ctx.guild.members:
                try:
                    offendingDiscordID, offendingTarkovName = await discordToTarkovName(member.id)
                    if not offendingTarkovName is None:
                        data = sqlCon.execute("SELECT count() from ttk where confirmed = 1 and offendingPlayer = ? COLLATE NOCASE;", (offendingTarkovName,))
                        results = ""
                        for result in data:
                            results = result[0]
                            members.append(f"{offendingTarkovName} has {results} TK(s)")                      
                except:
                    pass
            print(members)
            formattedMembers = "\n".join(members)
            if formattedMembers:
                await ctx.send(f"```{formattedMembers}```")
            else:
                await ctx.send(f"```No TKs Found.```")
        except:
            await ctx.send("```There was an error with your request or there were no results.```")
        sqlCon.commit()

    # ============== VIEW TOP 10 ================#
    @bot.command(name='top', help='!ttk top: Shows the Top 10 TKers in the database.')
    async def top(ctx):
        try:
            results = []
            data = sqlCon.execute("select count(offendingplayer),offendingPlayer from ttk where confirmed = 1 group by offendingPlayer order by count(offendingPlayer) desc limit 10;")
            for d in data:
                results.append(f"{d[1]} has {d[0]} TK(s)")
            print(results)
            formattedMembers = "\n".join(results)
            if formattedMembers:
                await ctx.send(f"```{formattedMembers}```")
            else:
                await ctx.send(f"```No TKs Found.```")
        except Exception as e:
            await ctx.send(e)
            #await ctx.send("```There was an error with your request or there were no results.```")
        sqlCon.commit()

    sqlCon.commit()
    bot.run(TOKEN) #start the bot
