import smtplib
import os
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

logger = logging.getLogger("VisionAlign.Email")
_config = None

def set_email_config(config):
    """Define a configuração global de e-mail."""
    global _config
    _config = config
    logger.info("Configuração de e-mail atualizada.")

def send_fracture_alert_email(recipients, subject, body_text, image_path=None, roi_path=None):
    """
    Envia um e-mail de alerta com um relatório visual das fraturas detectadas.
    """
    if _config:
        enabled = _config.get('enabled', False)
        smtp_server = _config.get('smtp_server')
        smtp_port = int(_config.get('smtp_port', 587))
        smtp_user = _config.get('smtp_username')
        smtp_password = _config.get('smtp_password')
        smtp_sender = _config.get('smtp_sender')
    else:
        enabled = os.getenv('EMAIL_NOTIFICATIONS_ENABLED', 'false').lower() == 'true'
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = int(os.getenv('SMTP_PORT', 587))
        smtp_user = os.getenv('SMTP_USERNAME')
        smtp_password = os.getenv('SMTP_PASSWORD')
        smtp_sender = os.getenv('SMTP_SENDER')

    try:
        msg = MIMEMultipart('related') # 'related' é necessário para imagens inline
        msg['From'] = f"VisionAlign Alert <{smtp_sender}>"
        msg['To'] = ", ".join(recipients) if isinstance(recipients, list) else recipients
        msg['Subject'] = f"🚨 {subject}"

        # Template HTML do Relatório
        html_content = f"""
        <html>
        <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; background-color: #f4f7f6; padding: 20px;">
            <div style="max-width: 700px; margin: 0 auto; background: #fff; border-radius: 12px; border: 1px solid #e0e0e0; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                
                <div style="background-color: #dc3545; color: white; padding: 20px; text-align: center;">
                    <h2 style="margin: 0; text-transform: uppercase; letter-spacing: 1px;">Relatório de Detecção de Fratura</h2>
                    <p style="margin: 5px 0 0 0; opacity: 0.9;">VisionFracture AI • Sistema de Análise em Tempo Real</p>
                </div>

                <div style="padding: 30px;">
                    <p style="font-size: 16px;"><strong>Status:</strong> <span style="color: #dc3545;">Fratura Detectada</span></p>
                    <p style="background: #fff3f3; border-left: 4px solid #dc3545; padding: 15px; font-style: italic;">
                        {body_text}
                    </p>

                    <h3 style="color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px; margin-top: 30px;">Evidências Visuais</h3>
                    
                    <div style="margin-top: 20px;">
                        {"<div style='text-align: center; margin-bottom: 30px;'>" 
                          "<p style='font-size: 14px; color: #666; font-weight: bold; margin-bottom: 10px;'>VISTA COMPLETA (COM DETECÇÕES)</p>"
                          "<img src='cid:main_image' style='width: 100%; max-width: 100%; border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 2px 5px rgba(0,0,0,0.1);'>"
                          "</div>" if image_path else ""}
                        
                        {"<div style='text-align: center;'>"
                          "<p style='font-size: 14px; color: #666; font-weight: bold; margin-bottom: 10px;'>DETALHE DA FRATURA (ROI)</p>"
                          "<img src='cid:roi_image' style='max-width: 100%; border-radius: 8px; border: 2px solid #dc3545; box-shadow: 0 2px 5px rgba(0,0,0,0.1);'>"
                          "</div>" if roi_path else ""}
                    </div>

                    <div style="margin-top: 40px; text-align: center;">
                        <a href="#" style="background-color: #2c3e50; color: white; padding: 12px 25px; text-decoration: none; border-radius: 6px; font-weight: bold;">Acessar Prontuário Completo</a>
                    </div>
                </div>

                <div style="background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 11px; color: #999;">
                    Este é um e-mail automático gerado pelo sistema VisionFracture. <br>
                    Data do Processamento: {os.path.basename(image_path) if image_path else 'N/A'}
                </div>
            </div>
        </body>
        </html>
        """

        # Attach do HTML
        msg.attach(MIMEText(html_content, 'html'))

        # Função auxiliar para embutir as imagens
        def embed_image(path, cid_name):
            if path and os.path.exists(path):
                with open(path, 'rb') as f:
                    img = MIMEImage(f.read())
                    img.add_header('Content-ID', f'<{cid_name}>')
                    img.add_header('Content-Disposition', 'inline', filename=os.path.basename(path))
                    msg.attach(img)

        embed_image(image_path, 'main_image')
        embed_image(roi_path, 'roi_image')

        # Envio via SMTP
        with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
            if smtp_port == 587:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info(f"Relatório de fratura enviado para {recipients}")
        return True

    except Exception as e:
        logger.error(f"Falha crítica ao enviar relatório: {e}")
        return False

def send_password_reset_email(recipient_email, reset_link):
    """
    Envia um email com o link para reset de senha renderizado em HTML.
    """
    if _config:
        smtp_server = _config.get('smtp_server')
        smtp_port = int(_config.get('smtp_port', 587))
        smtp_user = _config.get('smtp_username')
        smtp_password = _config.get('smtp_password')
        smtp_sender = _config.get('smtp_sender')
    else:
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = int(os.getenv('SMTP_PORT', 587))
        smtp_user = os.getenv('SMTP_USERNAME')
        smtp_password = os.getenv('SMTP_PASSWORD')
        smtp_sender = os.getenv('SMTP_SENDER')

    if not smtp_server or not smtp_sender:
        logger.error("Configurações de SMTP incompletas no arquivo .env.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = f"VisionAlign <{smtp_sender}>"
        msg['To'] = recipient_email
        msg['Subject'] = "[VisionAlign] Recuperação de Senha"

        # Template HTML
        body_html = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; border: 1px solid #e9ecef;">
                <h2 style="color: #007bff; text-align: center;">Redefinição de Senha</h2>
                <p>Olá,</p>
                <p>Recebemos uma solicitação para redefinir a senha da sua conta <strong>VisionAlign</strong>.</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" style="background-color: #007bff; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                        Redefinir minha senha
                    </a>
                </div>

                <p style="font-size: 0.9em; color: #666;">
                    Se o botão não funcionar, copie e cole este link no seu navegador:<br>
                    <a href="{reset_link}" style="color: #007bff; word-break: break-all;">{reset_link}</a>
                </p>

                <hr style="border: 0; border-top: 1px solid #ddd; margin: 20px 0;">
                
                <p style="font-size: 0.8em; color: #888; text-align: center;">
                    Este link expira em <strong>1 hora</strong>. Se você não solicitou esta alteração, ignore este e-mail.
                </p>
                <p style="text-align: center; font-weight: bold;">Equipe VisionAlign</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(body_html, 'html'))
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        server.set_debuglevel(0)
        
        if smtp_port == 587:
            server.starttls()
            
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
            
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email de reset enviado para {recipient_email}")
        return True

    except Exception as e:
        logger.error(f"Erro ao enviar email de reset: {e}")
        return False