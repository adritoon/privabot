import discord
import os
import aiohttp
import io
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands

# 1. CARGA DE VARIABLES
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if not TOKEN:
    raise ValueError("❌ Error: No se encontró el token en el archivo .env")

# 2. CONFIGURACIÓN
intents = discord.Intents.default()
intents.message_content = True 
client = commands.Bot(command_prefix="!", intents=intents)

# -----------------------------------------------------------
# 3. LA VISTA FINAL (EL CANDADO) - CON TIMEOUT Y SINGLE-USE
# -----------------------------------------------------------
class SecretView(discord.ui.View):
    def __init__(self, allowed_users: list[discord.User], secret_text: str = None, 
                 file_url: str = None, filename: str = "archivo"):
        # Timeout de 24 horas para limpiar memoria
        super().__init__(timeout=86400)  
        self.allowed_users = allowed_users
        self.secret_text = secret_text
        self.file_url = file_url
        self.filename = filename
        self._used_by = set()  # Tracking de usuarios que ya vieron el contenido

    async def on_timeout(self):
        """Limpia la vista cuando expira el timeout"""
        self.clear_items()
        
    @discord.ui.button(label="Ver Contenido Oculto", style=discord.ButtonStyle.blurple, emoji="🔒")
    async def show_content(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        # Validación de permisos
        if interaction.user not in self.allowed_users:
            await interaction.response.send_message(
                "⛔ No tienes permiso para ver esto.", 
                ephemeral=True
            )
            return

        # Evitar múltiples clicks del mismo usuario
        if interaction.user.id in self._used_by:
            await interaction.response.send_message(
                "ℹ️ Ya has visto este contenido. Revisa tus mensajes efímeros anteriores.",
                ephemeral=True
            )
            return
        
        self._used_by.add(interaction.user.id)
        await interaction.response.defer(ephemeral=True)

        files_to_send = []
        descripcion_embed = "Este contenido es invisible para los demás."

        # Lógica de texto inteligente
        if self.secret_text:
            if len(self.secret_text) <= 4096:
                descripcion_embed = self.secret_text
            else:
                buffer_texto = io.BytesIO(self.secret_text.encode('utf-8'))
                archivo_texto = discord.File(buffer_texto, filename="mensaje_secreto.txt")
                files_to_send.append(archivo_texto)
                descripcion_embed = "📜 **El texto es muy largo**, te lo envío como archivo adjunto."

        embed = discord.Embed(
            title="🕵️ Archivo Clasificado", 
            description=descripcion_embed,
            color=discord.Color.green()
        )
        embed.set_footer(text="Mensaje seguro vía Bot.")

        # Lógica de archivos con manejo de errores mejorado
        if self.file_url:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.file_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            # Verificar tamaño antes de descargar (límite 25MB)
                            content_length = resp.headers.get('Content-Length')
                            if content_length and int(content_length) > 25 * 1024 * 1024:
                                embed.add_field(
                                    name="⚠️ Archivo muy grande", 
                                    value="El archivo excede el límite de 25MB de Discord.", 
                                    inline=False
                                )
                            else:
                                data = await resp.read()
                                archivo_virtual = discord.File(io.BytesIO(data), filename=self.filename)
                                files_to_send.append(archivo_virtual)
                                
                                es_imagen = any(ext in self.filename.lower() 
                                              for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp'])
                                if es_imagen:
                                    embed.set_image(url=f"attachment://{self.filename}")
                        else:
                            embed.add_field(
                                name="Error", 
                                value=f"No se pudo recuperar el archivo (Status: {resp.status})", 
                                inline=False
                            )
            except aiohttp.ClientError as e:
                embed.add_field(name="Error de conexión", value=f"No se pudo descargar el archivo: {str(e)}", inline=False)
            except Exception as e:
                embed.add_field(name="Error inesperado", value="Ocurrió un error al procesar el archivo.", inline=False)

        await interaction.followup.send(embed=embed, files=files_to_send, ephemeral=True)

# -----------------------------------------------------------
# 4. VISTA DE SELECCIÓN (SIN REFERENCIA CIRCULAR)
# -----------------------------------------------------------
class RecipientSelect(discord.ui.UserSelect):
    def __init__(self, sender, secret_text, file_url, filename):
        super().__init__(placeholder="Busca y selecciona a los destinatarios...", min_values=1, max_values=25)
        self.sender = sender
        self.secret_text = secret_text
        self.file_url = file_url
        self.filename = filename

    async def callback(self, interaction: discord.Interaction):
        selected_users = self.values 
        
        # Crear lista de permisos incluyendo al remitente
        lista_permisos = list(selected_users)
        if self.sender not in lista_permisos:
            lista_permisos.append(self.sender)

        final_view = SecretView(
            allowed_users=lista_permisos, 
            secret_text=self.secret_text, 
            file_url=self.file_url, 
            filename=self.filename
        )

        menciones = ", ".join([u.mention for u in selected_users])
        
        embed_publico = discord.Embed(
            title="📨 Mensaje Protegido",
            description=f"{self.sender.mention} ha enviado un contenido secreto para: {menciones}.",
            color=discord.Color.dark_grey()
        )
        embed_publico.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/3064/3064197.png") 
        embed_publico.add_field(name="Instrucciones", value="Haz clic en el botón de abajo para verificar tu identidad.")

        await interaction.channel.send(embed=embed_publico, view=final_view)
        await interaction.response.edit_message(
            content=f"✅ ¡Enviado exitosamente a {len(selected_users)} personas!", 
            view=None
        )

class RecipientSelectView(discord.ui.View):
    def __init__(self, sender, secret_text, file_url, filename):
        super().__init__(timeout=300)  # 5 minutos para seleccionar
        self.add_item(RecipientSelect(sender, secret_text, file_url, filename))

# -----------------------------------------------------------
# 5. EVENTOS Y COMANDO
# -----------------------------------------------------------
@client.event
async def on_ready():
    print(f'✅ Bot conectado como: {client.user}')
    try:
        synced = await client.tree.sync()
        print(f"🔄 Sincronizados {len(synced)} comandos.")
    except Exception as e:
        print(f"❌ Error al sincronizar comandos: {e}")

@client.tree.command(
    name="secreto", 
    description="Sube contenido y selecciona después quién puede verlo."
)
@app_commands.describe(
    mensaje="Escribe algo (Opcional)", 
    archivo="Sube un archivo (Opcional)"
)
@app_commands.checks.cooldown(1, 10)  # Cooldown: 1 uso cada 10 segundos por usuario
async def secreto(interaction: discord.Interaction, mensaje: str = None, archivo: discord.Attachment = None):
    
    if not mensaje and not archivo:
        await interaction.response.send_message(
            "❌ Debes enviar al menos un mensaje o un archivo.", 
            ephemeral=True
        )
        return

    # Validar tamaño de mensaje
    if mensaje and len(mensaje) > 10000:
        await interaction.response.send_message(
            "❌ El mensaje es demasiado largo (máximo 10,000 caracteres).", 
            ephemeral=True
        )
        return

    url_archivo = archivo.url if archivo else None
    nombre_archivo = archivo.filename if archivo else "archivo"

    view = RecipientSelectView(
        sender=interaction.user, 
        secret_text=mensaje, 
        file_url=url_archivo, 
        filename=nombre_archivo
    )

    await interaction.response.send_message(
        "📂 **Contenido cargado.** \n👇 Ahora selecciona abajo quiénes podrán verlo (puedes elegir varios):", 
        view=view, 
        ephemeral=True
    )

@secreto.error
async def secreto_error(interaction: discord.Interaction, error):
    """Maneja errores del comando"""
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"⏳ Espera {error.retry_after:.1f} segundos antes de usar este comando de nuevo.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "❌ Ocurrió un error inesperado. Intenta de nuevo.",
            ephemeral=True
        )

if __name__ == "__main__":
    client.run(TOKEN)