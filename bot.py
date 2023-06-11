import os

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

DB = "linked_roles.db"
TOKEN = os.environ["LINKED_ROLES_TOKEN"]

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="..", intents=intents)


@bot.event
async def on_ready():
    if not os.path.exists(DB):
        print("Created DB file:", DB)
        with open(DB, "w") as f:
            f.write("")
    async with aiosqlite.connect(DB) as db:
        async with db.cursor() as cur:
            await cur.execute(
                """
            CREATE TABLE IF NOT EXISTS linked_roles(id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, role1_id INTEGER NOT NULL UNIQUE, role2_id INTEGER NOT NULL);
            """
            )
            await db.commit()
    await bot.tree.sync()
    print("Logged in as", bot.user)


@bot.tree.command(name="link-roles", description="Link two roles")
@app_commands.describe(role1="The role you apply")
@app_commands.describe(role2="The role that automatically gets added")
async def link_roles(
    interaction: discord.Interaction, role1: discord.Role, role2: discord.Role
):
    async with aiosqlite.connect(DB) as db:
        async with db.cursor() as cur:
            await cur.execute(
                f"""
            INSERT OR IGNORE INTO linked_roles(guild_id,role1_id,role2_id) VALUES({interaction.guild.id}, {role1.id}, {role2.id});
            """
            )
            await db.commit()
    await interaction.response.send_message(
        f"Members will automatically get {role2.mention} when they get {role1.mention}.",
        ephemeral=True,
        delete_after=15,
    )


@bot.tree.command(name="unlink-roles", description="Unlink two roles")
@app_commands.describe(role1="The role you apply")
@app_commands.describe(role2="The role that automatically gets added")
async def unlink_roles(
    interaction: discord.Interaction, role1: discord.Role, role2: discord.Role
):
    async with aiosqlite.connect(DB) as db:
        async with db.cursor() as cur:
            ulinked = await cur.execute(
                f"""
            DELETE FROM linked_roles WHERE guild_id={interaction.guild.id} AND role1_id={role1.id} AND role2_id={role2.id};
            """
            )
            await db.commit()
    if ulinked.rowcount > 0:
        await interaction.response.send_message(
            f"Members will no longer get {role2.mention} when they get {role1.mention}.",
            ephemeral=True,
            delete_after=15,
        )
    else:
        await interaction.response.send_message(
            f"{role2.mention} was not linked to {role1.mention}.  No changes made.",
            ephemeral=True,
            delete_after=15,
        )


@bot.tree.command(
    name="view-links", description="Display all the currently linked roles."
)
async def view_links(interaction: discord.Interaction):
    async with aiosqlite.connect(DB) as db:
        async with db.cursor() as cur:
            all_roles = await cur.execute(
                f"""
            SELECT role1_id,role2_id FROM linked_roles WHERE guild_id={interaction.guild.id};
            """
            )
            all_roles = await all_roles.fetchall()
    if len(all_roles) == 0:
        return await interaction.response.send_message(
            "No linked roles yet.", ephemeral=True, delete_after=15
        )
    else:
        linked_roles_list = []
        for role in all_roles:
            role1 = interaction.guild.get_role(role[0])
            role2 = interaction.guild.get_role(role[1])
            linked_roles_list.append(
                f"Members get {role2.mention} when given {role1.mention}.\n"
            )
        await interaction.response.send_message(
            f"Current linked roles:\n{''.join(linked_roles_list)}", ephemeral=True
        )


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    async with aiosqlite.connect(DB) as db:
        async with db.cursor() as cur:
            linked_roles = await cur.execute(
                f"SELECT role1_id,role2_id FROM linked_roles WHERE guild_id={after.guild.id};"
            )
            linked_roles = await linked_roles.fetchall()
    # add role2 when role1 is found
    for member_role in after.roles:
        if member_role == after.guild.default_role:
            continue
        for role in linked_roles:
            if role[0] == member_role.id:
                linked_role_to_give = after.guild.get_role(role[1])
                await after.add_roles(linked_role_to_give)
                break
    # rem role2 when role1 is removed
    lost_roles = [role for role in before.roles if role not in after.roles]
    if len(lost_roles) > 0:
        for role in linked_roles:
            if lost_roles[0].id == role[0]:
                linked_role_to_remove = after.guild.get_role(role[1])
                await after.remove_roles(linked_role_to_remove)


bot.run(TOKEN)
