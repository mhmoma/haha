# bot_final.py - 全能版图片反推与创意生成机器人 (OpenAI-Compatible)
import os
import discord
from discord import app_commands
import aiohttp
import httpx
from openai import AsyncOpenAI
from dotenv import load_dotenv
from PIL import Image
import io
import base64
import random
import json
import re
import websockets
import uuid
import asyncio
from urllib.parse import urlparse
import time

# 加载环境变量
load_dotenv()

# --- 彩虹屁配置 ---
COMPLIMENTS = [
    "哇，这张图也太好看了吧！简直是艺术品！", "这是什么神仙图片，美到我失语...", "大佬大佬，这光影，这构图，学到了学到了！",
    "您的审美真的太绝了，这张图我能看一天！", "太强了！这张图的氛围感直接拉满！", "好喜欢这张图的色调，感觉整个世界都温柔了。",
    "这张图完美地戳中了我的心巴！", "救命，怎么会有这么好看的图，我直接存了！", "这张图的细节处理得太棒了，简直无可挑剔！",
    "感觉屏幕都装不下这张图的美貌了！", "这是什么级别的画作，可以直接进博物馆的程度！", "看到这张图，我一天的疲惫都消失了。",
    "绝了绝了，这创意，这执行力，都堪称完美！", "我宣布，这张图就是我今天看到的最美的风景。", "这张图有一种让人平静下来的魔力，太治愈了。",
    "请问您是用魔法棒画的吗？不然怎么会这么好看！"
]

# --- OpenAI 兼容 API 配置 ---
API_BASE = os.getenv("OPENAI_API_BASE")
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("OPENAI_MODEL_NAME")
if not all([API_BASE, API_KEY, MODEL_NAME]):
    raise ValueError("请检查 .env 文件，确保 OPENAI_API_BASE, OPENAI_API_KEY, 和 OPENAI_MODEL_NAME 都已设置")

# --- ComfyUI 配置 ---
COMFYUI_ENABLED = os.getenv("COMFYUI_ENABLED", "true").lower() == "true"
COMFYUI_SERVER_ADDRESS = os.getenv("COMFYUI_SERVER_ADDRESS", "127.0.0.1:8188")

# --- 聊天功能配置 ---
CHAT_ENABLED = os.getenv("CHAT_ENABLED", "false").lower() == "true"
CHAT_PROBABILITY = float(os.getenv("CHAT_PROBABILITY", "0.15"))
CHAT_HISTORY_LIMIT = int(os.getenv("CHAT_HISTORY_LIMIT", "8"))

# --- 代理配置 ---
PROXY_URL = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")

# --- 客户端和机器人实例 ---
http_client = httpx.AsyncClient(proxy=PROXY_URL)
client_openai = AsyncOpenAI(base_url=API_BASE, api_key=API_KEY, http_client=http_client)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client_discord = discord.Client(intents=intents, proxy=PROXY_URL)
tree = app_commands.CommandTree(client_discord)

# --- 全局状态和配置 ---
AVAILABLE_MODELS = ["oneObsessionBranch_matureMAXEPS.safetensors"]
user_selected_model = {}
user_gen_settings = {}
is_generating = False
last_generation_time = 0
GENERATION_COOLDOWN = 10
KNOWLEDGE_BASE = None
KNOWLEDGE_BASE_TERMS = {}
user_states = {}

# --- 知识库函数 ---
def load_knowledge_base():
    """加载知识库，优先加载分类后的版本"""
    global KNOWLEDGE_BASE, KNOWLEDGE_BASE_TERMS
    
    classified_file = 'classified_lexicon.json'
    merged_file = 'merged_knowledge_base.json'
    
    try:
        if os.path.exists(classified_file):
            with open(classified_file, 'r', encoding='utf-8') as f:
                KNOWLEDGE_BASE = json.load(f)
            print(f"✅ 已加载分类后知识库: {classified_file}")
        elif os.path.exists(merged_file):
            with open(merged_file, 'r', encoding='utf-8') as f:
                KNOWLEDGE_BASE = json.load(f)
            print(f"✅ 已加载合并知识库: {merged_file}")
        else:
            print("📚 未找到任何知识库。")
            KNOWLEDGE_BASE = {}

        KNOWLEDGE_BASE_TERMS = {}
        total_terms = 0
        for category, items in KNOWLEDGE_BASE.items():
            for item in items:
                term = item.get('term', '').strip().lower()
                if term:
                    if term not in KNOWLEDGE_BASE_TERMS:
                        KNOWLEDGE_BASE_TERMS[term] = []
                    KNOWLEDGE_BASE_TERMS[term].append({
                        'category': category,
                        'term': item.get('term', ''),
                        'translation': item.get('translation', '')
                    })
                    total_terms += 1
        
        print(f"📊 知识库统计: {len(KNOWLEDGE_BASE)} 个分类, {total_terms} 个词条")
        
    except Exception as e:
        print(f"⚠️ 加载知识库时出错: {e}")
        KNOWLEDGE_BASE = {}
        KNOWLEDGE_BASE_TERMS = {}

# --- ComfyUI 核心功能 ---
async def generate_image_with_comfyui(positive_prompt: str, negative_prompt: str, model_name: str, user_settings: dict, workflow_name: str, channel):
    server_address = COMFYUI_SERVER_ADDRESS
    client_id = str(uuid.uuid4())
    ws_url = f"ws://{server_address}/ws?clientId={client_id}"
    workflow_filename = f"{workflow_name}.json" if not workflow_name.endswith('.json') else workflow_name

    try:
        with open(workflow_filename, 'r', encoding='utf-8') as f:
            workflow = json.load(f)

        positive_prompt_node_id = "6"
        negative_prompt_node_id = "7"
        sampler_node_id = "3"
        checkpoint_loader_node_id = "4"

        if model_name:
            workflow[checkpoint_loader_node_id]["inputs"]["ckpt_name"] = model_name
        
        sampler_inputs = workflow[sampler_node_id]["inputs"]
        for key, value in user_settings.items():
            if key in sampler_inputs:
                sampler_inputs[key] = value
        
        if 'seed' in user_settings:
            sampler_inputs["seed"] = user_settings['seed']
        else:
            sampler_inputs["seed"] = random.randint(0, 999999999999999)
        
        workflow[positive_prompt_node_id]["inputs"]["text"] = positive_prompt
        workflow[negative_prompt_node_id]["inputs"]["text"] = negative_prompt or ""

        prompt_data = {"prompt": workflow, "client_id": client_id}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"http://{server_address}/prompt", json=prompt_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"ComfyUI HTTP 请求失败: {response.status}, {error_text}")
                queue_data = await response.json()
                prompt_id = queue_data['prompt_id']

            async with session.ws_connect(ws_url, timeout=300) as ws:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        message = json.loads(msg.data)
                        if message.get('type') == 'executed' and message.get('data', {}).get('prompt_id') == prompt_id:
                            outputs = message['data'].get('output', {}).get('images', [])
                            if outputs:
                                image_info = outputs[0]
                                image_url = f"http://{server_address}/view?filename={image_info['filename']}&subfolder={image_info['subfolder']}&type=output"
                                async with session.get(image_url) as resp:
                                    if resp.status == 200:
                                        return await resp.read()
                            break
    except Exception as e:
        print(f"跑图函数内部错误: {e}")
        raise

# --- 事件处理 ---
@client_discord.event
async def on_ready():
    await tree.sync()
    print("="*50)
    print(f"✅ 机器人已登录: {client_discord.user}")
    print(f"💡 使用模型: {MODEL_NAME}")
    print(f"🖥️ 已连接到 {len(client_discord.guilds)} 个服务器:")
    for guild in client_discord.guilds:
        print(f"  - {guild.name} (ID: {guild.id})")
    
    print("\n" + "-"*50)
    
    commands = tree.get_commands()
    print(f"🚀 {len(commands)} 个斜杠命令已同步:")
    for command in commands:
        if isinstance(command, app_commands.Group):
            for sub_command in command.commands:
                print(f"  - /{command.name} {sub_command.name}")
        else:
            print(f"  - /{command.name}")
            
    print("\n" + "-"*50)
    
    load_knowledge_base()
    
    print("="*50)
    print("🎉 机器人已准备就绪，开始接收指令... 🎉")
    print("="*50)

@tree.command(name="settings", description="查看和配置个人绘图设置")
@app_commands.describe(
    steps="采样步数 (例如: 25)",
    cfg="提示词相关性 (例如: 7.5)",
    seed="随机种子 (留空则为随机)"
)
async def settings(interaction: discord.Interaction, steps: int = None, cfg: float = None, seed: int = None):
    user_id = interaction.user.id
    if user_id not in user_gen_settings:
        user_gen_settings[user_id] = {}

    updated_settings = []
    if steps is not None:
        user_gen_settings[user_id]['steps'] = steps
        updated_settings.append(f"步数设置为 `{steps}`")
    if cfg is not None:
        user_gen_settings[user_id]['cfg'] = cfg
        updated_settings.append(f"CFG 设置为 `{cfg}`")
    if seed is not None:
        if seed == -1:
            if 'seed' in user_gen_settings[user_id]:
                del user_gen_settings[user_id]['seed']
            updated_settings.append("随机种子设置为 `随机`")
        else:
            user_gen_settings[user_id]['seed'] = seed
            updated_settings.append(f"随机种子设置为 `{seed}`")
    
    if updated_settings:
        await interaction.response.send_message("✅ " + "\n".join(updated_settings), ephemeral=True)
    else:
        # Display current settings
        current_settings = user_gen_settings.get(user_id, {})
        embed = discord.Embed(title=f"{interaction.user.name} 的绘图设置", color=discord.Color.blue())
        embed.add_field(name="模型", value=f"`{user_selected_model.get(user_id, '默认')}`", inline=False)
        embed.add_field(name="步数", value=f"`{current_settings.get('steps', '默认')}`", inline=True)
        embed.add_field(name="CFG", value=f"`{current_settings.get('cfg', '默认')}`", inline=True)
        embed.add_field(name="采样器", value=f"`{current_settings.get('sampler_name', '默认')}`", inline=False)
        embed.add_field(name="调度器", value=f"`{current_settings.get('scheduler', '默认')}`", inline=True)
        seed_status = f"`{current_settings.get('seed')}`" if 'seed' in current_settings else '随机'
        embed.add_field(name="随机种", value=seed_status, inline=True)
        embed.set_footer(text="使用 /settings, /sampler, /scheduler, /model 命令来修改设置。")
        await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="model", description="切换使用的绘图模型")
@app_commands.describe(model_name="要切换到的模型名称")
@app_commands.choices(model_name=[
    app_commands.Choice(name=model, value=model) for model in AVAILABLE_MODELS
])
async def set_model(interaction: discord.Interaction, model_name: str):
    user_id = interaction.user.id
    if model_name in AVAILABLE_MODELS:
        user_selected_model[user_id] = model_name
        await interaction.response.send_message(f"✅ 模型已切换为: `{model_name}`", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ 无效的模型名称。可用模型: `{'`, `'.join(AVAILABLE_MODELS)}`", ephemeral=True)

@tree.command(name="sampler", description="设置采样器")
@app_commands.describe(sampler="选择一个采样器")
@app_commands.choices(sampler=[
    app_commands.Choice(name="euler", value="euler"),
    app_commands.Choice(name="euler_ancestral", value="euler_ancestral"),
    app_commands.Choice(name="dpmpp_2m_sde_gpu", value="dpmpp_2m_sde_gpu"),
    app_commands.Choice(name="dpmpp_3m_sde_gpu", value="dpmpp_3m_sde_gpu"),
])
async def set_sampler(interaction: discord.Interaction, sampler: str):
    user_id = interaction.user.id
    if user_id not in user_gen_settings:
        user_gen_settings[user_id] = {}
    user_gen_settings[user_id]['sampler_name'] = sampler
    await interaction.response.send_message(f"✅ 采样器已设置为: `{sampler}`", ephemeral=True)

@tree.command(name="scheduler", description="设置调度器")
@app_commands.describe(scheduler="选择一个调度器")
@app_commands.choices(scheduler=[
    app_commands.Choice(name="normal", value="normal"),
    app_commands.Choice(name="karras", value="karras"),
    app_commands.Choice(name="exponential", value="exponential"),
])
async def set_scheduler(interaction: discord.Interaction, scheduler: str):
    user_id = interaction.user.id
    if user_id not in user_gen_settings:
        user_gen_settings[user_id] = {}
    user_gen_settings[user_id]['scheduler'] = scheduler
    await interaction.response.send_message(f"✅ 调度器已设置为: `{scheduler}`", ephemeral=True)

@client_discord.event
async def on_message(message):
    if message.author.bot:
        return

    global is_generating, last_generation_time
    
    if message.content.startswith("跑图 "):
        if not COMFYUI_ENABLED:
            await message.reply("🎨 抱歉，在线部署模式下，跑图功能已暂停。")
            return

        author_id = message.author.id
        current_time = time.time()

        if is_generating:
            await message.reply("⏳ 当前有图片正在生成中，请稍后再试。")
            return
        
        if current_time - last_generation_time < GENERATION_COOLDOWN:
            remaining_time = round(GENERATION_COOLDOWN - (current_time - last_generation_time), 1)
            await message.reply(f"❄️ 跑图功能冷却中，请在 {remaining_time} 秒后重试。")
            return

        prompt_text = message.content[3:].strip()
        if not prompt_text:
            await message.reply("请在“跑图”指令后输入您的提示词。\n例如: `跑图 正面 a beautiful landscape 负面 blurry, low quality`")
            return

        positive_prompt, negative_prompt = "", ""
        if "正面" in prompt_text or "负面" in prompt_text:
            parts = re.split(r'(正面|负面)', prompt_text)
            current_marker = "positive"
            temp_prompts = {"positive": "", "negative": ""}
            for i, part in enumerate(parts):
                if part == "正面": current_marker = "positive"
                elif part == "负面": current_marker = "negative"
                elif i > 0 and parts[i-1] in ["正面", "负面"]:
                    temp_prompts[current_marker] += part.strip() + " "
            
            positive_prompt = temp_prompts["positive"].strip()
            negative_prompt = temp_prompts["negative"].strip()

            if not positive_prompt and "正面" not in prompt_text:
                positive_prompt = parts[0].strip()
        else:
            positive_prompt = prompt_text
        
        positive_prompt = positive_prompt.strip()
        negative_prompt = negative_prompt.strip()

        user_id = message.author.id
        model_to_use = user_selected_model.get(user_id)
        settings_to_use = user_gen_settings.get(user_id, {})

        settings_data = user_gen_settings.get(user_id, {})
        seed_status = f"`{settings_data.get('seed')}`" if 'seed' in settings_data else '随机'
        loading_msg_text = (
            f"🎨 **正在为您生成图片...**\n"
            f"---------------------------------\n"
            f"🔹 **模型**: `{model_to_use or '默认'}`\n"
            f"🔹 **步数**: `{settings_data.get('steps', '默认')}`\n"
            f"🔹 **CFG**: `{settings_data.get('cfg', '默认')}`\n"
            f"🔹 **采样器**: `{settings_data.get('sampler_name', '默认')}`\n"
            f"🔹 **调度器**: `{settings_data.get('scheduler', '默认')}`\n"
            f"🔹 **随机种**: {seed_status}\n"
            f"---------------------------------\n"
            f"🔸 **正面提示词**: `{'已加载' if positive_prompt else '无'}`\n"
            f"🔸 **负面提示词**: `{'已加载' if negative_prompt else '无'}`"
        )
        loading_msg = await message.reply(loading_msg_text)
        
        is_generating = True
        try:
            image_data = await generate_image_with_comfyui(positive_prompt, negative_prompt, model_to_use, settings_to_use, "工作流", message.channel)
            if image_data:
                await loading_msg.delete()
                await message.reply(
                    content=f"🖼️ {message.author.mention}，这是为您生成的图片：",
                    file=discord.File(io.BytesIO(image_data), filename="generated_image.png")
                )
            else:
                await loading_msg.edit(content="❌ 未能从 ComfyUI 获取到生成的图片。")
        except Exception as e:
            await loading_msg.edit(content=f"❌ 跑图失败：{e}")
        finally:
            is_generating = False
            last_generation_time = time.time()
        return

    # --- 聊天功能 ---
    if CHAT_ENABLED:
        # 检查是否应该回复：被@或者满足随机概率
        should_reply = client_discord.user in message.mentions or random.random() < CHAT_PROBABILITY

        if should_reply:
            channel_id = message.channel.id
            if channel_id not in user_states:
                user_states[channel_id] = {"history": []}

            # 添加用户消息到历史记录
            user_states[channel_id]["history"].append({"role": "user", "content": message.clean_content})

            # 保持历史记录在限制范围内
            if len(user_states[channel_id]["history"]) > CHAT_HISTORY_LIMIT:
                user_states[channel_id]["history"] = user_states[channel_id]["history"][-CHAT_HISTORY_LIMIT:]

            # 构建发送给API的消息
            messages_to_send = [
                {"role": "system", "content": "你是一个友好、乐于助人的Discord机器人，你的名字叫“小哈”。请用轻松、口语化的方式回答问题。"}
            ] + user_states[channel_id]["history"]

            try:
                async with message.channel.typing():
                    response = await client_openai.chat.completions.create(
                        model=MODEL_NAME,
                        messages=messages_to_send,
                        temperature=0.7,
                    )
                    bot_reply = response.choices[0].message.content.strip()

                    if bot_reply:
                        # 添加机器人回复到历史记录
                        user_states[channel_id]["history"].append({"role": "assistant", "content": bot_reply})
                        await message.reply(bot_reply)

            except Exception as e:
                print(f"调用聊天 API 时出错: {e}")
                # 可以在这里添加一个错误回复，但为了避免刷屏，暂时只打印日志
                await message.reply("哎呀，我的大脑好像短路了，稍后再试吧！")

# --- 启动机器人 ---
if __name__ == "__main__":
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if not DISCORD_TOKEN:
        raise ValueError("未找到 DISCORD_TOKEN，请检查 .env 文件")
    try:
        client_discord.run(DISCORD_TOKEN)
    except discord.errors.LoginFailure:
        print("❌ Discord Token 无效，请检查 .env 文件中的 DISCORD_TOKEN 是否正确。")
    except Exception as e:
        print(f"❌ 启动机器人时发生错误: {e}")
