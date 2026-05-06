import asyncio
import os
from typing import Any, Optional

import discord
import httpx
from discord import app_commands
from discord.ext import commands


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "jmec-staff")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")

TEAM_CHOICES = [
    app_commands.Choice(name="零小", value="Zeroth"),
    app_commands.Choice(name="一小", value="First"),
    app_commands.Choice(name="二小", value="Second"),
]

SYMBOL_CHOICES = [
    app_commands.Choice(name="INFOR 建中資訊社", value="INFOR"),
    app_commands.Choice(name="CMIOC 景美電資社", value="CMIOC"),
    app_commands.Choice(name="IZCC 四社聯合", value="IZCC"),
]

MARKET_SYMBOL_CHOICES = [
    app_commands.Choice(name="全市場", value="ALL"),
    *SYMBOL_CHOICES,
]

OPERATION_CHOICES = [
    app_commands.Choice(name="set 設定為", value="set"),
    app_commands.Choice(name="multiply 乘以", value="multiply"),
    app_commands.Choice(name="add 增加", value="add"),
    app_commands.Choice(name="remove 扣除", value="remove"),
]


class ApiError(Exception):
    pass


class TradingBot(commands.Bot):
    async def setup_hook(self):
        if DISCORD_GUILD_ID:
            guild = discord.Object(id=int(DISCORD_GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} slash commands to guild {DISCORD_GUILD_ID}.")
        else:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} global slash commands.")


intents = discord.Intents.default()
bot = TradingBot(command_prefix="!", intents=intents)


async def api_request(
    method: str,
    path: str,
    *,
    json: Optional[dict[str, Any]] = None,
    admin: bool = False,
) -> Any:
    headers = {"X-Admin-Token": ADMIN_TOKEN} if admin else None
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=10) as client:
        response = await client.request(method, path, json=json, headers=headers)

    try:
        payload = response.json()
    except ValueError:
        payload = {"detail": response.text}

    if response.status_code >= 400:
        detail = payload.get("detail", f"HTTP {response.status_code}")
        raise ApiError(str(detail))

    return payload


def fmt_money(value: float) -> str:
    return f"${value:,.2f}"


def fmt_quantity(value: float) -> str:
    return f"{value:,.6f}".rstrip("0").rstrip(".")


def is_game_admin(interaction: discord.Interaction) -> bool:
    user = interaction.user
    if not isinstance(user, discord.Member):
        return False
    permissions = user.guild_permissions
    return permissions.administrator or permissions.manage_guild


async def ensure_game_admin(interaction: discord.Interaction) -> bool:
    if is_game_admin(interaction):
        return True
    await interaction.response.send_message(
        "這個指令僅限 Admin 或具備管理伺服器權限的成員使用。",
        ephemeral=True,
    )
    return False


async def send_api_error(interaction: discord.Interaction, error: Exception):
    message = f"指令失敗：{error}"
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


def build_price_embed(data: dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(title="CMIOC x INFOR 即時行情", color=0x38FF7E)
    for item in data["prices"]:
        change = item["change_percent"]
        sign = "+" if change >= 0 else ""
        embed.add_field(
            name=f'{item["symbol"]} {item["name"]}',
            value=f'{fmt_money(item["current_price"])}\n{sign}{change:.2f}%',
            inline=True,
        )

    latest_news = data.get("latest_news")
    if latest_news:
        embed.add_field(
            name="新聞快訊",
            value=latest_news["headline"],
            inline=False,
        )
    return embed


def build_team_embed(team: dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(
        title=f'{team["name"]} 資產狀態',
        description=f'總資產 {fmt_money(team["total_portfolio_value"])}',
        color=0x37D6FF,
    )
    embed.add_field(name="現金", value=fmt_money(team["balance"]), inline=False)

    if team["holdings"]:
        for holding in team["holdings"]:
            embed.add_field(
                name=holding["crypto_symbol"],
                value=(
                    f'{fmt_quantity(holding["quantity"])} 顆\n'
                    f'{fmt_money(holding["current_value"])}'
                ),
                inline=True,
            )
    else:
        embed.add_field(name="持倉", value="目前沒有持倉", inline=False)

    return embed


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} | API: {API_BASE_URL}")


@bot.tree.command(name="price", description="查看即時幣價與最新新聞")
async def price(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        data = await api_request("GET", "/price")
        await interaction.followup.send(embed=build_price_embed(data))
    except Exception as error:
        await send_api_error(interaction, error)


@bot.tree.command(name="buy", description="買入虛擬貨幣")
@app_commands.choices(team_name=TEAM_CHOICES, crypto_symbol=SYMBOL_CHOICES)
async def buy(
    interaction: discord.Interaction,
    team_name: app_commands.Choice[str],
    crypto_symbol: app_commands.Choice[str],
    quantity: float,
):
    await interaction.response.defer()
    try:
        trade = await api_request(
            "POST",
            "/trade",
            json={
                "team_name": team_name.value,
                "crypto_symbol": crypto_symbol.value,
                "quantity": quantity,
                "trade_type": "buy",
            },
        )
        await interaction.followup.send(
            f'{trade["team_name"]} 買入 {fmt_quantity(trade["quantity"])} '
            f'{trade["crypto_symbol"]}，成交價 {fmt_money(trade["price_at_trade"])}，'
            f'總額 {fmt_money(trade["total_value"])}'
        )
    except Exception as error:
        await send_api_error(interaction, error)


@bot.tree.command(name="sell", description="賣出虛擬貨幣")
@app_commands.choices(team_name=TEAM_CHOICES, crypto_symbol=SYMBOL_CHOICES)
async def sell(
    interaction: discord.Interaction,
    team_name: app_commands.Choice[str],
    crypto_symbol: app_commands.Choice[str],
    quantity: float,
):
    await interaction.response.defer()
    try:
        trade = await api_request(
            "POST",
            "/trade",
            json={
                "team_name": team_name.value,
                "crypto_symbol": crypto_symbol.value,
                "quantity": quantity,
                "trade_type": "sell",
            },
        )
        await interaction.followup.send(
            f'{trade["team_name"]} 賣出 {fmt_quantity(trade["quantity"])} '
            f'{trade["crypto_symbol"]}，成交價 {fmt_money(trade["price_at_trade"])}，'
            f'總額 {fmt_money(trade["total_value"])}'
        )
    except Exception as error:
        await send_api_error(interaction, error)


@bot.tree.command(name="balance", description="查看小隊資產")
@app_commands.choices(team_name=TEAM_CHOICES)
async def balance(
    interaction: discord.Interaction,
    team_name: app_commands.Choice[str],
):
    await interaction.response.defer()
    try:
        team = await api_request("GET", f"/teams/{team_name.value}")
        await interaction.followup.send(embed=build_team_embed(team))
    except Exception as error:
        await send_api_error(interaction, error)


@bot.tree.command(name="leaderboard", description="查看排行榜")
async def leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        teams = await api_request("GET", "/leaderboard")
        lines = [
            f'{index + 1}. {team["name"]}: {fmt_money(team["total_portfolio_value"])}'
            for index, team in enumerate(teams)
        ]
        embed = discord.Embed(
            title="CMIOC x INFOR 排行榜",
            description="\n".join(lines),
            color=0xFFD76A,
        )
        await interaction.followup.send(embed=embed)
    except Exception as error:
        await send_api_error(interaction, error)


@bot.tree.command(name="news", description="查看最新新聞")
async def news(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        items = await api_request("GET", "/news")
        if not items:
            await interaction.followup.send("目前尚無新聞。")
            return

        lines = [f'- {item["headline"]}' for item in items[:6]]
        embed = discord.Embed(
            title="新聞快訊",
            description="\n".join(lines),
            color=0x38FF7E,
        )
        await interaction.followup.send(embed=embed)
    except Exception as error:
        await send_api_error(interaction, error)


@bot.tree.command(name="start_game", description="開始遊戲並設定三隊本金")
@app_commands.default_permissions(administrator=True)
async def start_game(
    interaction: discord.Interaction,
    zeroth_balance: float = 800.0,
    first_balance: float = 800.0,
    second_balance: float = 800.0,
):
    if not await ensure_game_admin(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    try:
        state = await api_request(
            "POST",
            "/admin/game/start",
            json={
                "zeroth_balance": zeroth_balance,
                "first_balance": first_balance,
                "second_balance": second_balance,
            },
            admin=True,
        )
        prices = ", ".join(
            f'{item["symbol"]} {fmt_money(item["current_price"])}'
            for item in state["prices"]
        )
        await interaction.followup.send(
            "遊戲已開始。\n"
            f"零小本金：{fmt_money(zeroth_balance)}\n"
            f"一小本金：{fmt_money(first_balance)}\n"
            f"二小本金：{fmt_money(second_balance)}\n"
            f"初始價格：{prices}",
            ephemeral=True,
        )
    except Exception as error:
        await send_api_error(interaction, error)


@bot.tree.command(name="end_game", description="結束遊戲並進入結算狀態")
@app_commands.default_permissions(administrator=True)
async def end_game(interaction: discord.Interaction):
    if not await ensure_game_admin(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    try:
        state = await api_request("POST", "/admin/game/end", admin=True)
        leader = max(state["teams"], key=lambda team: team["total_portfolio_value"])
        await interaction.followup.send(
            f'遊戲已結束。目前領先：{leader["name"]} '
            f'{fmt_money(leader["total_portfolio_value"])}',
            ephemeral=True,
        )
    except Exception as error:
        await send_api_error(interaction, error)


@bot.tree.command(name="team_balance", description="管理小隊現金")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(team_name=TEAM_CHOICES, operation=OPERATION_CHOICES)
async def team_balance(
    interaction: discord.Interaction,
    team_name: app_commands.Choice[str],
    operation: app_commands.Choice[str],
    amount: float,
):
    if not await ensure_game_admin(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    try:
        team = await api_request(
            "POST",
            f"/admin/teams/{team_name.value}/balance",
            json={"operation": operation.value, "amount": amount},
            admin=True,
        )
        await interaction.followup.send(
            f'{team["name"]} 現金已更新為 {fmt_money(team["balance"])}',
            ephemeral=True,
        )
    except Exception as error:
        await send_api_error(interaction, error)


@bot.tree.command(name="team_holding", description="管理小隊持幣")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(
    team_name=TEAM_CHOICES,
    crypto_symbol=SYMBOL_CHOICES,
    operation=OPERATION_CHOICES,
)
async def team_holding(
    interaction: discord.Interaction,
    team_name: app_commands.Choice[str],
    crypto_symbol: app_commands.Choice[str],
    operation: app_commands.Choice[str],
    quantity: float,
):
    if not await ensure_game_admin(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    try:
        team = await api_request(
            "POST",
            f"/admin/teams/{team_name.value}/holdings",
            json={
                "operation": operation.value,
                "crypto_symbol": crypto_symbol.value,
                "quantity": quantity,
            },
            admin=True,
        )
        await interaction.followup.send(
            f'{team["name"]} 的 {crypto_symbol.value} 持倉已更新。',
            ephemeral=True,
        )
    except Exception as error:
        await send_api_error(interaction, error)


async def trigger_staff_event(
    interaction: discord.Interaction,
    event_type: str,
    symbol: app_commands.Choice[str],
    percent: float,
    headline: Optional[str],
):
    if not await ensure_game_admin(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    target_symbol = None if symbol.value == "ALL" else symbol.value
    try:
        result = await api_request(
            "POST",
            "/admin/market-event",
            json={
                "event_type": event_type,
                "symbol": target_symbol,
                "percent": percent,
                "headline": headline,
            },
            admin=True,
        )
        await interaction.followup.send(
            f'已排入下一輪行情：{result["headline"]}',
            ephemeral=True,
        )
    except Exception as error:
        await send_api_error(interaction, error)


@bot.tree.command(name="pump", description="觸發利多暴漲")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(symbol=MARKET_SYMBOL_CHOICES)
async def pump(
    interaction: discord.Interaction,
    symbol: app_commands.Choice[str],
    percent: float = 5.0,
    headline: Optional[str] = None,
):
    await trigger_staff_event(interaction, "pump", symbol, percent, headline)


@bot.tree.command(name="crash", description="觸發市場崩盤")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(symbol=MARKET_SYMBOL_CHOICES)
async def crash(
    interaction: discord.Interaction,
    symbol: app_commands.Choice[str],
    percent: float = 5.0,
    headline: Optional[str] = None,
):
    await trigger_staff_event(interaction, "crash", symbol, percent, headline)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    await send_api_error(interaction, error)


async def main():
    if not DISCORD_BOT_TOKEN:
        raise RuntimeError("Please set DISCORD_BOT_TOKEN before starting the bot.")

    async with bot:
        await bot.start(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
