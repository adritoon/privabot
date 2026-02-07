import discord
import os
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands

# -----------------------------------------------------------
# 1. CARGA DE VARIABLES DE ENTORNO
# -----------------------------------------------------------
load_dotenv()  # Carga el archivo .env
TOKEN = os.getenv('DISCORD_TOKEN')

# Verificación de seguridad: Si no hay token, detenemos el programa
if not TOKEN:
    raise ValueError("❌ Error: No se encontró el token en el archivo .env")

# -----------------------------------------------------------
# 2. CONFIGURACIÓN DEL BOT
# -----------------------------------------------------------
intents = discord.Intents.default()
# Necesario para leer contenido de mensajes si usas comandos con prefijo (!),
# aunque para Slash Commands (/) es menos estricto, es buena práctica activarlo.
intents.message_content = True 

client = commands.Bot(command_prefix="!", intents=intents)

# -----------------------------------------------------------
# 3. LA CLASE DE LA VISTA (EL BOTÓN)
# -----------------------------------------------------------
class SecretImageView(discord.ui.View):
    def __init__(self, target_user: discord.User, image_url: str):
        # timeout=None hace que el botón no deje de funcionar después de un tiempo
        super().__init__(timeout=None) 
        self.target_user = target_user
        self.image_url = image_url

    @discord.ui.button(label="Ver Imagen Secreta", style=discord.ButtonStyle.blurple, emoji="🔒")
    async def show_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Esta función se ejecuta cuando alguien hace clic en el botón.
        """
        # A. Validación: ¿Quién hizo clic?
        if interaction.user != self.target_user:
            # Si no es el destinatario, mensaje de error efímero
            await interaction.response.send_message(
                f"⛔ ¡Alto ahí! Esta imagen es confidencial solo para {self.target_user.mention}.", 
                ephemeral=True
            )
            return

        # B. Éxito: Construir el embed con la imagen
        embed = discord.Embed(
            title="🕵️ Archivo Clasificado", 
            description="Esta imagen desaparecerá de tu vista si cierras esta 'respuesta'.",
            color=discord.Color.green()
        )
        embed.set_image(url=self.image_url)
        embed.set_footer(text="Mensaje seguro vía Bot.")
        
        # C. Enviar la respuesta Efímera (SOLO visible para el usuario que clicó)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# -----------------------------------------------------------
# 4. EVENTOS DEL BOT
# -----------------------------------------------------------
@client.event
async def on_ready():
    print(f'✅ Bot conectado como: {client.user}')
    try:
        # Sincroniza los comandos Slash con los servidores de Discord
        synced = await client.tree.sync()
        print(f"🔄 Sincronizados {len(synced)} comandos Slash exitosamente.")
    except Exception as e:
        print(f"❌ Error al sincronizar comandos: {e}")

# -----------------------------------------------------------
# 5. EL COMANDO SLASH (/secreto)
# -----------------------------------------------------------
@client.tree.command(name="secreto", description="Envía una imagen oculta visible solo para un usuario específico.")
@app_commands.describe(usuario="Usuario que podrá ver la imagen", imagen="Sube el archivo de imagen aquí")
async def secreto(interaction: discord.Interaction, usuario: discord.User, imagen: discord.Attachment):
    
    # Validación: Verificar que el archivo sea realmente una imagen
    if not imagen.content_type or not imagen.content_type.startswith("image/"):
        await interaction.response.send_message("❌ El archivo subido no es una imagen válida.", ephemeral=True)
        return

    # Creamos la vista (botón) pasándole los datos necesarios
    view = SecretImageView(target_user=usuario, image_url=imagen.url)

    # Creamos el mensaje público (el "cebo")
    embed_publico = discord.Embed(
        title="📨 Mensaje Protegido",
        description=f"{interaction.user.mention} ha dejado una imagen **solo para los ojos de** {usuario.mention}.",
        color=discord.Color.dark_grey()
    )
    embed_publico.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/3064/3064197.png") # Icono de candado opcional
    embed_publico.add_field(name="Instrucciones", value="Haz clic en el botón de abajo para verificar tu identidad.")

    # Enviamos el mensaje al canal
    await interaction.response.send_message(embed=embed_publico, view=view)

# -----------------------------------------------------------
# 6. EJECUCIÓN
# -----------------------------------------------------------
if __name__ == "__main__":
    client.run(TOKEN)