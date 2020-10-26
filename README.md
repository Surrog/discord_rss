# discord_rss
A discord bot that fetch RSS and post it to a specific channel

## Resources

Tuto: https://realpython.com/how-to-make-a-discord-bot-python/

Doc: 
https://pypi.org/project/discord.py/

https://pypi.org/project/python-decouple/

## Commands

```
/help: display this help message
/last, /last_news: trigger a flash news right now
/status: display the current bot operational status
```

## Installation Guide
+ Clone this repository on your server
+ Create your bot on the discord bot interface to generate a valid bot token id
+ Create a `.env` file in the directory folder where you cloned this repository
+ Edit the `.env` with these configuration keys:
```
DISCORD_TOKEN=<token> # token id given by discord
CONFIGURATION_PATH=<filepath> (default="discord_rss_config.json") # filepath where the bot store its last actions
LOGGING_PATH=<filepath> (default="discord_rss.log") # filepath where the bot log is dumped
COMMAND_PREFIX=<character> (default='/') # character prefix to start a command dedicate to this bot
URL_LIST=<url>[, <url>, ...] # urls to rss separated by a ','
CHANNEL_TO_POST=<string> (default="") # channel name where the bot will post news
HOUR_OF_FLASH_NEWS=<number> (default=the current hour at which the bot is started) # the hour at which the bot will fetch the news
QUIP_ON_NEWS=<yes | no | on_multiple_news> (default=on_multiple_news)  # If the bot add a small quip when news are being posted
SALES = <yes | no> (default=no) # If the bot remove news that contain the word "sales"
```
+ Build the docker image: `sudo docker build -t <yourname>  .`
+ Run the docker image built with the .env: `sudo docker run -d --restart unless-stopped --name <yourinstancename> --env-file .env -e TZ=Europe/Paris <yourname>`
