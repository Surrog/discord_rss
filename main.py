from decouple import config
import random
import discord # https://pypi.org/project/discord.py/
from discord.ext import commands
import json
import os.path
import threading
import datetime
import dateutil
import requests
from xml.etree import ElementTree

DISCORD_TOKEN = config('DISCORD_TOKEN')
CONFIGURATION_PATH = config('CONFIGURATION_PATH')
COMMAND_PREFIX = config('COMMAND_PREFIX', default='/')

interval = 86400 # number of second in day

configuration = {
    "interval_second": str(interval),
    "url_list": []
}

if (os.path.isfile(CONFIGURATION_PATH)):
    print("config file " + CONFIGURATION_PATH + " found")
    with open(DATAFILE_PATH, "r") as f:
        configuration = json.load(f)
else:
    with open(CONFIGURATION_PATH, "w") as f:
        print("config file " + CONFIGURATION_PATH + " not found, generating one now")
        json.dump(configuration, f)
        print("configuration file " + CONFIGURATION_PATH + " created, ending now")
        exit()

def pull_news():
    print("pulling news !")
    date_now = datetime.datetime.now()
    previous_run = None
    if "last_run" in configuration:
        previous_run = dateutil.parser.parse(configuration["last_run"])

    for url in configuration["url_list"]:
        r_result = requests.get(url)
        if r_result.status_code == requests.codes.ok:
            tree = ElementTree.fromstring(r_result.content)
            for val in tree:
                print(val)

timer = None
def pull_news_at_interval():
    pull_news()
    timer = threading.Timer(int(configuration["interval_second"]), pull_news_at_interval)
    timer.start()
    return

bot = commands.Bot(command_prefix=COMMAND_PREFIX)

@bot.event
async def on_ready():
    print(f'{bot.user.name} is now connected to Discord')
    pull_news_at_interval()

@bot.command(name='pull news', help='fetch news')
async def _pull_news(ctx):
    await ctx.send("fetching news now !")
    pull_news()

bot.run(DISCORD_TOKEN)
