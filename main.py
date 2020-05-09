from decouple import config
import discord # https://pypi.org/project/discord.py/
from discord.ext import commands
import json
import os.path
import threading
import datetime
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
CHANNEL_TARGET = config("CHANNEL_TO_POST", default="")
HOUR_OF_FLASH_NEWS = int(config("HOUR_OF_FLASH_NEWS", default=datetime.datetime.now().hour)) % 24
QUIP_ON_NEWS = config("QUIP_ON_NEWS", default="on_multiple_news")

if QUIP_ON_NEWS == "yes":
    QUIP_ON_NEWS = 1
elif QUIP_ON_NEWS == "on_multiple_news":
    QUIP_ON_NEWS = 2
else:
    QUIP_ON_NEWS = 0

configuration = {
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

def create_logger:
    log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')

    file_handler = RotatingFileHandler(LOGGING_PATH, mode='w', maxBytes=5*1024*1024, 
                                     backupCount=2, encoding=None, delay=0)
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.DEBUG)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(log_formatter)
    stdout_handler.setLevel(logging.DEBUG)

    app_log = logging.getLogger('root')
    app_log.setLevel(logging.DEBUG)

    app_log.addHandler(file_handler)
    app_log.addHandler(stdout_handler)

    return app_log

app_log = create_logger

def exception_handler(type, value, tb):
    app_log.exception("Uncaught exception: {0}".format(str(value)))

sys.excepthook = exception_handler
threading.excepthook = exception_handler

def cleanup_summary(summary):
    return BeautifulSoup(summary.replace("<br>", '\n'), "lxml").text

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

quip_counter = 0
def get_quip():
        quip = ["Today I bring _SHOCKING NEWS_  to you !"]
        quip_counter = quip_counter + 1 % len(quip)
        return quip[quip_counter]

def append_quip(messages):
    global QUIP_ON_NEWS
    
    if len(messages) > 0:
        if QUIP_ON_NEWS == 1:
            messages.insert(0, get_quip())
        elif QUIP_ON_NEWS == 2 and messages > 1:                                                    
            messages.insert(0, get_quip())
    return messages
                                        
async def pull_news(ctx=None):
    global configuration
    app_log.info("pulling news !")

    messages = []
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
        messages = append_quip(messages)
        for msg in messages:
            await ctx.send(msg)
                                                            
        if len(url_errored) > 0:
                await ctx.send("Sorry these url(s) failed: {0}".format(str(url_errored)))

    configuration["last_run"] = str(datetime.datetime.now())
    with open(CONFIGURATION_PATH, "w") as f:
        json.dump(configuration, f)

async def pull_last_news(ctx=None):
    app_log.info("pulling last news !")

    messages = []
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
        if len(messages) > 0: 
            messages = append_quip(messages)    
            for message in messages:
                await local_ctx.send(message)
        else:
            await local_ctx.send("No news to post ! :(")
        
        if len(url_errored) > 0:
                await local_ctx.send("Sorry these url(s) failed: {0}".format(str(url_errored)))

async def pull_news_at_interval():
    date_now = datetime.datetime.now()
    if date_now.hour > HOUR_OF_FLASH_NEWS: 
        date_now = date_now + datetime.timedelta(days=1)
    
    date_now = date_now.replace(hour=HOUR_OF_FLASH_NEWS, minute=0)
    second_to_wait = abs(date_now - datetime.datetime.now()).total_seconds() 

    app_log.info("next flash news in {0} hours".format(second_to_wait / 3600))
    await asyncio.sleep(second_to_wait)
    await pull_news()
    asyncio.create_task(pull_news_at_interval())

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
    app_log.info("initialize link done")
    asyncio.create_task(pull_news_at_interval())
    app_log.info("task launched")
    
@bot.command(name='last_news', help='Fetch and post lastest news from each urls')
async def _pull_news(ctx):
    await pull_last_news(ctx)

@bot.command(name="last", help='Fetch and post lastest news from each urls')
async def _pull(ctx):
    await pull_last_news(ctx)

@bot.command(name="status", help='Display current bot status')
async def _status(ctx):
    if "chan_target_id" not in configuration:
       await ctx.send("Sorry, could not find the designated channel to post in")
    await ctx.send("OK!")

@_pull_news.error
@_pull.error
@_status.error
async def _pull_news_error(ctx, error):
    app_log.exception("Uncaught exception: {0}".format(str(error)))

bot.run(DISCORD_TOKEN)
