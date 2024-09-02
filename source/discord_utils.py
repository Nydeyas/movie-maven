from typing import Optional, Union

import logging

from discord import Emoji, Reaction, PartialEmoji, Message, Embed, HTTPException, Forbidden, NotFound, TextChannel, \
    File


async def delete_message(message: Message) -> None:
    try:
        await message.delete()
    except NotFound as err:
        logging.warning(f"Failed to delete message. Message not found: {err}.")
    except Forbidden as err:
        logging.error(f"Failed to delete message. Forbidden: {err}.")
    except HTTPException as err:
        logging.error(f"Failed to delete message. HTTPException: {err}", exc_info=True)
    return


async def edit_message(
        message: Message,
        content: Optional[str] = None,
        embed: Optional[Embed] = None
) -> Message | None:
    try:
        msg = await message.edit(content=content, embed=embed)
        return msg
    except NotFound as err:
        logging.warning(f"Failed to edit message. Message not found: {err}.")
    except ValueError as err:
        logging.error(f"Failed to edit message. The length of embeds was invalid: {err}.")
    except Forbidden as err:
        logging.error(f"Failed to edit message. Forbidden: {err}.")
    except HTTPException as err:
        logging.error(f"Failed to edit message. HTTPException: {err}", exc_info=True)
    return None


async def fetch_message(channel: TextChannel, message_id: int) -> Message | None:
    try:
        fetched_message = await channel.fetch_message(message_id)
        return fetched_message
    except NotFound as err:
        logging.warning(f"Failed to fetch_message. Message with ID {message_id} not found in channel {channel}. {err}")
    except Forbidden as err:
        logging.error(f"Failed to fetch_message. Forbidden: {err}.")
    except HTTPException as err:
        logging.error(f"Failed to fetch message. HTTPException: {err}", exc_info=True)
    return None


async def send_message(
        channel: TextChannel,
        content: Optional[str] = None,
        embed: Optional[Embed] = None,
        file: Optional[File] = None
) -> Message | None:
    try:
        msg = await channel.send(content=content, embed=embed, file=file)
        return msg
    except ValueError as err:
        logging.error(f"Failed to send message. The length of embeds was invalid: {err}.")
    except Forbidden as err:
        logging.error(f"Failed to send message. Forbidden: {err}.")
    except HTTPException as err:
        logging.error(f"Failed to send message. HTTPException: {err}", exc_info=True)
    return None


async def add_reaction(message: Message, emoji: Union[Emoji, Reaction, PartialEmoji, str]) -> None:
    try:
        await message.add_reaction(emoji)
    except NotFound as err:
        logging.warning(f"Failed to add reaction. Message not found: {err}.")
    except Forbidden as err:
        logging.error(f"Failed to add reaction. Forbidden: {err}.")
    except TypeError as err:
        logging.error(f"Failed to add reaction. Emoji parameter is invalid.: {err}.")
    except HTTPException as err:
        logging.error(f"Failed to add reaction. HTTPException: {err}", exc_info=True)
    return


async def clear_reactions(message: Message) -> None:
    try:
        await message.clear_reactions()
    except NotFound as err:
        logging.warning(f"Failed to clear reactions. Message not found: {err}.")
    except Forbidden as err:
        logging.error(f"Failed to clear reactions. Forbidden: {err}.")
    except HTTPException as err:
        logging.error(f"Failed to clear reactions. HTTPException: {err}", exc_info=True)
    return
