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
# 3. LA VISTA FINAL (EL CANDADO)
# -----------------------------------------------------------
class SecretView(discord.ui.View):
    def __init__(self, allowed_users: list[discord.User], secret_text: str = None, file_url: str = None, filename: str = "archivo"):
        super().__init__(timeout=None) 
        self.allowed_users = allowed_users
        self.secret_text = secret_text
        self.file_url = file_url
        self.filename = filename

    @discord.ui.button(label="Ver Contenido Oculto", style=discord.ButtonStyle.blurple, emoji="🔒")
    async def show_content(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        # Validación: ¿Está el usuario en la lista?
        if interaction.user not in self.allowed_users:
            await interaction.response.send_message(
                f"⛔ No tienes permiso para ver esto.", 
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="🕵️ Archivo Clasificado", 
            description="Este contenido es invisible para los demás.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Mensaje seguro vía Bot.")

        if self.secret_text:
            embed.add_field(name="Mensaje:", value=self.secret_text, inline=False)

        files_to_send = []

        if self.file_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.file_url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        archivo_virtual = discord.File(io.BytesIO(data), filename=self.filename)
                        files_to_send.append(archivo_virtual)
                        
                        es_imagen = any(ext in self.filename.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp'])
                        if es_imagen:
                            embed.set_image(url=f"attachment://{self.filename}")
                    else:
                        embed.add_field(name="Error", value="No se pudo recuperar el archivo original.", inline=False)

        await interaction.followup.send(embed=embed, files=files_to_send, ephemeral=True)

# -----------------------------------------------------------
# 4. LA NUEVA VISTA DE SELECCIÓN (EL MENÚ DE USUARIOS)
# -----------------------------------------------------------
class RecipientSelect(discord.ui.UserSelect):
    def __init__(self, parent_view):
        # max_values=25 es el límite de Discord por menú
        super().__init__(placeholder="Busca y selecciona a los destinatarios...", min_values=1, max_values=25)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        # Esta función se ejecuta cuando el usuario selecciona gente y cierra el menú
        
        # Guardamos los usuarios seleccionados
        selected_users = self.values # Lista de usuarios seleccionados
        
        # Recuperamos los datos que guardamos en la vista padre
        mensaje = self.parent_view.secret_text
        url_archivo = self.parent_view.file_url
        nombre_archivo = self.parent_view.filename
        original_sender = self.parent_view.sender

        # Creamos la vista final (el candado) con la lista de usuarios elegidos
        final_view = SecretView(allowed_users=selected_users, secret_text=mensaje, file_url=url_archivo, filename=nombre_archivo)

        # Construimos el mensaje público
        menciones = ", ".join([u.mention for u in selected_users])
        embed_publico = discord.Embed(
            title="📨 Mensaje Protegido",
            description=f"{original_sender.mention} ha enviado un contenido secreto para: {menciones}.",
            color=discord.Color.dark_grey()
        )
        embed_publico.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/3064/3064197.png") 
        embed_publico.add_field(name="Instrucciones", value="Haz clic en el botón de abajo para verificar tu identidad.")

        # ENVIAMOS EL MENSAJE PÚBLICO AL CANAL
        # Usamos interaction.channel.send porque interaction.response ya se usó para el menú
        await interaction.channel.send(embed=embed_publico, view=final_view)

        # Avisamos al remitente que ya se envió y borramos el menú de selección
        await interaction.response.edit_message(content=f"✅ ¡Enviado exitosamente a {len(selected_users)} personas!", view=None)

class RecipientSelectView(discord.ui.View):
    def __init__(self, sender, secret_text, file_url, filename):
        super().__init__()
        self.sender = sender
        self.secret_text = secret_text
        self.file_url = file_url
        self.filename = filename
        
        # Añadimos el componente de selección a esta vista
        self.add_item(RecipientSelect(self))

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
        print(f"❌ Error: {e}")

@client.tree.command(name="secreto", description="Sube contenido y selecciona después quién puede verlo.")
@app_commands.describe(
    mensaje="Escribe algo (Opcional)", 
    archivo="Sube un archivo (Opcional)"
)
async def secreto(interaction: discord.Interaction, mensaje: str = None, archivo: discord.Attachment = None):
    
    if not mensaje and not archivo:
        await interaction.response.send_message("❌ Debes enviar al menos un mensaje o un archivo.", ephemeral=True)
        return

    url_archivo = archivo.url if archivo else None
    nombre_archivo = archivo.filename if archivo else "archivo"

    # AQUÍ ESTÁ EL CAMBIO:
    # No pedimos usuario todavía. Creamos la vista de selección.
    view = RecipientSelectView(sender=interaction.user, secret_text=mensaje, file_url=url_archivo, filename=nombre_archivo)

    # Enviamos un mensaje EFÍMERO (solo tú lo ves) con el menú para elegir gente
    await interaction.response.send_message(
        "📂 **Contenido cargado.** \n👇 Ahora selecciona abajo quiénes podrán verlo (puedes elegir varios):", 
        view=view, 
        ephemeral=True
    )

if __name__ == "__main__":
    client.run(TOKEN)