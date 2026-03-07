from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger("VisionAlign.TimezoneUtils")
try:
    from dateutil import tz
    # Tenta obter o fuso horário de São Paulo (Horário de Brasília)
    TARGET_DISPLAY_TIMEZONE = tz.gettz('America/Sao_Paulo')
    if TARGET_DISPLAY_TIMEZONE:
        logger.info(f"Usando dateutil.tz. Fuso horário de exibição configurado para: America/Sao_Paulo ({TARGET_DISPLAY_TIMEZONE.tzname(datetime.now())})")
    else:
        # Fallback para o fuso horário local da máquina se 'America/Sao_Paulo' não for encontrado
        TARGET_DISPLAY_TIMEZONE = tz.tzlocal()
        logger.warning(f"Fuso 'America/Sao_Paulo' não encontrado. Usando fuso local da máquina: {TARGET_DISPLAY_TIMEZONE.tzname(datetime.now()) if TARGET_DISPLAY_TIMEZONE else 'Desconhecido'}")
except ImportError:
    TARGET_DISPLAY_TIMEZONE = None
    logger.warning("Biblioteca 'python-dateutil' não encontrada. "
                   "A conversão para fuso horário local pode ser limitada. "
                   "Considere instalar com: pip install python-dateutil")

def get_current_utc_timestamp() -> datetime:
    return datetime.now(timezone.utc)

def get_current_timestamp_for_storage(dt=None) -> str:
    """
    Retorna o timestamp atual ou converte o datetime fornecido para o formato de armazenamento.
    Args:
        dt (datetime, optional): Datetime para converter. Se None, usa o momento atual.
    Returns:
        str: Timestamp no formato 'YYYY-MM-DD HH:MM:SS'
    """
    try:
        if dt is None:
            dt = get_current_utc_timestamp()
        elif not isinstance(dt, datetime):
            logger.error(f"get_current_timestamp_for_storage recebeu tipo inválido: {type(dt)}")
            # Se receber tipo inválido, usa timestamp atual
            dt = get_current_utc_timestamp()
            
        # Se o datetime é timezone-aware, converte para UTC
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        # Se é naive, assume que já está em UTC
        
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logger.error(f"Erro em get_current_timestamp_for_storage: {e}")
        # Em caso de erro, retorna timestamp atual
        return get_current_utc_timestamp().strftime('%Y-%m-%d %H:%M:%S')

def parse_stored_timestamp_to_utc(timestamp_str: str) -> datetime | None:

    if not timestamp_str:
        return None
    try:
        # Assume que o formato é YYYY-MM-DD HH:MM:SS
        dt_naive = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        return dt_naive.replace(tzinfo=timezone.utc) # Torna timezone-aware como UTC
    except ValueError:
        logger.error(f"Falha ao parsear timestamp '{timestamp_str}' para UTC.", exc_info=False)
        return None

def format_datetime_for_storage(dt_object: datetime) -> str:
    """
    Formats a given datetime object into the standard string format ('YYYY-MM-DD HH:MM:SS')
    representing UTC.
    If the input datetime is naive, it's assumed to be UTC.
    If the input datetime is timezone-aware, it's converted to UTC.
    """
    if not isinstance(dt_object, datetime):
        logger.error(f"format_datetime_for_storage received non-datetime object: {type(dt_object)}")
        return "INVALID_DATETIME_INPUT" 
    
    if dt_object.tzinfo is None or dt_object.tzinfo.utcoffset(dt_object) is None:
        # Naive datetime, assume it's UTC
        dt_utc = dt_object.replace(tzinfo=timezone.utc)
    else:
        # Timezone-aware datetime, convert to UTC
        dt_utc = dt_object.astimezone(timezone.utc)
    
    return dt_utc.strftime('%Y-%m-%d %H:%M:%S')

def convert_utc_to_local_display(utc_dt: datetime) -> str | None:
    if not utc_dt:
        return None
    if TARGET_DISPLAY_TIMEZONE: # Usa o fuso horário de exibição alvo (Brasil)
        local_dt = utc_dt.astimezone(TARGET_DISPLAY_TIMEZONE)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S') # Ou outro formato desejado para exibição
    return utc_dt.strftime('%Y-%m-%d %H:%M:%S (UTC)')