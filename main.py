import discord, os, pytesseract, io, aiohttp, hashlib
from Levenshtein import distance
from datetime import timedelta
from dotenv import load_dotenv
from PIL import Image

load_dotenv(os.path.expanduser(".env"))
# load_dotenv(os.path.expanduser("~/secrets/env"))

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
SCAM_WORDS = "withdraw claim reward casino crypto mrbeast promo special cryptocurrency vip bonus redeem receive coin deleted wallet celebrate register transferred promotion chance money winner successful block explorer deposit".split()
trigger_level = 120
log_channel = 
HASH_FILE = "scam_hashes.txt"

def load_hashes():
    try:
        with open(HASH_FILE) as f: return set(f.read().splitlines())
    except FileNotFoundError: return set()

def save_hashes(new):
    global known_hashes
    known_hashes.update(new)
    with open(HASH_FILE, "a") as f:
        for h in new: f.write(h + "\n")

async def run_ocr(message, images):
    global known_hashes
    image_hashes, matches, all_text, scam_images = [], {}, "", set()
    async with aiohttp.ClientSession() as session:
        for i, att in enumerate(images):
            async with session.get(att.url) as resp:
                data = await resp.read()
            h = hashlib.sha256(data).hexdigest()

            image_hashes.append(h)
            if h in known_hashes:
                embed = discord.Embed(title="Recognized Scam Hash", color=0xd42c03)
                embed.description = f"Deleted message in {message.channel.mention} by {message.author.mention}"
                return True, embed

            try: text = pytesseract.image_to_string(Image.open(io.BytesIO(data))).strip()
            except pytesseract.TesseractError: continue
            except OSError: exit("Please install tesseract-ocr with your package manager")
            if not text: continue

            all_text += text + " "
            img_matches = {}
            for sw in SCAM_WORDS:
                c = sum(1 for w in text.lower().split() if distance(w, sw) <= max(0, (len(sw) - 4) // 3))
                if c: img_matches[sw] = c

            if len(img_matches) >= 3:
                scam_images.add(h)

            matches = {}
            for sw in SCAM_WORDS:
                c = sum(1 for w in all_text.lower().split() if distance(w, sw) <= max(0, (len(sw) - 4) // 3))
                if c: matches[sw] = c

            if len(matches) < 3: continue

            confidence = len(matches) * sum(matches.values())

            if confidence >= trigger_level:
                save_hashes([h for h in scam_images if h not in known_hashes])
                match_list = ", ".join(f"{w} (x{c})" for w, c in matches.items())
                analysis_embed = discord.Embed(title="Scam Message Detected", color=0xf7b200)
                analysis_embed.description = f"Deleted message in {message.channel.mention} by {message.author.mention}"
                analysis_embed.add_field(name="Likelihood coefficient", value=f"{confidence} after {i+1} image{'s' if i else ''}", inline=True)
                analysis_embed.add_field(name="Matches", value=match_list, inline=False)
                return True, analysis_embed

    return False, None

@bot.event
async def on_message(message):
    images = [a for a in message.attachments if a.content_type and a.content_type.startswith("image/")]
    if not images or message.author.bot: return

    is_scam_msg, analysis_embed = await run_ocr(message, images)
    if not is_scam_msg: return

    try: await message.author.timeout(timedelta(seconds=60), reason="Blocking mrbeast scam")
    except: pass

    try: await message.forward(bot.get_channel(log_channel))
    except: pass

    try: await message.delete()
    except: pass

    processing_time = int((discord.utils.utcnow() - message.created_at).total_seconds() * 1000)
    analysis_embed.set_footer(text=f"Processing time: {processing_time}ms")
    await bot.get_channel(log_channel).send(embed=analysis_embed)

@bot.event
async def on_ready():
    print(f"Ready as {bot.user}")

known_hashes = load_hashes()
bot.run(os.getenv("INFRABOT_TOKEN"))
