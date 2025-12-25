# Discord Bot Setup Guide

This guide walks you through creating a Discord bot, inviting it to your server, and getting the necessary credentials for gcal-to-discord.

## Prerequisites

- A Discord account
- Administrator permissions on the Discord server where you want to add the bot
- Access to the Discord Developer Portal

## Step 1: Create a Discord Application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"** in the top right
3. Enter a name for your application (e.g., "gcal2disc")
4. Accept the Terms of Service and click **"Create"**

## Step 2: Create a Bot User

1. In your application page, click **"Bot"** in the left sidebar
2. Click **"Add Bot"**
3. Click **"Yes, do it!"** to confirm
4. **Important**: Under the bot settings, ensure the following:
   - **Public Bot**: Toggle OFF if you only want to use it in your own servers
   - **Requires OAuth2 Code Grant**: Leave OFF
   - **Privileged Gateway Intents**: All can remain OFF (we don't need privileged intents)

## Step 3: Get Your Bot Token

1. Under the bot settings, find the **"TOKEN"** section
2. Click **"Reset Token"** (or "Copy" if you haven't reset it yet)
3. Click **"Yes, do it!"** to confirm
4. Click **"Copy"** to copy your bot token
5. **Save this token securely** - you'll need it for the `DISCORD_BOT_TOKEN` environment variable
6. ⚠️ **Never share this token publicly** - treat it like a password

## Step 4: Configure Bot Permissions

1. In the left sidebar, click **"OAuth2"** → **"URL Generator"**
2. Under **"SCOPES"**, select:
   - ✅ `bot`
3. Under **"BOT PERMISSIONS"**, select:
   - ✅ `Send Messages` - Required to post calendar events
   - ✅ `Embed Links` - Required to create rich embeds
   - ✅ `Read Message History` - Required to check for existing events

   The permissions integer should be: **76800**

4. Copy the generated URL at the bottom of the page

## Step 5: Invite Bot to Your Server

1. Paste the URL from Step 4 into your browser
2. Select the server where you want to add the bot from the dropdown
3. Click **"Continue"**
4. Review the permissions and click **"Authorize"**
5. Complete the CAPTCHA verification
6. You should see a confirmation that the bot has been added

## Step 6: Get Your Channel ID

You need to enable Developer Mode in Discord to see channel IDs.

### Enable Developer Mode

1. Open Discord
2. Click the **gear icon** (User Settings) in the bottom left
3. Go to **"Advanced"** under "App Settings"
4. Toggle **"Developer Mode"** ON
5. Close settings

### Get Channel ID

1. Navigate to the server where you added your bot
2. Find the text channel where you want calendar events posted
3. Right-click on the channel name
4. Click **"Copy Channel ID"**
5. **Save this ID** - you'll need it for the `DISCORD_CHANNEL_ID` environment variable

The channel ID will be a long number like: `1024131739368575069`

## Step 7: Verify Bot Permissions in Channel

Make sure your bot has permission to access and post in the target channel:

1. Right-click on the target channel
2. Select **"Edit Channel"**
3. Go to **"Permissions"** tab
4. Find your bot in the members/roles list (or add it)
5. Ensure these permissions are allowed (green checkmark):
   - ✅ View Channel
   - ✅ Send Messages
   - ✅ Embed Links
   - ✅ Read Message History

6. Click **"Save Changes"**

## Step 8: Configure gcal-to-discord

Add the following to your `.env` file:

```env
DISCORD_BOT_TOKEN=your_bot_token_from_step_3
DISCORD_CHANNEL_ID=your_channel_id_from_step_6
```

Example:
```env
DISCORD_BOT_TOKEN=MTQ1Mzg1OTYzNTkxNTM5MTA4MA.GxK9zY.example_token_do_not_share
DISCORD_CHANNEL_ID=1024131739368575069
```

## Step 9: Test Your Bot

1. Make sure your bot is online (you should see it in your server's member list with a green status)
2. Run gcal-to-discord:
   ```bash
   uv run gcal-to-discord --once
   ```
3. Check the target channel for calendar event messages

## Troubleshooting

### Bot appears offline
- Verify the bot token is correct
- Check that you're running gcal-to-discord
- Review application logs for connection errors

### "Missing Access" or "Unknown Channel" error
- Verify the channel ID is correct
- Ensure the bot has been invited to the server
- Check channel permissions (Step 7)

### Bot can't send messages
- Verify "Send Messages" permission is enabled
- Check if the channel has any restrictions
- Ensure the bot role isn't being overridden by channel-specific permissions

### Bot is sending messages but they look broken
- Verify "Embed Links" permission is enabled
- Check that MESSAGE_PREFIX (if set) doesn't contain invalid characters

## Security Best Practices

1. **Never commit your bot token** - Keep it in `.env` and ensure `.env` is in your `.gitignore`
2. **Rotate tokens if exposed** - If you accidentally share your token, reset it immediately in the Developer Portal
3. **Use minimal permissions** - Only grant the permissions your bot actually needs
4. **Restrict bot to specific channels** - Use channel permissions to limit where the bot can post
5. **Regular audits** - Periodically review your bot's permissions and access

## Additional Resources

- [Discord Developer Documentation](https://discord.com/developers/docs)
- [Discord Bot Best Practices](https://discord.com/developers/docs/topics/community-resources#bots-and-apps)
- [Discord API Support Server](https://discord.gg/discord-api)

## Getting Help

If you encounter issues:
1. Check the troubleshooting section above
2. Review gcal-to-discord logs for error messages
3. Open an issue on the [GitHub repository](https://github.com/yourusername/gcal-to-discord/issues)
