import discord
from discord.ext import commands
import asyncio
import re
import datetime
import os

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='.', intents=intents, help_command=None)

# ════════════════════════════════════════════════
#  ⚙️  BURAYA KENDİ ID'LERİNİ YAZ
# ════════════════════════════════════════════════
LOG_KANAL_ID      = 1479829702821548243   # Log kanalı ID

KAYIT_YETKI_ROL   = "Kayıt Yetkilisi"    # Kayıt yetkisi olan rolün adı
KAYITLI_ROL       = "Kayıtlı"            # Kayıt sonrası verilecek rol
KAYITSIZ_ROL      = "Kayıtsız"           # Kayıtsız komutuyla verilecek rol

ROL_UYE           = "Üye"
ROL_FUTBOLCU      = "Futbolcu"
ROL_TAKIM_BASKANI = "Takım Başkanı"
# ════════════════════════════════════════════════

afk_listesi     = {}
antrenman_sayac = {}
kayit_sayaci    = {}

# ─────────────────────────────────────────────
def hata_embed(mesaj):
    return discord.Embed(description=f"❌ {mesaj}", color=0xFF4C4C)

def basari_embed(mesaj):
    return discord.Embed(description=f"✅ {mesaj}", color=0x2ECC71)


def deger_isle(isim, miktar_str, islem):
    parcalar = [p.strip() for p in isim.split("|")]
    if len(parcalar) < 2:
        return None, "İsim formatı hatalı! Format: `Ad | 1M | ...`"
    mevcut_str = parcalar[1].strip()
    eslesme = re.match(r"^(\d+(?:\.\d+)?)M$", mevcut_str, re.IGNORECASE)
    if not eslesme:
        return None, f"Mevcut değer `{mevcut_str}` geçerli formatta değil!"
    mevcut = float(eslesme.group(1))
    miktar_eslesme = re.match(r"^(\d+(?:\.\d+)?)M$", miktar_str, re.IGNORECASE)
    if not miktar_eslesme:
        return None, f"`{miktar_str}` geçerli bir değer değil! (örnek: `2M`)"
    miktar = float(miktar_eslesme.group(1))
    yeni = mevcut + miktar if islem == "ekle" else max(0.0, mevcut - miktar)
    yeni_str = f"{int(yeni)}M" if yeni == int(yeni) else f"{yeni}M"
    parcalar[1] = f" {yeni_str} "
    return "|".join(parcalar), f"`{mevcut_str}` → `{yeni_str}`"


def antrenman_deger_ekle(isim, eklenecek: float):
    parcalar = [p.strip() for p in isim.split("|")]
    if len(parcalar) < 2:
        return None, "İsim formatı hatalı! Format: `Ad | 1M | ...`", None
    mevcut_str = parcalar[1].strip()
    eslesme = re.match(r"^(\d+(?:\.\d+)?)M$", mevcut_str, re.IGNORECASE)
    if not eslesme:
        return None, f"Değer `{mevcut_str}` formatı hatalı!", None
    mevcut = float(eslesme.group(1))
    yeni = mevcut + eklenecek
    yeni_str = f"{int(yeni)}M" if yeni == int(yeni) else f"{yeni}M"
    parcalar[1] = f" {yeni_str} "
    return "|".join(parcalar), mevcut_str, yeni_str


async def log_deger_gonder(guild, islem_yapan, hedef, eski_deger, yeni_deger, islem_turu):
    kanal = guild.get_channel(LOG_KANAL_ID)
    if not kanal:
        return
    embed = discord.Embed(title="📊 Değer Güncellendi", color=0x5865F2,
                          timestamp=datetime.datetime.utcnow())
    embed.add_field(name="İşlem",        value=islem_turu, inline=True)
    embed.add_field(name="Hedef",        value=hedef.mention, inline=True)
    embed.add_field(name="İşlemi Yapan", value=getattr(islem_yapan, 'mention', str(islem_yapan)), inline=True)
    embed.add_field(name="Eski Değer",   value=f"`{eski_deger}`", inline=True)
    embed.add_field(name="Yeni Değer",   value=f"`{yeni_deger}`", inline=True)
    embed.set_footer(text=f"Kullanıcı ID: {hedef.id}")
    await kanal.send(embed=embed)


def kayit_yetkisi_var_mi(member: discord.Member) -> bool:
    return any(r.name == KAYIT_YETKI_ROL for r in member.roles)


# ─────────────────────────────────────────────
#  EVENTS
# ─────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ {bot.user} olarak giriş yapıldı!")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=".yardım | Moderasyon Botu"
    ))

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.author.id in afk_listesi:
        sebep, zaman = afk_listesi.pop(message.author.id)
        gecen = datetime.datetime.utcnow() - zaman
        dakika = int(gecen.total_seconds() // 60)
        await message.channel.send(embed=discord.Embed(
            description=f"👋 **{message.author.display_name}**, AFK modundan çıktın! ({dakika} dakika AFK'daydın)",
            color=0x5865F2), delete_after=5)
    for mention in message.mentions:
        if mention.id in afk_listesi:
            sebep, zaman = afk_listesi[mention.id]
            gecen = datetime.datetime.utcnow() - zaman
            dakika = int(gecen.total_seconds() // 60)
            await message.channel.send(embed=discord.Embed(
                description=f"💤 **{mention.display_name}** şu an AFK! Sebep: {sebep} ({dakika} dakikadır AFK)",
                color=0xFFA500), delete_after=8)
    await bot.process_commands(message)


# ─────────────────────────────────────────────
#  KANAL KOMUTLARI
# ─────────────────────────────────────────────
@bot.command(name="lock")
@commands.has_permissions(manage_channels=True)
async def lock(ctx, kanal: discord.TextChannel = None):
    kanal = kanal or ctx.channel
    await kanal.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(embed=basari_embed(f"🔒 {kanal.mention} kanalı kilitlendi."))

@bot.command(name="unlock")
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, kanal: discord.TextChannel = None):
    kanal = kanal or ctx.channel
    await kanal.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(embed=basari_embed(f"🔓 {kanal.mention} kanalının kilidi açıldı."))


# ─────────────────────────────────────────────
#  KULLANICI KOMUTLARI
# ─────────────────────────────────────────────
@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, uye: discord.Member, *, sebep: str = "Sebep belirtilmedi"):
    if uye == ctx.author:
        return await ctx.send(embed=hata_embed("Kendinizi ban yapamazsınız!"))
    if uye.top_role >= ctx.author.top_role:
        return await ctx.send(embed=hata_embed("Bu kullanıcıyı ban yapamazsınız!"))
    await uye.ban(reason=sebep)
    await ctx.send(embed=basari_embed(f"**{uye}** banlandı.\n📋 Sebep: {sebep}"))

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, kullanici: str):
    bans = [entry async for entry in ctx.guild.bans()]
    for entry in bans:
        user = entry.user
        if str(user) == kullanici or user.name == kullanici:
            await ctx.guild.unban(user)
            return await ctx.send(embed=basari_embed(f"**{user}** kullanıcısının banı kaldırıldı."))
    await ctx.send(embed=hata_embed(f"`{kullanici}` adlı banlı kullanıcı bulunamadı."))

@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute(ctx, uye: discord.Member, *, arguman: str = "10"):
    parcalar = arguman.split(" ", 1)
    try:
        sure = int(parcalar[0])
        sebep = parcalar[1] if len(parcalar) > 1 else "Sebep belirtilmedi"
    except ValueError:
        sure = 10
        sebep = arguman
    if uye == ctx.author:
        return await ctx.send(embed=hata_embed("Kendinizi susturmak için bu komutu kullanamazsınız!"))
    if uye.top_role >= ctx.author.top_role:
        return await ctx.send(embed=hata_embed("Bu kullanıcıyı susturma yetkiniz yok!"))
    if sure < 1 or sure > 40320:
        return await ctx.send(embed=hata_embed("Süre 1 ile 40320 dakika arasında olmalıdır!"))
    bitis = discord.utils.utcnow() + datetime.timedelta(minutes=sure)
    await uye.timeout(bitis, reason=sebep)
    await ctx.send(embed=basari_embed(f"🔇 **{uye.mention}** {sure} dakika susturuldu.\n📋 Sebep: {sebep}"))

@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, uye: discord.Member):
    await uye.timeout(None)
    await ctx.send(embed=basari_embed(f"🔊 **{uye.mention}** kullanıcısının susturması kaldırıldı."))

@bot.command(name="sil")
@commands.has_permissions(manage_messages=True)
async def sil(ctx, adet: int):
    if adet < 1 or adet > 10000:
        return await ctx.send(embed=hata_embed("1 ile 100 arasında bir sayı giriniz!"))
    await ctx.message.delete()
    silinen = await ctx.channel.purge(limit=adet)
    msg = await ctx.send(embed=basari_embed(f"🗑️ {len(silinen)} mesaj silindi."))
    await asyncio.sleep(3)
    await msg.delete()


# ─────────────────────────────────────────────
#  ROL KOMUTLARI
# ─────────────────────────────────────────────
@bot.command(name="rolver")
@commands.has_permissions(manage_roles=True)
async def rolver(ctx, uye: discord.Member, rol: discord.Role):
    if rol >= ctx.guild.me.top_role:
        return await ctx.send(embed=hata_embed("Bu rolü veremem, rolüm bu rolden aşağıda!"))
    if rol in uye.roles:
        return await ctx.send(embed=hata_embed(f"**{uye.display_name}** zaten bu role sahip!"))
    await uye.add_roles(rol)
    await ctx.send(embed=basari_embed(f"**{uye.mention}** kullanıcısına **{rol.name}** rolü verildi."))

@bot.command(name="rolal")
@commands.has_permissions(manage_roles=True)
async def rolal(ctx, uye: discord.Member, rol: discord.Role):
    if rol >= ctx.guild.me.top_role:
        return await ctx.send(embed=hata_embed("Bu rolü alamam, rolüm bu rolden aşağıda!"))
    if rol not in uye.roles:
        return await ctx.send(embed=hata_embed(f"**{uye.display_name}** bu role sahip değil!"))
    await uye.remove_roles(rol)
    await ctx.send(embed=basari_embed(f"**{uye.mention}** kullanıcısından **{rol.name}** rolü alındı."))

@bot.command(name="toplurolver")
@commands.has_permissions(manage_roles=True)
async def toplu_rolver(ctx, rol: discord.Role):
    if rol >= ctx.guild.me.top_role:
        return await ctx.send(embed=hata_embed("Bu rolü veremem, rolüm bu rolden aşağıda!"))
    msg = await ctx.send(embed=discord.Embed(
        description=f"⏳ Tüm üyelere **{rol.name}** rolü veriliyor...", color=0xFFA500))
    sayac = 0
    for uye in ctx.guild.members:
        if rol not in uye.roles and not uye.bot:
            try:
                await uye.add_roles(rol)
                sayac += 1
                await asyncio.sleep(0.5)
            except Exception:
                pass
    await msg.edit(embed=basari_embed(f"✅ **{sayac}** üyeye **{rol.name}** rolü verildi."))

@bot.command(name="toplurolal")
@commands.has_permissions(manage_roles=True)
async def toplu_rolal(ctx, rol: discord.Role):
    if rol >= ctx.guild.me.top_role:
        return await ctx.send(embed=hata_embed("Bu rolü alamam, rolüm bu rolden aşağıda!"))
    msg = await ctx.send(embed=discord.Embed(
        description=f"⏳ Tüm üyelerden **{rol.name}** rolü alınıyor...", color=0xFFA500))
    sayac = 0
    for uye in ctx.guild.members:
        if rol in uye.roles and not uye.bot:
            try:
                await uye.remove_roles(rol)
                sayac += 1
                await asyncio.sleep(0.5)
            except Exception:
                pass
    await msg.edit(embed=basari_embed(f"✅ **{sayac}** üyeden **{rol.name}** rolü alındı."))


# ─────────────────────────────────────────────
#  İSİM / DEĞER KOMUTLARI
# ─────────────────────────────────────────────
@bot.command(name="isimdeğiştir")
@commands.has_permissions(manage_nicknames=True)
async def isim_degistir(ctx, uye: discord.Member, *, yeni_isim: str):
    eski_isim = uye.display_name
    await uye.edit(nick=yeni_isim)
    await ctx.send(embed=basari_embed(f"**{eski_isim}** → **{yeni_isim}** olarak değiştirildi."))

@bot.command(name="dver")
@commands.has_permissions(manage_nicknames=True)
async def dver(ctx, uye: discord.Member, miktar: str):
    eski_isim = uye.display_name
    parcalar = [p.strip() for p in eski_isim.split("|")]
    eski_deger = parcalar[1].strip() if len(parcalar) >= 2 else "?"
    yeni_isim, sonuc = deger_isle(eski_isim, miktar, "ekle")
    if yeni_isim is None:
        return await ctx.send(embed=hata_embed(sonuc))
    await uye.edit(nick=yeni_isim)
    yeni_parcalar = [p.strip() for p in yeni_isim.split("|")]
    yeni_deger = yeni_parcalar[1].strip() if len(yeni_parcalar) >= 2 else "?"
    await ctx.send(embed=basari_embed(
        f"**{uye.mention}** değeri güncellendi: {sonuc}\n📝 Yeni isim: `{yeni_isim}`"))
    await log_deger_gonder(ctx.guild, ctx.author, uye, eski_deger, yeni_deger, "➕ Değer Eklendi")

@bot.command(name="dsil")
@commands.has_permissions(manage_nicknames=True)
async def dsil(ctx, uye: discord.Member, miktar: str = None):
    mevcut_isim = uye.display_name
    parcalar = [p.strip() for p in mevcut_isim.split("|")]
    if len(parcalar) < 2:
        return await ctx.send(embed=hata_embed("İsim formatı hatalı! Format: `Ad | 1M | ...`"))
    eski_deger = parcalar[1].strip()
    if miktar is None:
        parcalar[1] = " 0M "
        yeni_isim = "|".join(parcalar)
        await uye.edit(nick=yeni_isim)
        await ctx.send(embed=basari_embed(
            f"**{uye.mention}** değeri sıfırlandı: `{eski_deger}` → `0M`\n📝 Yeni isim: `{yeni_isim}`"))
        await log_deger_gonder(ctx.guild, ctx.author, uye, eski_deger, "0M", "🔄 Değer Sıfırlandı")
        return
    yeni_isim, sonuc = deger_isle(mevcut_isim, miktar, "çıkar")
    if yeni_isim is None:
        return await ctx.send(embed=hata_embed(sonuc))
    await uye.edit(nick=yeni_isim)
    yeni_parcalar = [p.strip() for p in yeni_isim.split("|")]
    yeni_deger = yeni_parcalar[1].strip() if len(yeni_parcalar) >= 2 else "?"
    await ctx.send(embed=basari_embed(
        f"**{uye.mention}** değeri güncellendi: {sonuc}\n📝 Yeni isim: `{yeni_isim}`"))
    await log_deger_gonder(ctx.guild, ctx.author, uye, eski_deger, yeni_deger, "➖ Değer Çıkarıldı")


# ─────────────────────────────────────────────
#  KAYIT KOMUTU (.k)
# ─────────────────────────────────────────────
@bot.command(name="k")
async def kayit(ctx, uye: discord.Member, *, bilgi: str):
    if not kayit_yetkisi_var_mi(ctx.author):
        return await ctx.send(embed=hata_embed("Bu komutu kullanmak için **Kayıt Yetkilisi** rolüne sahip olmalısın!"))

    # Yazılan her şey olduğu gibi nick olur — örn: "L.Messi | 1M | | SNT"
    yeni_nick = bilgi.strip()

    if not yeni_nick:
        return await ctx.send(embed=hata_embed("Kullanım: `.k @üye L.Messi | 1M | | SNT`"))

    embed = discord.Embed(
        title="📋 Kayıt Türü Seç",
        description=(
            f"**{uye.mention}** için kayıt türü seçin.\n"
            f"📝 Nick: `{yeni_nick}`"
        ),
        color=0x5865F2
    )
    embed.set_footer(text="Aşağıdaki butonlardan birini seçin")

    view = KayitSecimView(
        hedef=uye,
        yeni_nick=yeni_nick,
        yapan=ctx.author
    )
    await ctx.send(embed=embed, view=view)


class KayitSecimView(discord.ui.View):
    def __init__(self, hedef: discord.Member, yeni_nick: str, yapan: discord.Member):
        super().__init__(timeout=60)
        self.hedef      = hedef
        self.yeni_nick  = yeni_nick
        self.yapan      = yapan
        self.kullanildi = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.yapan.id:
            await interaction.response.send_message(
                embed=hata_embed("Bu butonları yalnızca komutu kullanan kişi kullanabilir!"),
                ephemeral=True
            )
            return False
        return True

    async def kayit_yap(self, interaction: discord.Interaction, rol_adi: str):
        if self.kullanildi:
            await interaction.response.send_message(
                embed=hata_embed("Bu kayıt zaten tamamlandı!"), ephemeral=True)
            return
        self.kullanildi = True

        guild     = interaction.guild
        hedef     = self.hedef
        yeni_nick = self.yeni_nick

        # Rolleri bul
        secilen_rol = discord.utils.get(guild.roles, name=rol_adi)
        kayitli_rol = discord.utils.get(guild.roles, name=KAYITLI_ROL)

        eksik_roller = []
        if not secilen_rol:
            eksik_roller.append(rol_adi)
        if not kayitli_rol:
            eksik_roller.append(KAYITLI_ROL)

        if eksik_roller:
            await interaction.response.edit_message(
                embed=hata_embed(f"Sunucuda şu roller bulunamadı: `{'`, `'.join(eksik_roller)}`\nLütfen rolleri oluştur."),
                view=None
            )
            return

        # Nick değiştir
        nick_hata = None
        try:
            await hedef.edit(nick=yeni_nick)
        except discord.Forbidden:
            nick_hata = "⚠️ Nick değiştirilemedi: Bot bu üye üzerinde yetkisiz (rol sırası kontrolü)."
        except discord.HTTPException as e:
            nick_hata = f"⚠️ Nick değiştirilemedi: {e}"

        # Rolleri ver
        await hedef.add_roles(secilen_rol, kayitli_rol, reason=f"Kayıt: {interaction.user}")

        # Kayıt sayacını güncelle
        kayit_sayaci[interaction.user.id] = kayit_sayaci.get(interaction.user.id, 0) + 1

        # Sonuç embed
        sonuc_embed = discord.Embed(
            title="✅ Kayıt Tamamlandı",
            color=0x2ECC71 if not nick_hata else 0xFFA500,
            timestamp=datetime.datetime.utcnow()
        )
        sonuc_embed.add_field(name="👤 Üye",        value=hedef.mention,    inline=True)
        sonuc_embed.add_field(name="📝 Nick",        value=f"`{yeni_nick}`", inline=True)
        sonuc_embed.add_field(name="🎭 Verilen Rol", value=f"`{rol_adi}` + `{KAYITLI_ROL}`", inline=False)
        if nick_hata:
            sonuc_embed.add_field(name="❗ Uyarı", value=nick_hata, inline=False)
        sonuc_embed.set_footer(text=f"Kaydeden: {interaction.user.display_name}")

        await interaction.response.edit_message(embed=sonuc_embed, view=None)

        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="Üye", style=discord.ButtonStyle.primary, emoji="👤")
    async def uye_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.kayit_yap(interaction, ROL_UYE)

    @discord.ui.button(label="Futbolcu", style=discord.ButtonStyle.success, emoji="⚽")
    async def futbolcu_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.kayit_yap(interaction, ROL_FUTBOLCU)

    @discord.ui.button(label="Takım Başkanı", style=discord.ButtonStyle.danger, emoji="👑")
    async def takim_baskani_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.kayit_yap(interaction, ROL_TAKIM_BASKANI)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


# ─────────────────────────────────────────────
#  KAYITSIZ KOMUTU
# ─────────────────────────────────────────────
@bot.command(name="kayıtsız")
async def kayitsiz(ctx, uye: discord.Member):
    if not kayit_yetkisi_var_mi(ctx.author):
        return await ctx.send(embed=hata_embed("Bu komutu kullanmak için **Kayıt Yetkilisi** rolüne sahip olmalısın!"))

    guild = ctx.guild

    kayitsiz_rol = discord.utils.get(guild.roles, name=KAYITSIZ_ROL)
    if not kayitsiz_rol:
        return await ctx.send(embed=hata_embed(f"`{KAYITSIZ_ROL}` rolü sunucuda bulunamadı!"))

    alinacak_roller = [
        r for r in uye.roles
        if r != guild.default_role and not r.managed
        and r < guild.me.top_role
    ]

    if alinacak_roller:
        await uye.remove_roles(*alinacak_roller, reason=f"Kayıtsız: {ctx.author}")

    await uye.add_roles(kayitsiz_rol, reason=f"Kayıtsız komutu: {ctx.author}")

    try:
        await uye.edit(nick=uye.name, reason="Kayıtsız komutu - nick sıfırlandı")
    except (discord.Forbidden, discord.HTTPException):
        pass

    embed = discord.Embed(
        title="🚫 Kayıtsız",
        description=(
            f"{uye.mention} kullanıcısı kayıtsıza alındı.\n"
            f"🗑️ **{len(alinacak_roller)}** rol silindi.\n"
            f"🏷️ `{KAYITSIZ_ROL}` rolü verildi.\n"
            f"📝 Nick kullanıcı adına sıfırlandı."
        ),
        color=0xFF4C4C,
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text=f"İşlemi yapan: {ctx.author.display_name}")
    await ctx.send(embed=embed)


# ─────────────────────────────────────────────
#  KAYIT SAYISI KOMUTU (.kayıtsayı)
# ─────────────────────────────────────────────
@bot.command(name="kayıtsayı")
async def kayit_say(ctx):
    if not kayit_yetkisi_var_mi(ctx.author):
        return await ctx.send(embed=hata_embed("Bu komutu kullanmak için **Kayıt Yetkilisi** rolüne sahip olmalısın!"))

    if not kayit_sayaci:
        return await ctx.send(embed=discord.Embed(
            description="📋 Henüz hiç kayıt yapılmamış.",
            color=0xFFA500
        ))

    siralama = sorted(kayit_sayaci.items(), key=lambda x: x[1], reverse=True)

    embed = discord.Embed(
        title="📊 Kayıt İstatistikleri",
        color=0x5865F2,
        timestamp=datetime.datetime.utcnow()
    )

    sirali_metin = ""
    for sira, (uye_id, sayi) in enumerate(siralama, 1):
        uye = ctx.guild.get_member(uye_id)
        isim = uye.display_name if uye else f"Bilinmeyen ({uye_id})"
        madalya = "🥇" if sira == 1 else "🥈" if sira == 2 else "🥉" if sira == 3 else f"**{sira}.**"
        sirali_metin += f"{madalya} {isim} — `{sayi}` kayıt\n"

    embed.description = sirali_metin or "Kayıt bulunamadı."
    embed.set_footer(text=f"Toplam kayıt yapan: {len(siralama)} kişi")
    await ctx.send(embed=embed)


# ─────────────────────────────────────────────
#  AFK KOMUTU
# ─────────────────────────────────────────────
@bot.command(name="afk")
async def afk(ctx, *, sebep: str = "Sebep belirtilmedi"):
    afk_listesi[ctx.author.id] = (sebep, datetime.datetime.utcnow())
    await ctx.send(embed=discord.Embed(
        description=f"💤 **{ctx.author.display_name}** AFK moduna geçti.\n📋 Sebep: {sebep}",
        color=0xFFA500))


# ─────────────────────────────────────────────
#  ANTRENMAN KOMUTU
# ─────────────────────────────────────────────
@bot.command(name="antrenman")
async def antrenman(ctx):
    uye = ctx.author
    mevcut = antrenman_sayac.get(uye.id, 0) + 1
    if mevcut > 10:
        mevcut = 1
    antrenman_sayac[uye.id] = mevcut

    dolu = "🟩" * mevcut
    bos  = "⬜" * (10 - mevcut)

    embed = discord.Embed(
        title="🏋️ Antrenman",
        description=f"{uye.mention} antrenman yapıyor!\n\n**{mevcut}/10**\n{dolu}{bos}",
        color=0xF1C40F if mevcut < 10 else 0x2ECC71
    )

    if mevcut < 10:
        embed.set_footer(text=f"{10 - mevcut} antrenman daha kaldı!")
        await ctx.send(embed=embed)
    else:
        embed.set_footer(text="✅ Antrenman tamamlandı! +3M ekleniyor...")
        await ctx.send(embed=embed)

        try:
            uye = await ctx.guild.fetch_member(ctx.author.id)
        except Exception:
            uye = ctx.author

        guncel_isim = uye.nick if uye.nick else uye.name
        yeni_isim, eski_d, yeni_d = antrenman_deger_ekle(guncel_isim, 3)
        if yeni_isim is not None:
            try:
                await uye.edit(nick=yeni_isim)
                await ctx.send(embed=basari_embed(
                    f"💰 {uye.mention} antrenman ödülü aldı: **+3M**\n"
                    f"📊 Değer: `{eski_d}` → `{yeni_d}`\n"
                    f"📝 Yeni isim: `{yeni_isim}`"
                ))
            except (discord.Forbidden, discord.HTTPException):
                await ctx.send(embed=basari_embed(
                    f"💰 {uye.mention} antrenman ödülü: **+3M** kazandı!\n"
                    f"📊 Değer: `{eski_d}` → `{yeni_d}`\n"
                    f"⚠️ İsim otomatik güncellenemedi, lütfen manuel güncelle: `{yeni_isim}`"
                ))
        else:
            await ctx.send(embed=hata_embed(
                f"{uye.mention} 10/10 tamamladı fakat isim formatı hatalı!\n"
                f"Format: `Ad | 1M | takım | SNT` olmalı."
            ))
        antrenman_sayac[uye.id] = 0


# ─────────────────────────────────────────────
#  YARDIM KOMUTU
# ─────────────────────────────────────────────
@bot.command(name="yardım")
async def yardim(ctx):
    embed = discord.Embed(title="📋 Komut Listesi", color=0x5865F2)
    embed.add_field(name="🔒 Kanal", inline=False, value=(
        "`.lock` · `.lock #kanal` · `.unlock`"
    ))
    embed.add_field(name="🔨 Kullanıcı", inline=False, value=(
        "`.ban @u` · `.ban @u sebep` · `.unban isim`\n"
        "`.mute @u` · `.mute @u 30` · `.mute @u 30 sebep` · `.unmute @u`"
    ))
    embed.add_field(name="🗑️ Mesaj", inline=False, value="`.sil 10` — max 10000")
    embed.add_field(name="🎭 Rol", inline=False, value=(
        "`.rolver @u @rol` · `.rolal @u @rol`\n"
        "`.toplurolver @rol` · `.toplurolal @rol`"
    ))
    embed.add_field(name="✏️ İsim / Değer", inline=False, value=(
        "`.isimdeğiştir @u yeniisim`\n"
        "`.dver @u 3M` · `.dsil @u 2M` · `.dsil @u`"
    ))
    embed.add_field(name="📋 Kayıt", inline=False, value=(
        "`.k @u L.Messi | 1M | | SNT` — kayıt türü seçimi\n"
        "`.kayıtsız @u` — üyeyi kayıtsıza al, tüm rolleri sil\n"
        "`.kayıtsayı` — kayıt istatistikleri\n"
        "⚠️ Bu komutlar yalnızca **Kayıt Yetkilisi** rolüyle kullanılabilir."
    ))
    embed.add_field(name="🏋️ Antrenman", inline=False, value=(
        "`.antrenman` — 10/10 tamamlanınca +3M eklenir"
    ))
    embed.add_field(name="💤 AFK", inline=False, value=(
        "`.afk` · `.afk sebep`"
    ))
    embed.set_footer(text=f"Prefix: .  •  {bot.user.name}")
    await ctx.send(embed=embed)


# ─────────────────────────────────────────────
#  HATA YÖNETİMİ
# ─────────────────────────────────────────────
@bot.event
async def on_command_error(ctx, error):
    if hasattr(ctx.command, 'on_error'):
        return
    if isinstance(error, commands.CommandInvokeError):
        error = error.original
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=hata_embed("Bu komutu kullanmak için yetkiniz yok!"))
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send(embed=hata_embed("Kullanıcı bulunamadı!"))
    elif isinstance(error, commands.RoleNotFound):
        await ctx.send(embed=hata_embed("Rol bulunamadı!"))
    elif isinstance(error, commands.BadArgument):
        await ctx.send(embed=hata_embed("Geçersiz argüman!"))
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=hata_embed(f"Eksik argüman: `{error.param.name}`"))
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        pass


TOKEN = os.getenv("DISCORD_TOKEN")

if __name__ == "__main__":
    if not TOKEN:
        print("❌ HATA: DISCORD_TOKEN environment variable bulunamadı!")
        print("Railway'de Variables sekmesinden DISCORD_TOKEN ekleyin.")
        exit(1)
    bot.run(TOKEN)
