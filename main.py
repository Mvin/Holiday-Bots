import discord
import discord.utils
import os
import json
from replit import db
from keep_alive import keep_alive
import pytz
import math
import random
from datetime import datetime, timedelta
from os import path
import threading
import copy

intents = discord.Intents(messages=True, guilds=True, reactions=True)
client = discord.Client(intents=intents)

#State Variables
client.token = os.getenv('TOKEN')
threadLock = threading.Lock()

#load the input file
here = os.path.dirname(os.path.abspath(__file__))
input_file =open(os.path.join(here, 'input.json'),mode="r",encoding="utf-8")
input_json = json.load(input_file)
config = input_json["config"]

#config parameters for this to run on the server
client.config = input_json["config"]
client.this_guild = 279668907101388810
client.bot_channel_id = 751499436982796479
client.min_messages = config["spawn"]["min_messages"]
client.max_messages = config["spawn"]["max_messages"]
client.cupid_spawn_time = config["spawn"]["spawn_time"]
client.current_cupid = 0
client.spawn_cupid = 0
client.is_cupid_spawned = False
client.last_message_from = 0
client.cupid_death_time = 0
client.cupid_message_id = 0
client.cupid_defeated = False
client.cupid_defeated_by = []
client.correct_reaction = 0
client.current_spawn = 0
client.custom_emojis = []
client.confirmations = {}
client.f_o = {}
client.availible_floats = []

#Utility Functions(To be taken into separate file)

async def add_reaction(emoji, message):
  await message.add_reaction(emoji)

async def decode_emoji(emoji):
  if(":" in emoji):
    temp = emoji.replace(":", "")
    for c_emoji in client.custom_emojis:
      if(c_emoji.name == temp):
        return c_emoji
  else:
    return emoji

async def clear_emojis(input, message):
  for emoji in input:
    await message.clear_reaction(await decode_emoji(emoji))

def create_user_key(user_id):
  return "profile_{0}_{1}".format(user_id, input_json["db_name"])

def create_float_key():
  return "floats_{0}".format(input_json["db_name"])

def add_float_to_db(float_object):
  this_key = create_float_key()
  if (this_key in db.keys()):
    current_profile = db[this_key]
    entry_json = json.loads(current_profile)
    entry_json["mid"] = float_object["mid"]
    entry_json["correct_reaction"] = float_object["correct_reaction"]
    entry_json["float_id"] = float_object["float_id"]
    entry_json["end_time"] = float_object["end_time"]
    entry_json["defeated"] = float_object["defeated"]
    entry_json["defeated_by"] = float_object["defeated_by"]
    json_profile = json.dumps(entry_json)
    db[this_key] = json_profile
  else:
    profile = {}
    profile["mid"] = float_object["mid"]
    profile["correct_reaction"] = float_object["correct_reaction"]
    profile["float_id"] = float_object["float_id"]
    profile["end_time"] = float_object["end_time"]
    profile["defeated"] = float_object["defeated"]
    profile["defeated_by"] = float_object["defeated_by"]
    json_profile = json.dumps(profile)
    db[this_key] = json_profile

def clear_float_object():
  this_key = create_float_key()
  del db[this_key]

def get_float_object():
  this_key = create_float_key()
  if (this_key in db.keys()):
    current_profile = db[this_key]
    entry_json = json.loads(current_profile)
    return entry_json
  else: 
    return False

async def manage_user_profile(user_id, score, n_arrows, activity, candy, presents, po=[], decorations = 0, lo=[], this_float = "", featured = None):
  this_key = create_user_key(user_id)
  if (this_key in db.keys()):
    #print("Updating user profile!")
    current_profile = db[this_key]
    entry_json = json.loads(current_profile)
    entry_json['score'] += score
    entry_json['n_arrows'] += n_arrows
    entry_json['activity'] += activity
    entry_json['candy'] += candy
    entry_json['decorations'] += decorations
    entry_json['presents'] += presents

    if(featured != None):
      entry_json['featured'] = featured

    #if the number of presents is negative remove objects
    if(presents < 0):
      target = abs(presents)
      for x in range(target):
        entry_json['presents_objects'].pop(0)
    #if postive we are adding present objects
    elif(presents > 0):
      for present in po:
        entry_json['presents_objects'].append(present)

    #if there are any new loot objects update the collection
    if(lo != []):
      for loot in lo:
        entry_json['collection'] = await update_collection(loot, this_float, entry_json['collection'])

    #recalculate score
    entry_json['score'] = 100 * math.ceil(entry_json['candy'] + (entry_json['activity'] / 10))
    json_profile = json.dumps(entry_json)
    db[this_key] = json_profile
  else:
    print("Created user profile!")
    profile = {}
    profile['score'] = score
    profile['n_arrows'] = n_arrows
    profile['activity'] = activity
    profile['candy'] = candy
    profile['decorations'] = decorations
    profile['presents'] = presents
    profile['presents_objects'] = []
    profile['collection'] = await generate_collection()
    profile['featured'] = None
    #calculate score
    profile['score'] = 100 * math.ceil(profile['candy'] + (profile['activity'] / 10))
    json_profile = json.dumps(profile)
    db[this_key] = json_profile

async def print_rankings_embed(message):
  rank_items = input_json["commands"]["=rank"]["items"]
  embedVar = discord.Embed(title=rank_items["title"], description=rank_items["description"], color=0x3498DB)
  embedVar.set_author(name=input_json["event_name"])

  all = db.keys()
  profiles_with_candy = []

  for key in all:
    if(input_json["db_name"] in key):
      profile = db[key]
      profile_json = json.loads(profile)

      if('candy' in profile_json and profile_json['candy'] > 0):
        key_parts = key.split("_")
        profile_json['key'] = key_parts[1]
        if(int(key_parts[1]) != client.this_guild):
          profiles_with_candy.append(profile_json)
  
  profiles_with_candy.sort(key=lambda x: x['score'], reverse=True)

  index = 1
  for profile in profiles_with_candy:
    score_msg = "<@{0}>".format(profile['key']) + " - 💰 {:,}".format(profile['score'])
    embedVar.add_field(name = '#{0}'.format(index), value= score_msg, inline = False)
    index += 1
    #/ 🏅
  
  embedVar.set_thumbnail(url=message.guild.icon_url)
  await message.channel.send(embed=embedVar)

async def add_present_to_all(presents, this_float, id):
  for key in db.keys():
    if(input_json["db_name"] in key):
      user = db[key]
      user_json = json.loads(user)
      if('presents_objects' in user_json):
        user_json['presents'] += presents
        total_presents = user_json['presents_objects']

        for x in range(presents):
          total_presents.append({ "from": this_float, "id": id, "rarity": 0 })

        user_json['presents_objects'] = total_presents
        db[key] = json.dumps(user_json)

async def get_user_profile(user_id):
  this_key = create_user_key(user_id)
  if (this_key in db.keys()):
    return db[this_key]
  else:
    return []

async def clear_user_profile(user_id):
  this_key = create_user_key(user_id)
  del db[this_key]
  return True

async def generate_discord_url(message):
  base_url = 'https://discord.com/channels'
  return '{0}/{1}/{2}/{3}'.format(base_url, client.this_guild, message.channel.id, message.id)

def check_floats():
  floats = input_json["floats"]
  index = 0

  if(len(client.availible_floats) == 0):
    for t_float in floats:
      if(index == 0):
        index += 1
        continue

      client.availible_floats.append(index)
      index += 1

async def create_profile_embed(profile, user):
  profile_items = input_json["commands"]["=profile"]["items"]
  embedVar = discord.Embed(title=profile_items["title"], description=user, color=0x9B59B6)
  embedVar.set_author(name=input_json["event_name"])
  entry_json = json.loads(profile)
  featured = entry_json["featured"]

  embedVar.add_field(name="Total Score", value='💰 {:,}'.format(entry_json['score']), inline=False)
  embedVar.add_field(name="Activity", value='📈 {:,}'.format(entry_json['activity']), inline=False)
  embedVar.add_field(name=client.config["arrows"]["name"], value=client.config["arrows"]["emoji"] + ' {:,}'.format(entry_json['n_arrows']), inline=False)
  #embedVar.add_field(name=client.config["points"]["name"], value=client.config["points"]["emoji"] + ' {:,}'.format(entry_json['candy']), inline=False)
  embedVar.add_field(name=client.config["decorations"]["name"], value=client.config["decorations"]["emoji"] + ' {:,}'.format(entry_json['decorations']), inline=False)
  embedVar.add_field(name="Presents", value='🎁 {:,}'.format(entry_json['presents']), inline=False)

  if("featured" in entry_json and entry_json["featured"] != None):
    rarity = await decode_rarity(featured["rarity"])
    embedVar.add_field(name="Featured Item", value='️{0} `{1}` - **[{2}]**'.format(client.config["items"]["emoji"], featured["name"], rarity), inline=False)
    embedVar.set_image(url=featured["image"])
  return embedVar

async def make_cupid_embed(title, description, users, image, thumb):
  embedVar = discord.Embed(title=title, description=description, color=0xB62101)
  embedVar.set_image(url=image)
  embedVar.set_author(name=input_json["event_name"])
  embedVar.set_thumbnail(url=thumb)
  embedVar.set_footer(text=input_json["commands"]["=spawn"]["items"]["spawn-footer"])

  if(len(users) != 0):
    participants = ""
    for user in users:
      participants += ' <@{0}> '.format(user)
    embedVar.add_field(name='Participants', value= participants, inline=False)

  return embedVar

async def add_fields_to_embed(fields, embed, input = []):
  index = 0
  for field in fields:
    if(input != [] and input[index] != None):
      value = field["value"].format(input[index])
    else:  
      value = field["value"]
    embed.add_field(name=field["name"],value=value,inline=field["inline"])
    index += 1

async def spawn_cupid(float_id = -1):
  float_object = get_float_object()

  if(float_object == False):
    client.is_cupid_spawned = True
    print("Spawning Cupid")
    floats = input_json["floats"]
    spawn_items = input_json["commands"]["=spawn"]["items"]
    my_guild = client.get_guild(client.this_guild)
    bot_channel = my_guild.get_channel(client.bot_channel_id)
    #if you pass in a float id spawn that instead
    if(float_id != -1):
      random_key = float_id
    else:
      check_floats()
      random_key = random.choice(client.availible_floats)
      client.availible_floats.remove(random_key)
      #random_key = random.randint(1, len(floats) - 1)

    this_float = floats[random_key]
    random_option = random.randint(0, len(this_float["options"]) - 1)
    this_option = this_float["options"][random_option]
    client.correct_reaction = await decode_emoji(this_option["emoji"])
    client.current_spawn = random_key
    cupid_msg = await bot_channel.send(embed=await make_cupid_embed(spawn_items["title"], "{0} \n ----------------------------------------- \n\n {1} ".format(this_float["description"], this_option["name"]), [], this_float["picture"], 
    this_float["logo"]))
    #await bot_channel.send(client.correct_reaction)
    for emoji in this_float["emojis"]:
      await add_reaction(await decode_emoji(emoji), cupid_msg)
    client.cupid_message_id = cupid_msg.id
    client.current_cupid = 0
    client.spawn_cupid = 0
    client.cupid_defeated = False
    client.cupid_defeated_by = []
    client.cupid_death_time = datetime.now() + timedelta(minutes=client.cupid_spawn_time)
    f_o = { "mid": cupid_msg.id, "correct_reaction": this_option["emoji"], 
      "float_id": random_key, "end_time": str(client.cupid_death_time),
      "defeated": False, "defeated_by": [] }
    client.f_o = f_o
    add_float_to_db(f_o)
    await discord.utils.sleep_until(client.cupid_death_time)
    await kill_cupid()
  else:
    print("Failed to spawn, cause an active float was found in the DB.")

async def reattach_spawn(f_o):
  print("Ataching to previous Float!")
  #set all the client information for a spawn
  client.f_o = f_o
  client.correct_reaction = await decode_emoji(f_o["correct_reaction"])
  client.current_spawn = f_o["float_id"]
  client.cupid_message_id = f_o["mid"]
  client.current_cupid = 0
  client.spawn_cupid = 0
  client.is_cupid_spawned = True
  client.cupid_death_time = datetime.strptime(f_o["end_time"], '%Y-%m-%d %H:%M:%S.%f')
  client.cupid_defeated = f_o["defeated"]
  client.cupid_defeated_by = f_o["defeated_by"]
  await discord.utils.sleep_until(client.cupid_death_time)
  await kill_cupid()

async def kill_cupid():
  my_guild = client.get_guild(client.this_guild)
  bot_channel = my_guild.get_channel(client.bot_channel_id)
  this_message = await bot_channel.fetch_message(client.cupid_message_id)
  kill_items = input_json["commands"]["=die"]["items"]
  this_float = input_json["floats"][client.current_spawn]
  death_title = ""

  if(len(client.cupid_defeated_by) == 0):
    death_title = kill_items["types"][0]["title"]
    death_message = kill_items["types"][0]["message"]
  elif(client.cupid_defeated == True):
    n_presents = client.config["presents"]["number"]
    present = [{ "from": this_float["name"], "id": client.current_spawn, "rarity": 0 }]
    death_title = kill_items["types"][1]["title"]
    death_message = kill_items["types"][1]["message"].format(n_presents)

    for user in client.cupid_defeated_by:
      await manage_user_profile(user, 0, 0, 0, 0, n_presents, present)

  else:
    death_title = kill_items["types"][0]["title"]
    death_message = kill_items["types"][0]["message"]

  await this_message.edit(embed=await make_cupid_embed(death_title, "{0} \n --------------------------------------------- \n\n {1} ".format(this_float["description"], death_message), client.cupid_defeated_by, this_float["picture"],
  this_float["logo"]))
  client.is_cupid_spawned = False
  for emoji in input_json["floats"][client.current_spawn]["emojis"]:
    await this_message.clear_reaction(await decode_emoji(emoji))
  
  clear_float_object()

async def open_presents(user_id, presents, profile):
  total_arrows = 0
  total_candy = 0
  total_decorations = 0
  total_loot = []
  last_float = ""
  present_objects = profile["presents_objects"]

  for x in range(presents):
    this_present = present_objects[x]
    this_float = input_json["floats"][this_present["id"]]
    last_float = this_float["name"]

    total_arrows += random.randint(client.config["arrows"]["min"],
     client.config["arrows"]["max"])
    total_candy += random.randint(client.config["points"]["min"],
     client.config["points"]["max"])

    #if this is a BG present dont give decorations
    if(this_float["name"] != "Boston Gaymers"): 
      total_decorations += random.randint(client.config["decorations"]["min"],
        client.config["decorations"]["max"])
    else:
      total_decorations = 0

    total_loot.append(await pick_loot(this_float["loot"]))

  await manage_user_profile(user_id, 0, total_arrows, 0, total_candy, -presents, [], 
  total_decorations, total_loot, last_float)

  return [total_arrows, total_candy, total_loot, total_decorations, last_float]

async def generate_collection():
  collection = []
  #for each float create a collection object
  for this_float in input_json["floats"]:
    temp = { "name": this_float["name"], "total": len(this_float["loot"]), "owned": 0, "loot": [] }
    #add all the loot
    for loot in this_float["loot"]:
      t_loot = copy.deepcopy(loot)
      t_loot["owned"] = False
      temp["loot"].append(t_loot)

    collection.append(temp)
  return collection

async def update_collection(loot, this_float, collection):
  #search for the float in the collection
  for part in collection:
    if(part["name"] == this_float):
      for t_loot in part["loot"]:
        if(t_loot["name"] == loot["name"] and t_loot["owned"] != True):
          part["owned"] += 1
          t_loot["owned"] = True

  return collection

async def pick_loot(options):
  loot_pile = []
  for loot in options:
    for x in range(loot["rarity"]):
      loot_pile.append(loot)

  random_option = random.randint(0, len(loot_pile) - 1)

  return loot_pile[random_option]

async def create_open_presents_embed(output, mention, message):
  embedVar = discord.Embed(title="🎁 Your {0} Present Rewards:".format(output[4]), description=mention, color=0xC27C0E)
  if(output[3] != 0):
    embedVar.add_field(name="{0}".format(client.config["decorations"]["name"]), value="{0} {1}".format(client.config["decorations"]["emoji"], output[3]), inline=False)
  if(output[1] != 0):
    embedVar.add_field(name="{0}".format(client.config["points"]["name"]), value="{0} {1}".format(client.config["points"]["emoji"], output[1]), inline=False)
  if(output[0] != 0):
    embedVar.add_field(name="{0}".format(client.config["arrows"]["name"]), value="{0} {1}".format(client.config["arrows"]["emoji"], output[0]), inline=False)
  embedVar.add_field(name="{0}".format(client.config["items"]["name"]), value="{0} `{1}` - **[{2}]**".format(client.config["items"]["emoji"], output[2][0]["name"], await decode_rarity(output[2][0]["rarity"])), inline=False)
  embedVar.set_thumbnail (url="https://media.giphy.com/media/l0NgQb9BvGwxqvOvK/giphy.gif")
  embedVar.set_image(url=output[2][0]["image"])
  return embedVar

async def decode_rarity(rarity):
  return client.config["rarity"]["{0}".format(rarity)]

async def create_inventory_embed(inv_items, message, collection, index):
  embedVar = discord.Embed(title=inv_items["title"].format(index + 1), 
  description=inv_items["description"][index].format(message.author.mention), color=0x2ECC71)
  embedVar.set_thumbnail(url=inv_items["thumbnail"])
  embedVar.set_author(name=input_json["event_name"])

  for this_float in collection:
    loot_string = "\n"
    for loot in this_float["loot"]:
      if(loot["owned"] == True):
        loot_string += "✅ [" + loot["name"] + "](" + loot["image"] + ")\n"
      else:
        loot_string += loot["name"] + "\n"

    embedVar.add_field(name=this_float["name"] + " [{0}/{1}]".format(this_float["owned"], this_float["total"]), value="{0}".format(loot_string),inline=True)
  await message.author.send(embed=embedVar)

async def confirm_donate(amount, userO, reaction, message):
  donate_items = input_json["commands"]["=donate"]["items"]
  your_id = userO.id
  profile = await get_user_profile(your_id)
  profile_json = json.loads(profile)
  s_profile = await get_user_profile(client.this_guild)
  s_profile_json = json.loads(s_profile)
  current_decorations = s_profile_json["decorations"]

  my_guild = client.get_guild(client.this_guild)
  bot_channel = my_guild.get_channel(client.bot_channel_id)
  this_message = await bot_channel.fetch_message(message)

  if(reaction == donate_items["confirm"]["emojis"][1]):
    embedVar = discord.Embed(title=donate_items["cancelled"]["title"], description=donate_items["cancelled"]["description"].format(userO.mention, amount), color=0x9B59B6)
    embedVar.set_thumbnail(url=donate_items["thumbnail"])
    embedVar.set_author(name=input_json["event_name"])
    await this_message.edit(embed=embedVar)
    await clear_emojis(donate_items["confirm"]["emojis"], this_message)
    return
  else:
    if(amount > profile_json["decorations"]):
      await bot_channel.send(donate_items["errors"][0].format(userO.mention))
      return
    elif(amount < 2):  
      await bot_channel.send(donate_items["errors"][1].format(userO.mention))
      return

    points = math.floor(amount/2)
    await manage_user_profile(your_id, 0, 0, 0, points, 0, [], -amount)
    await manage_user_profile(client.this_guild, 0, 0, 0, 0, 0, [], amount)
    embedVar = discord.Embed(title=donate_items["success"]["success-title"], description=donate_items["success"]["description"].format(userO.mention, amount), color=0x1ABC9C)
    embedVar.set_thumbnail(url=donate_items["thumbnail"])
    embedVar.set_author(name=input_json["event_name"])
    await this_message.edit(embed=embedVar)
    await clear_emojis(donate_items["confirm"]["emojis"], this_message)

    #find the current tier
    current_tier = 0
    for tier in client.config["float"]["tiers"]:
      if(current_decorations >= tier):
        current_tier = tier

    total_s_decorations = int(current_decorations) + amount
    for tier in client.config["float"]["tiers"]:
      if(tier > current_tier):
        if(total_s_decorations >= tier):
          await add_present_to_all(client.config["float"]["gift"], 
            input_json["floats"][0]["name"], 0)

async def confirm_shop(amount, userO, reaction, message):
  store_items = input_json["commands"]["=shop"]["items"]
  user = userO.id
  profile = await get_user_profile(user)
  profile_json = json.loads(profile)
  cost = amount * store_items["cost"] 
  this_float = input_json["floats"][0]

  my_guild = client.get_guild(client.this_guild)
  bot_channel = my_guild.get_channel(client.bot_channel_id)
  this_message = await bot_channel.fetch_message(message)

  if(reaction == store_items["confirm"]["emojis"][1]):
    embedVar = discord.Embed(title=store_items["cancelled"]["title"], description=store_items["cancelled"]["description"].format(userO.mention, amount, cost), color=0x9B59B6)
    embedVar.set_thumbnail(url=store_items["thumbnail"])
    embedVar.set_author(name=input_json["event_name"])
    await this_message.edit(embed=embedVar)
    await clear_emojis(store_items["confirm"]["emojis"], this_message)
    return
  else:
    if(cost > profile_json["decorations"]):
      await bot_channel.send(store_items["errors"][1].format(userO.mention))
      return

    presents = []
    for x in range(amount):
      presents.append({ "from": this_float["name"], "id": 0, "rarity": 0 })

    await manage_user_profile(user, 0, 0, 0, 0, amount, presents, -cost)
    embedVar = discord.Embed(title=store_items["success"]["success-title"], description=store_items["success"]["description"].format(userO.mention, amount, cost), color=0x9B59B6)
    embedVar.set_thumbnail(url=store_items["thumbnail"])
    embedVar.set_author(name=input_json["event_name"])
    await this_message.edit(embed=embedVar)
    await clear_emojis(store_items["confirm"]["emojis"], this_message)


#Discord Events
@client.event
async def on_ready():
  print('We have logged in as {0.user}'.format(client))
  await manage_user_profile(client.this_guild, 0, 0, 0, 0, 0)
  await client.change_presence(activity=discord.Game(name=" | =event for details"))

  my_guild = client.get_guild(client.this_guild)
  for emoji in my_guild.emojis:
    client.custom_emojis.append(emoji)

  #if there is dangling float lets reattach
  float_o = get_float_object()
  if(float_o != False):
    print("Unclosed float found.")
    await reattach_spawn(float_o)


@client.event
async def on_raw_reaction_add(reaction):
  if reaction.member == client.user:
    return

  user = reaction.member

  #If the user reacts to the cupid message, with the correct reaction
  #and they have not already gotten points
  if(reaction.message_id == client.cupid_message_id and str(reaction.emoji) == str(client.correct_reaction) and user.id not in client.cupid_defeated_by):
    #if they are the first user to do so
    if(client.cupid_defeated == False):
      client.cupid_defeated = True
      embedVar = discord.Embed(title=input_json["commands"]["=victory"]["title"], description=input_json["commands"]["=victory"]["description"], color=0xEF5148)
      embedVar.set_thumbnail(url=input_json["commands"]["=event"]["items"]["thumbnail"])
      await user.send(embed=embedVar)
      await manage_user_profile(user.id, 0, 0, 0, client.config["points"]["winner"], 0)
      client.cupid_defeated_by.append(user.id)
      client.f_o["defeated"] = True
      client.f_o["defeated_by"] = client.cupid_defeated_by
    else:
      await manage_user_profile(user.id, 0, 0, 0, client.config["points"]["correct"], 0)
      client.cupid_defeated_by.append(user.id)
      client.f_o["defeated_by"] = client.cupid_defeated_by
    
    add_float_to_db(client.f_o)

  #if the user reacts to the cupid message, with the wrong reaction
  #and they have not already gotten points
  if(reaction.message_id == client.cupid_message_id and user.id not in client.cupid_defeated_by):
    await manage_user_profile(user.id, 0, 0, 0, client.config["points"]["participant"], 0)
    client.cupid_defeated_by.append(user.id)
    client.f_o["defeated_by"] = client.cupid_defeated_by
    add_float_to_db(client.f_o)

@client.event
async def on_reaction_add(reaction, user):
  if user == client.user:
    return
  
  #Check if this is a reaction to a confirm
  if(reaction.message.id in client.confirmations):
    confirm = client.confirmations[reaction.message.id]

    if(user.id != confirm["user"]):
      print("nice try!")
      return

    if(confirm["function"] == "confirm_shop"):
      await confirm_shop(confirm["input"], user, reaction.emoji, 
        confirm["message"])
    elif(confirm["function"] == "confirm_donate"):
      await confirm_donate(confirm["input"], user, reaction.emoji, 
        confirm["message"])
    
    del client.confirmations[reaction.message.id]

#On Message, where all the commands are
@client.event
async def on_message(message):
  #if this message is from the bot ignore it
  if message.author == client.user:
    return

  #create a useful shorthand for the message content
  msg = message.content
  msg_lower = msg.lower()

  #if(message.channel.id == client.bot_channel_id):
  #event description
  if(msg == '=event'):
    embedVar = discord.Embed(title=input_json["commands"]["=event"]["items"]["title"], description=input_json["commands"]["=event"]["items"]["description"], color=0xF1C40F)
    embedVar.set_author(name=input_json["event_name"])
    await add_fields_to_embed(input_json["commands"]["=event"]["items"]["fields"], embedVar)
    embedVar.set_thumbnail(url=message.guild.icon_url)
    embedVar.set_thumbnail(url=input_json["commands"]["=event"]["items"]["thumbnail"])
    await message.channel.send(embed=embedVar)

#get rankings 
  if(msg == '=rank'):
    await print_rankings_embed(message)

#inventory
  if(msg.startswith('=inventory')):  
    inv_items = input_json["commands"]["=inventory"]["items"]
    your_id = message.author.id
    profile = await get_user_profile(your_id)
    profile_json = json.loads(profile)
    collection = profile_json["collection"]

    message_parts = message.content.split("=inventory ", 1)
    if(len(message_parts) > 1):
      n_item = message_parts[1]
      found = []

      for t_float in collection:
        for item in t_float["loot"]:
          if(item["name"] == n_item and item["owned"] == True):
            found = item

      if(found != []):
        await manage_user_profile(your_id, 0, 0, 0, 0, 0, [], 0, [], "", found)
        embedVar = discord.Embed(title=inv_items["success"]["title"],
        description=inv_items["success"]["message"].format(message.author.mention, n_item), color=0x2ECC71)
        embedVar.set_thumbnail(url=found["image"])
        embedVar.set_author(name=input_json["event_name"])
        await message.channel.send(embed=embedVar)
      else:
        await message.channel.send(inv_items["errors"][0])

    else:
      length = len(collection)
      middle_index = length//2
      first = collection[:middle_index]
      second = collection[middle_index:]

      await create_inventory_embed(inv_items, message, first, 0)
      await create_inventory_embed(inv_items, message, second, 1)
      await message.channel.send("Your inventory has been sent in DMs.")

#shop the BG Float
  if(msg.startswith('=shop')):
    store_items = input_json["commands"]["=shop"]["items"]
    your_id = message.author.id
    profile = await get_user_profile(your_id)
    profile_json = json.loads(profile)

    message_parts = message.content.split("=shop ", 1)
    if(len(message_parts) > 1):
      amount = int(message_parts[1])

      if(amount <= 0):
        await message.channel.send(store_items["errors"][0].format(message.author.mention))
        return

      cost = amount * store_items["cost"]

      if(cost > profile_json["decorations"]):
        await message.channel.send(store_items["errors"][1].format(message.author.mention))
        return

      embedVar = discord.Embed(title=store_items["confirm"]["title"], description=store_items["confirm"]["description"].format(message.author.mention,amount, cost), color=0x9B59B6)
      embedVar.set_thumbnail(url=store_items["thumbnail"])
      embedVar.set_author(name=input_json["event_name"])
      confirm_msg = await message.channel.send(embed=embedVar)

      for emoji in store_items["confirm"]["emojis"]:
        await add_reaction(await decode_emoji(emoji), confirm_msg)

      key = confirm_msg.id
      client.confirmations[key] = {
        "function": "confirm_shop",
        "input": amount,
        "user": your_id,
        "message": confirm_msg.id
      }
    else:
      embedVar = discord.Embed(title=store_items["title"], description=store_items["description"].format(message.author.mention,profile_json["decorations"]), color=0x9B59B6)
      embedVar.set_thumbnail(url=store_items["thumbnail"])
      embedVar.set_author(name=input_json["event_name"])
      await add_fields_to_embed(store_items["fields"], embedVar, [profile_json["decorations"], store_items["cost"]])
      await message.channel.send(embed=embedVar)

#donate to the float
  if(msg.startswith('=donate')):
    donate_items = input_json["commands"]["=donate"]["items"]
    your_id = message.author.id
    profile = await get_user_profile(your_id)
    profile_json = json.loads(profile)
    s_profile = await get_user_profile(client.this_guild)
    s_profile_json = json.loads(s_profile)
    current_decorations = s_profile_json["decorations"]

    message_parts = message.content.split("=donate ", 1)
    if(len(message_parts) > 1):
      donation = int(message_parts[1])
      if(donation > profile_json["decorations"]):
        await message.channel.send(donate_items["errors"][0].format(message.author.mention))
        return
      elif(donation < 2):  
        await message.channel.send(donate_items["errors"][1].format(message.author.mention))
        return
      else:
        embedVar = discord.Embed(title=donate_items["confirm"]["title"], description=donate_items["confirm"]["description"].format(message.author.mention,donation), color=0x9B59B6)
        embedVar.set_thumbnail(url=donate_items["thumbnail"])
        embedVar.set_author(name=input_json["event_name"])
        confirm_msg = await message.channel.send(embed=embedVar)

        key = confirm_msg.id
        client.confirmations[key] = {
          "function": "confirm_donate",
          "input": donation,
          "user": your_id,
          "message": confirm_msg.id
        }

        for emoji in donate_items["confirm"]["emojis"]:
          await add_reaction(await decode_emoji(emoji), confirm_msg)

    else:
      embedVar = discord.Embed(title=donate_items["title"], description=donate_items["description"].format(message.author.mention,profile_json["decorations"]), color=0x1ABC9C)
      embedVar.set_thumbnail(url=donate_items["thumbnail"])
      embedVar.set_author(name=input_json["event_name"])
      await message.channel.send(embed=embedVar)

#Heart of love
  if(msg == '=float'):
    spawn_items = input_json["commands"]["=float"]["items"]
    profile = await get_user_profile(client.this_guild)
    profile_json = json.loads(profile)
    embedVar = discord.Embed(title=spawn_items["title"], description=spawn_items["description"].format(profile_json['decorations']),color=0xE74C3C)
    embedVar.set_author(name=input_json["event_name"])

    index = 1
    highest_tier = 0
    found = False
    for tier in client.config["float"]["tiers"]:
      if(tier > profile_json['decorations'] and found == False):
        embedVar.add_field(name="⏭️ Tier {0}".format(index), value=spawn_items["tier_message"].format(tier), inline=False)
        found = True
      elif(tier <= profile_json['decorations']):
        highest_tier = index
        embedVar.add_field(name="✅ Tier {0} ".format(index), value=spawn_items["c_tier_message"].format(tier), inline=True)
      index += 1

    embedVar.add_field(name="Reward Per Tier".format(index), value="🎁 5 Presents", inline=False)
    embedVar.set_footer(text=spawn_items["footer"])
    embedVar.set_image(url=spawn_items["float_images"][highest_tier])
    embedVar.set_thumbnail(url=message.guild.icon_url)
    await message.channel.send(embed=embedVar)

#give us presents (delete later)
  #if(msg.startswith('=give')):
    #message_parts = message.content.split("=give ", 1)
    #if(len(message_parts) > 1):
      # t_float = int(message_parts[1])
      #this_float = input_json["floats"][t_float]
      #number = 50
      #present = []
      
      #for x in range(number):
        #present.append({ "from": this_float["name"], "id": t_float, "rarity": 0 })

      #await manage_user_profile(message.author.id, 0, 0, 0, 0, number, present)
      #await message.channel.send("Gave {0} presents from {1}".format(number, 
      #this_float["name"]))

  #if(msg.startswith('=give2')):
    #message_parts = message.content.split("=give2 ", 1)
    #if(len(message_parts) > 1):
      # n_arrows = int(message_parts[1])
      #await manage_user_profile(message.author.id, 0, n_arrows, 0, 0, 0)
      #await message.channel.send("Gave {0} arrows".format(n_arrows))

  #if(msg.startswith('=give3')):
    #message_parts = message.content.split("=give3 ", 1)
    #if(len(message_parts) > 1):
      #n_arrows = int(message_parts[1])
      #await manage_user_profile(message.author.id, 0, 0, 0, 0, 0, [], n_arrows)
      #await message.channel.send("Gave {0} decorations".format(n_arrows))

  if(msg.startswith('=glitbomb')):
    i_json = input_json["commands"]["=throw"]["items"]
    message_parts = message.content.split("=glitbomb ", 1)

    if(len(message_parts) > 1 and len(message.mentions) > 0):
      user = message.mentions[0]
      your_id = message.author.id

      if(your_id == user.id):
        await message.channel.send(i_json["errors"][0])
        return

      profile = await get_user_profile(your_id)
      profile_json = json.loads(profile)

      if(profile_json['n_arrows'] > 0):
        #shoot (need to decrement arrows)
        await manage_user_profile(your_id, 0, -1, 0, 0, 0)
        current_message = await message.channel.send(i_json["loading"])
        this_message = await message.channel.fetch_message(current_message.id)
        cupid_animation_time = datetime.now() + timedelta(seconds=1)
        await discord.utils.sleep_until(cupid_animation_time)
        await this_message.edit(content=i_json["loading"] + ".")
        cupid_animation_time = datetime.now() + timedelta(seconds=1)
        await discord.utils.sleep_until(cupid_animation_time)
        await this_message.edit(content=i_json["loading"] + "..")
        cupid_animation_time = datetime.now() + timedelta(seconds=1)
        await discord.utils.sleep_until(cupid_animation_time)
        await this_message.edit(content=i_json["loading"] + "...")
        cupid_animation_time = datetime.now() + timedelta(seconds=1)
        await discord.utils.sleep_until(cupid_animation_time)
        await this_message.delete()

        arrow_index = random.randint(0, len(i_json["reads"]) - 1)
        arrow_message = i_json["reads"][arrow_index]["message"]

        embedVar = discord.Embed(title=i_json["title"], description=arrow_message.format(user.mention), color=0xE91E63)
        embedVar.set_image(url=i_json["reads"][arrow_index]["image"])
        embedVar.set_footer(text=i_json["footer"])
        await message.channel.send(embed=embedVar)
      else:
        await message.channel.send(i_json["errors"][1])
    else:
      await message.channel.send(i_json["errors"][2])

  if(msg == '=open'):
    o_json = input_json["commands"]["=open"]["items"]
    user = message.author.id
    mention = message.author.mention
    profile = await get_user_profile(user)
    profile_json = json.loads(profile)

    if(profile_json['presents'] > 0):
      output = await open_presents(user, 1, profile_json)
      current_message = await message.channel.send("🎁 Opening your present(s)")
      this_message = await message.channel.fetch_message(current_message.id)
      cupid_animation_time = datetime.now() + timedelta(seconds=1)
      await discord.utils.sleep_until(cupid_animation_time)
      await this_message.edit(content="🎁 Opening your present(s).")
      cupid_animation_time = datetime.now() + timedelta(seconds=1)
      await discord.utils.sleep_until(cupid_animation_time)
      await this_message.edit(content="🎁 Opening your present(s)..")
      cupid_animation_time = datetime.now() + timedelta(seconds=1)
      await discord.utils.sleep_until(cupid_animation_time)
      await this_message.edit(content="🎁 Opening your present(s)...")
      cupid_animation_time = datetime.now() + timedelta(seconds=1)
      await discord.utils.sleep_until(cupid_animation_time)
      await this_message.delete()
      embed = await create_open_presents_embed(output, mention, message)
      await message.channel.send(embed=embed)
    else:
      await message.channel.send(o_json["errors"][0])

  if(msg.startswith('=profile')):
    message_parts = message.content.split("=profile ", 1)
    if(len(message_parts) > 1 and len(message.mentions) > 0):
      mention = message.mentions[0].mention
      user = message.mentions[0].id
      picture = message.mentions[0].avatar_url
    else:
      user = message.author.id
      mention = message.author.mention
      picture = message.author.avatar_url

    #get the profile  
    profile = await get_user_profile(user)

    if(profile == []):
      await message.channel.send("There is no profile for that user!")
      return

    embed = await create_profile_embed(profile, mention)
    embed.set_thumbnail(url=picture)
    await message.channel.send(embed=embed)

  if(msg.startswith('=clear')):
    message_parts = message.content.split("=clear ", 1)
    if(len(message_parts) > 1 and len(message.mentions) > 0):
      user = message.mentions[0].id
      await clear_user_profile(user)
      await message.channel.send("Cleared the profile!")

  if(msg.startswith('=make')):
    message_parts = message.content.split("=make ", 1)
    if(len(message_parts) > 1 and len(message.mentions) > 0):
      user = message.mentions[0].id
      await manage_user_profile(user, 0, 0, 1, 0, 0)
      await message.channel.send("made the profile!")

  #if(msg == '=clearserver'):
    #await clear_user_profile(client.this_guild)
    #await message.channel.send("Cleared the server profile!")

  if(msg.startswith('=spawn')):
    message_parts = message.content.split("=spawn ", 1)
    if(len(message_parts) > 1):
      spawn_id = int(message_parts[1])
      await spawn_cupid(spawn_id)
    else:
      await spawn_cupid()

  #if(msg.startswith('=die')):
    #await kill_cupid()

  if(message.channel.id != client.bot_channel_id and client.is_cupid_spawned == False):
    if(client.spawn_cupid == 0):
      client.spawn_cupid = random.randint(client.min_messages, client.max_messages)
      print("Reseting the count!")
    elif(client.spawn_cupid == client.current_cupid and client.is_cupid_spawned == False):
      print("Spawning the float with {0} : {1} : {2}".format(client.current_cupid, client.spawn_cupid, client.is_cupid_spawned))
      await spawn_cupid()
    else:
      if(client.last_message_from != message.author.id):
        print("Incrementing message for {0}".format(message.author.id))
        client.current_cupid += 1
        await manage_user_profile(message.author.id, 0, 0, 1, 0, 0)
        client.last_message_from = message.author.id


#Run the threads
keep_alive()
client.run(client.token)
