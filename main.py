from typing import Final, Dict
import os
from dotenv import load_dotenv
from discord import Intents, Client, Message, TextChannel
from responses import get_response
import asyncio
from datetime import datetime, timedelta

# STEP 0: LOAD TOKEN FROM SOMEWHERE SAFE
load_dotenv()
TOKEN: Final[str] = os.getenv("DISCORD_TOKEN")
current_daily_message_id = None
current_channel_id = None
user_numbers: Dict[int, int] = {}  # Maps user IDs to their submitted numbers

# STEP 1: BOT SETUP
intents: Intents = Intents.default()
intents.message_content = True  # NOQA
client: Client = Client(intents=intents)

# STEP 2: MESSAGE FUNCTIONALITY
async def send_message(message: Message, user_message: str) -> None:
    global current_channel_id

    if not user_message:
        print('(Message was empty because intents were not enabled properly)')
        return

    if is_private := user_message[0] == '?':
        user_message = user_message[1:]

    if user_message.lower().startswith('!setchannel'):
        try:
            new_channel_id = int(user_message.split()[1])
            current_channel_id = new_channel_id
            await message.channel.send(f'Channel changed to <#{client.get_channel(new_channel_id)}>')

        except (IndexError, ValueError):
            await message.channel.send('Invalid channel id use `!setchannel <channel_id>`.')
        return

    try:
        response: str = get_response(user_message)
        await message.author.send(response) if is_private else await message.channel.send(response)
    except Exception as e:
        print(e)

# STEP 3: HANDLING STARTUP FOR BOT
@client.event
async def on_ready() -> None:
    global current_channel_id
    print(f'{client.user} is now running!')

    for guild in client.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                current_channel_id = channel.id
                print(f'Default channel set to: {channel.name} (ID: {channel.id})')
                break
        if current_channel_id:
            break

    # Start daily message background task
    client.loop.create_task(daily_message_task())

# STEP 4: HANDLING INCOMING MESSAGES
@client.event
async def on_message(message: Message) -> None:
    if message.author == client.user:
        return

    username: str = str(message.author)
    user_message: str = message.content
    channel: str = str(message.channel)

    print(f'[{channel}] {username}: "{user_message}"')

    # Check if message is from the current channel and is a number
    if message.channel.id == current_channel_id and user_message.lstrip('-').isdigit():
        user_id = message.author.id
        user_message_value = int(user_message)

        # Initialize the user's number if not already present
        if user_id in user_numbers:
            user_numbers[user_id] += user_message_value
        else:
            user_numbers[user_id] = user_message_value

        # Update the daily message
        await update_daily_message()

        # Delete the user's message
        await message.delete()  # Deletes the user's message containing the number

        return

    await send_message(message, user_message)

async def update_daily_message():
    global current_daily_message_id

    if current_channel_id:
        channel: TextChannel = client.get_channel(current_channel_id)
        if channel:
            if current_daily_message_id:
                # Fetch the existing message
                daily_message = await channel.fetch_message(current_daily_message_id)
            else:
                # Send the initial message
                daily_message = await channel.send("Good morning! Here's your daily message.")
                current_daily_message_id = daily_message.id

            # Construct the new message content
            message_content = construct_daily_message()

            # Edit the daily message with the new content
            await daily_message.edit(content=message_content)

def construct_daily_message() -> str:
    now: datetime = datetime.now()
    date_str = now.strftime("%m/%d/%Y")  # Format: MM/DD/YYYY
    message_content = f"------------------ {date_str} --------------------\n"

    # Append user contributions to the message
    for user_id, number in user_numbers.items():
        user_mention = f"<@{user_id}>"
        message_content += f"{user_mention}: {number}\n"

    return message_content


# STEP 5: DAILY MESSAGE TASK
async def daily_message_task():
    await client.wait_until_ready()

    global current_daily_message_id

    while True:
        now: datetime = datetime.now()

        # Calculate time until the next scheduled time
        next_run = now.replace(hour=00, minute=17, second=0, microsecond=0)

        # Set next run to tomorrow if past the scheduled time
        if now > next_run:
            next_run = next_run + timedelta(days=1)

        # Calculate the time until the next run
        time_until_next_run: float = (next_run - now).total_seconds()

        # Wait until the specified time
        await asyncio.sleep(time_until_next_run)

        # Prepare the daily message with the date
        date_str = now.strftime("------ %m/%d/%Y ------")  # Adjust date format as needed
        daily_message_content = date_str

        # Send the message
        if current_channel_id:
            channel: TextChannel = client.get_channel(current_channel_id)
            if channel:
                # Send a new daily message
                daily_message = await channel.send(daily_message_content)
                current_daily_message_id = daily_message.id

                # Reset user numbers dictionary
                user_numbers.clear()  # Clear the user submissions
            else:
                print(f'Channel with ID {current_channel_id} was not found')


# STEP 6: MAIN ENTRY POINT
def main() -> None:
    client.run(token=TOKEN)

if __name__ == '__main__':
    main()
