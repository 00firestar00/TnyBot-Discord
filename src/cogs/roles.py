from typing import List, Tuple

from discord import Forbidden, Message, Member, Role
from discord.ext import commands
from discord.ext.commands import Context, BadArgument
from discord.ext.commands.converter import RoleConverter

from src.cogs import BaseDBCog
from src.database import RolesDB


class Roles(BaseDBCog):
    def __init__(self, bot, db_file="res/roles.db", db_url=None):
        super().__init__(bot, RolesDB(db_file, db_url))

    async def on_server_role_delete(self, role: Role):
        await self.database.delete(role)

    @commands.group(pass_context=True, aliases=["biashelp"])
    async def roleshelp(self, ctx):
        """Shows the help information for self assigned roles
        """
        if ctx.invoked_subcommand is None:
            role = "role"
            plural = "s"
            if "bias" in ctx.invoked_with:
                role = "bias"
                plural = "es"

            msg = []
            msg.append("```")
            msg.append("Hello! I let you assign your own {1}{2}!")
            msg.append("Use: {0}{1} to add the {1}{2} you want.")
            msg.append("Example: {0}{1} lions, tigers, bears")
            msg.append("Hint: You can also add them individually if you want...")
            msg.append("")
            msg.append("If you want to add a main {1}, you have to use {0}main{1}.")
            msg.append("You can only have one of these, and it will be the prominent color.")
            msg.append("Example: {0}main{1} robots")
            msg.append("```")
            await self.bot.say("\n".join(msg).format(ctx.prefix, role, plural))

    @roleshelp.command(pass_context=True, aliases=["mod"])
    @commands.has_permissions(manage_roles=True)
    async def admin(self, ctx):
        """Shows the help information for creating self assigned roles
        """
        role = "role"
        plural = "s"
        if "bias" in ctx.invoked_with:
            role = "bias"
            plural = "es"

        msg = []
        msg.append("```")
        msg.append("To get started, give me permission to manage roles, and delete messages.")
        msg.append("I should have been added with these roles, so just check for a `TnyBot` role.")
        msg.append("")
        msg.append("Next, you need to create a list of {1}{2} members can add.")
        msg.append("Use: {0}set{1} Role=Alias, Role2=Alias2")
        msg.append("Example: {0}set{1} robots=robits, dogs=doge, lions, tigers, bears=beers")
        msg.append("")
        msg.append("If you want to enforce 1 {1} per user, then use {0}setmain{1}")
        msg.append("The Member will be prompted if they want to swap {1}{2}.")
        msg.append("")
        msg.append("Hint: {1}{2}, and main{1}{2} can share the same alias.")
        msg.append("To make it easier to add roles, you can allow @mentions and just mention each role you want to add")
        msg.append("```")
        await self.bot.say("\n".join(msg).format(ctx.prefix, role, plural))

    @commands.command(pass_context=True, aliases=["setbias"])
    @commands.has_permissions(manage_roles=True)
    async def setrole(self, ctx, *, roles):
        """Sets a role, or list of roles as self assigned roles
        """
        rows = await self._parse_roles(ctx, roles)
        await self.database.bulk_insert(rows)
        await self.bot.say("Done! Use listroles to check what you added")

    @commands.command(pass_context=True, aliases=["listbias", "listbiases", "listroles", "lsar"])
    async def listrole(self, ctx):
        """Lists the roles created with setrole command
        """
        server = ctx.message.server
        all_roles = await self.database.get_all_regular(server)
        role_names = await self._format_roles(ctx, all_roles)
        if not role_names:
            await self.bot.say("There are no self assigning roles on this server")
        else:
            await self.bot.say("\n".join(role_names))

    @commands.command(pass_context=True, aliases=["setmainbias", "addmainbias", "addmainrole"])
    @commands.has_permissions(manage_roles=True)
    async def setmainrole(self, ctx, *, roles):
        """Sets a role, or list of roles as self assigned main roles
        """
        rows = await self._parse_roles(ctx, roles, is_primary=1)
        await self.database.bulk_insert(rows)
        await self.bot.say("Done! Use listmainroles to check what you added")

    @commands.command(pass_context=True, aliases=["listmainbias", "listmainbiases", "listmainroles"])
    async def listmainrole(self, ctx):
        """Lists the roles created with setmainrole command
        """
        server = ctx.message.server
        all_roles = await self.database.get_all_main(server)
        role_names = await self._format_roles(ctx, all_roles)
        if not role_names:
            await self.bot.say("There are no self assigning roles on this server")
        else:
            await self.bot.say("\n".join(role_names))

    @commands.command(pass_context=True, aliases=["delmainrole", "delmainbias", "delbias", "rsar"])
    @commands.has_permissions(manage_roles=True)
    async def delrole(self, ctx, *, roles):
        """Deletes a self assigned role
        """
        rows = await self._parse_roles(ctx, roles, is_primary=1)
        await self.database.bulk_delete(rows)
        await self.bot.say("Done!")

    @commands.command(pass_context=True, aliases=["mainbias", "primary", "toprole", "main", "primaryrole"])
    async def mainrole(self, ctx, *, alias):
        """Add a primary role. Only one of these roles can be added to a member
        """
        message = ctx.message
        server = message.server

        role_id = await self.database.get(server, alias, is_primary=1)
        if role_id is None:
            await self.bot.say("That role isn't something I can add")
            return

        role_conv = await self._role_convert(ctx, role_id)
        if role_conv is None:
            await self.bot.say("That role isn't something I can add")
            return

        db_roles = await self.database.get_all_main(server)
        main_roles = []
        for role_id, alias in db_roles:
            main_roles.append(role_id)

        members = await self._get_members_from_message(message)
        for m in members:
            if role_conv in m.roles:
                await self.bot.say("{0.mention} already has {1.name} as their main role".format(m, role_conv))

            for r in m.roles:
                if r.id in main_roles:
                    if r.id == role_conv.id:
                        await self.bot.say("{0.mention} already has `{1.name}` as their main role".format(m, role_conv))
                        continue

                    bot_message = await self.bot.say(
                        "{0.mention} already has a main role, would you like to change it to `{1.name}`? Y/N".format(
                            m, role_conv))
                    reply = await self.bot.wait_for_message(timeout=5.0, author=message.author)
                    if reply and reply.content.lower() in ["yes", "y"]:
                        await self.bot.remove_roles(m, r)
                    else:
                        await self.bot.delete_message(bot_message)
                        continue
            try:
                await self.bot.add_roles(m, role_conv)
                await self.bot.say("Adding {0.mention} to `{1.name}`".format(m, role_conv))
            except Forbidden:
                await self.bot.say("Oops, something happened, I don't have permission to give that role.")

    @commands.command(pass_context=True, aliases=["iam", "bias", "sub"])
    async def role(self, ctx, *, all_alias):
        """Add a role. A member can have any number of these roles
        """
        server = ctx.message.server
        all_alias = all_alias.rstrip(", \t\n\r")
        alias_arr = all_alias.split(",")
        members = await self._get_members_from_message(ctx.message)
        for m in members:
            roles_arr = []
            for a in alias_arr:
                alias = a.replace(m.mention, "").strip(" \t\n\r\"'")
                role_id = await self.database.get(server, alias)
                if role_id is None:
                    await self.bot.say("{} isn't something I can add".format(a))
                    continue

                role_conv = await self._role_convert(ctx, role_id)
                if role_conv is not None:
                    roles_arr.append(role_conv)

            try:
                if not roles_arr:
                    continue
                await self.bot.add_roles(m, *roles_arr)
                say = "Adding {0.mention} to ".format(m)
                for r in roles_arr:
                    say += "`{0.name}` ".format(r)
                await self.bot.say(say)
            except Forbidden:
                await self.bot.say("Oops, something happened, I don't have permission to give that role.")

    @commands.command(pass_context=True, aliases=["clearbias"])
    async def clearrole(self, ctx):
        """Clears all self assigned roles from you, or the listed members
        """
        message = ctx.message
        server = message.server
        db_roles = await self.database.get_all(server)
        listed_roles = []
        for role_id, alias in db_roles:
            listed_roles.append(role_id)
        members = await self._get_members_from_message(message)
        for m in members:
            member_roles = m.roles
            for r in m.roles:
                if r.id not in listed_roles:
                    member_roles.remove(r)
            bot_message = await self.bot.say(
                "This will clear all roles for: {0.mention}. Are you sure you want to do that? Y/N".format(m))
            reply = await self.bot.wait_for_message(timeout=5.0, author=message.author)
            if reply and reply.content.lower() in ["yes", "y"]:
                try:
                    await self.bot.remove_roles(m, *member_roles)
                except Forbidden:
                    await self.bot.say("Oops, something happened, I don't have permission to clear your roles.")
            else:
                await self.bot.delete_message(bot_message)

    async def _format_roles(self, ctx: Context, all_roles: List[Tuple]) -> List[str]:
        role_names = []
        for role_id, alias in all_roles:
            role_conv = await self._role_convert(ctx, role_id)
            if role_conv is not None:
                name = role_conv.name
                if alias != name:
                    name = "{0} -> {1}".format(name, alias)
                role_names.append(name)

        return role_names

    async def _role_convert(self, ctx: Context, role_id: str):
        role = "<@&{}>".format(role_id)
        role_conv = None
        try:
            role_conv = RoleConverter(ctx, role).convert()
        except BadArgument as e:
            # Unable to convert this role, lets remove it from our database
            msg = e.args[0]
            print(msg)
            await self.database.delete_by_id(ctx.message.server, role_id)
        return role_conv

    async def _parse_roles(self, ctx: Context, roles: str, is_primary: int = 0) -> List[Tuple]:
        roles = roles.rstrip(", \t\n\r")
        roles_arr = roles.split(",")
        alias = None
        rows = []
        for r in roles_arr:
            if "=" in r:
                role, alias = r.split("=")
                role = role.strip(" \t\n\r\"'")
                alias = alias.strip(" \t\n\r\"'")
            else:
                role = r.strip(" \t\n\r\"'")

            try:
                role_conv = RoleConverter(ctx, role).convert()
            except BadArgument as e:
                # Unable to convert this role
                msg = e.args[0]
                print(msg)
                await self.bot.say("Couldn't find role `{}` on this server".format(role))
                continue
            rows.append((role_conv, alias, is_primary))
        return rows

    async def _get_members_from_message(self, msg: Message) -> List[Member]:
        ch = msg.channel
        permissions = ch.permissions_for(msg.author)
        members = []
        if permissions.manage_roles is True:
            members = msg.mentions
        if not members:
            members = [msg.author]
        return members


def setup(bot, kwargs):
    bot.add_cog(Roles(bot, **kwargs))
