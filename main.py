from decouple import config
import random
import discord # https://pypi.org/project/discord.py/
from discord.ext import commands
import json
import os.path
import threading
import datetime
import dateutil.parser
import feedparser
import asyncio
from bs4 import BeautifulSoup
from time import mktime

DISCORD_TOKEN = config('DISCORD_TOKEN')
CONFIGURATION_PATH = config('CONFIGURATION_PATH')
COMMAND_PREFIX = config('COMMAND_PREFIX', default='/')
URLS = config("URL_LIST")
INTERVAL = int(config("INTERVAL_SECOND", default="86400")) # number of second in a day
CHANNEL_TARGET = config("CHANNEL_TO_POST", default="")

configuration = {
    "interval_second": int(INTERVAL),
    "url_list": [item.strip() for item in URLS.split(',')],
    "link_done": {}
}

if (os.path.isfile(CONFIGURATION_PATH)):
    with open(CONFIGURATION_PATH, "r") as f:
        configuration = json.load(f)
else:
    with open(CONFIGURATION_PATH, "w") as f:
        json.dump(configuration, f)

def cleanup_summary(summary):
    return BeautifulSoup(summary, "lxml").text

def news_before_date(previous_run, date):
    return previous_run is None or date is None or previous_run < date

bot = commands.Bot(command_prefix=COMMAND_PREFIX)

async def pull_news():
    global configuration
    print("pulling news !")
    date_now = datetime.datetime.now()
    previous_run = None
    if "last_run" in configuration:
        previous_run = dateutil.parser.parse(configuration["last_run"])

    for url in configuration["url_list"]:
        print("pulling from " + url)
        feed = feedparser.parse(url)
        if feed["bozo"] == 0:
            if url not in configuration["link_done"]:
                configuration["link_done"][url] = []
            
            for item in feed["items"]:
                date = None
                if "date_parsed" in item:
                    date = datetime.datetime.fromtimestamp(mktime(item["date_parsed"]))
                elif "published_parsed" in item:
                    date = datetime.datetime.fromtimestamp(mktime(item["published_parsed"]))
                elif "date" in item:
                    date = dateutil.parser.parse(item["date"])
                elif "published" in item:
                    date = dateutil.parser.parse(item["published"])
                                        
                if news_before_date(previous_run, date) and item["link"] not in configuration["link_done"][url]:
                    message = "**" + item["title"] + "**\n"
                    message += cleanup_summary(item["summary"]) + '\n'
                    message += item["link"]
                    if "chan_target_id" in configuration:
                        await bot.get_channel(configuration["chan_target_id"]).send(message)
                        configuration["link_done"][url].append(item["link"])

            if len(configuration["link_done"][url]) > 20:
                configuration["link_done"][url] = configuration["link_done"][url][-19:]
            
        else:
            print("feedparser failed : " + str(feed["bozo"])) 

    if "chan_target_id" in configuration:
        configuration["last_run"] = str(date_now)
        with open(CONFIGURATION_PATH, "w") as f:
            json.dump(configuration, f)

timer = None
async def pull_news_at_interval():
    await asyncio.sleep(configuration["interval_second"])
    await pull_news()
    await pull_news_at_interval()

@bot.event
async def on_ready():
    print(f'{bot.user.name} is now connected to Discord')
    global configuration
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.name == CHANNEL_TARGET:
                print("found channel: " + channel.name)
                configuration["chan_target_id"] = channel.id
    if "chan_target_id" not in configuration:
        print("can't find channel: " + CHANNEL_TARGET)
    else:
        await bot.get_channel(configuration["chan_target_id"]).send("posting here")
    await pull_news()
    await pull_news_at_interval()

@bot.command(name='pull_news', help='fetch news')
async def _pull_news(ctx):
    await ctx.send("fetching news now !")
    await pull_news()

@bot.command(name="pull", help='pull news : fetc news')
async def _pull(ctx, arg):
    if arg == "news":
        await _pull_news(ctx)

bot.run(DISCORD_TOKEN)
