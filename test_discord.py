import discord
print("Discord version:", discord.__version__)
print("Module path:", discord.__file__)
print("Has attribute 'Bot':", hasattr(discord, "Bot"))
print("List of attributes:", dir(discord))
