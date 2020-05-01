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
import logging
from logging.handlers import RotatingFileHandler
import sys
from bs4 import BeautifulSoup
from time import mktime

DISCORD_TOKEN = config("DISCORD_TOKEN")
CONFIGURATION_PATH = config("CONFIGURATION_PATH", default="discord_rss_config.json")
LOGGING_PATH = config("LOGGING_PATH", default="discord_rss.log")
COMMAND_PREFIX = config("COMMAND_PREFIX", default='/')
URLS = config("URL_LIST")
INTERVAL = int(config("INTERVAL_SECOND", default="86400")) # number of second in a day
CHANNEL_TARGET = config("CHANNEL_TO_POST", default="")

configuration = {
    "interval_second": int(INTERVAL),
    "url_list": [item.strip() for item in URLS.split(',')],
    "link_done": {},
    "last_run": str(datetime.datetime.now())
}

if (os.path.isfile(CONFIGURATION_PATH)):
    with open(CONFIGURATION_PATH, "r") as f:
        previous = json.load(f)
        configuration["last_run"] = previous["last_run"]
        configuration["link_done"] = previous["link_done"]
    
with open(CONFIGURATION_PATH, "w") as f:
    json.dump(configuration, f)

log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')

my_handler = RotatingFileHandler(LOGGING_PATH, mode='w', maxBytes=5*1024*1024, 
                                 backupCount=2, encoding=None, delay=0)
my_handler.setFormatter(log_formatter)
my_handler.setLevel(logging.INFO)

app_log = logging.getLogger('root')
app_log.setLevel(logging.INFO)

app_log.addHandler(my_handler)

def exception_handler(type, value, tb):
    app_log.exception("Uncaught exception: {0}".format(str(value)))

sys.excepthook = exception_handler
threading.excepthook = exception_handler

def cleanup_summary(summary):
    return BeautifulSoup(summary.replace("<br>", '\n'), "lxml").text

def news_before_date(previous_run, date):
    return previous_run is None or date is None or previous_run < date

bot = commands.Bot(command_prefix=COMMAND_PREFIX)

async def fetch_initial_link():
    for url in configuration["url_list"]:
        feed = feedparser.parse(url)
        if feed["bozo"] == 0:
            if url not in configuration["link_done"]:
                configuration["link_done"][url] = []
            
            for item in feed["items"]:   
                if item["link"] not in configuration["link_done"][url]:
                    configuration["link_done"][url].append(item["link"])

def format_message(item):
    message = "__**" + item["title"] + "**__\n"
    message += cleanup_summary(item["summary"]) + '\n'
    limit = 1900 - len(item["link"]) - len("...")

    if len(message) > limit:
        message = message[:limit] + "...";

    if item["link"] not in message:
        message += item["link"]
    return message

async def pull_news(ctx=None):
    global configuration
    app_log.info("pulling news !")

    messages = ["Today I bring _SHOCKING NEWS_  to you !"]
    url_errored = []

    if ctx is None and "chan_target_id" in configuration:
        ctx =  bot.get_channel(configuration["chan_target_id"])

    for url in configuration["url_list"]:
        app_log.info("pulling from " + url)
        feed = feedparser.parse(url)
        if feed["bozo"] == 0:
            message = ""
            for item in feed["items"]:
                if item["link"] not in configuration["link_done"][url]:
                    message = format_message(item)
                    if len(message):
                        messages.append(message)            
                    configuration["link_done"][url].append(item["link"])

            if len(configuration["link_done"][url]) > 20:
                configuration["link_done"][url] = configuration["link_done"][url][-19:]           
        else:
            app_log.warning("feedparser failed to parse {0} ".format(url))
            url_errored.append(url)

    if ctx is not None:
        if len(messages) > 1:
            for message in messages:
                await ctx.send(message)
        
        if len(url_errored) > 0:
                await ctx.send("Sorry these url(s) failed: {0}".format(str(url_errored)))

    configuration["last_run"] = str(datetime.datetime.now())
    with open(CONFIGURATION_PATH, "w") as f:
        json.dump(configuration, f)

async def pull_last_news(ctx=None):
    app_log.info("pulling last news !")

    messages = ["Today I bring _SHOCKING NEWS_  to you !"]
    url_errored = []

    local_ctx = None
    if ctx is None and "chan_target_id" in configuration:
        local_ctx =  bot.get_channel(configuration["chan_target_id"])
    else:
        local_ctx = ctx

    for url in configuration["url_list"]:
        app_log.info("pulling from " + url)
        feed = feedparser.parse(url)
        if feed["bozo"] == 0:
            if url not in configuration["link_done"]:
                configuration["link_done"][url] = []
            
            message = ""
            if len(feed["items"]) > 0:
                message = format_message(feed["items"][0])
            
            if len(message):
                messages.append(message)
        else:
            app_log.warning("feedparser failed to parse {0} ".format(url))
            url_errored.append(url)

    if local_ctx is not None:
        if len(messages) > 1:
            for message in messages:
                await local_ctx.send(message)
        elif ctx is not None:
            await local_ctx.send("No news to post ! :(")
        
        if len(url_errored) > 0:
                await local_ctx.send("Sorry these url(s) failed: {0}".format(str(url_errored)))

timer = None
async def pull_news_at_interval():
    await asyncio.sleep(configuration["interval_second"])
    await pull_news()
    await pull_news_at_interval()

@bot.event
async def on_ready():
    app_log.info(f'{bot.user.name} is now connected to Discord')
    global configuration
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.name == CHANNEL_TARGET:
                app_log.info("found channel: " + channel.name)
                configuration["chan_target_id"] = channel.id
    if "chan_target_id" not in configuration:
        app_log.warning("can't find channel: " + CHANNEL_TARGET)
    await fetch_initial_link()
    await pull_news_at_interval()

@bot.command(name='last_news', help='Fetch and post lastest news from each urls')
async def _pull_news(ctx):
    await pull_last_news(ctx)

@bot.command(name="last", help='Fetch and post lastest news from each urls')
async def _pull(ctx, arg):
    if arg == "news":
        await _pull_news(ctx)

@bot.command(name="status", help='Display current bot status')
async def _status(ctx, arg):
    if "chan_target_id" not in configuration:
       await ctx.send("Sorry, could not find the designated channel to post in")

@_pull_news.error
@_pull.error
async def _pull_news_error(ctx, error):
    app_log.exception("Uncaught exception: {0}".format(str(error)))

bot.run(DISCORD_TOKEN)
