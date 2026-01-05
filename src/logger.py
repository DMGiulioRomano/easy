# =============================================================================
# logger.py - Gestione logging per envelope clip warnings
# =============================================================================
import logging
from datetime import datetime
import os

# =============================================================================
# CONFIGURAZIONE
# =============================================================================
CLIP_LOG_CONFIG = {
    'enabled': True,                    # Master switch: False disabilita tutto
    'console_enabled': True,            # Stampa su terminale
    'file_enabled': True,               # Scrive su file
    'log_dir': './logs',                # Directory per i file di log
    'log_filename': None,               # None = auto-genera con timestamp
}

_clip_logger = None
_clip_logger_initialized = False


# =============================================================================
# FUNZIONI PUBBLICHE
# =============================================================================

def configure_clip_logger(
    enabled=True,
    console_enabled=True,
    file_enabled=True,
    log_dir='./logs',
    yaml_name=None        # <-- NUOVO: nome del file YAML
):
    """
    Configura il logger per i clip warnings.
    Chiamare PRIMA di creare qualsiasi Stream.
    
    Args:
        enabled: Master switch - se False, nessun logging
        console_enabled: Se True, stampa warning su terminale
        file_enabled: Se True, scrive su file
        log_dir: Directory dove salvare i file di log
        yaml_name: Nome del file YAML (senza path, senza estensione)
                   Il file sarà: envelope_clips_{yaml_name}.log
    """
    global CLIP_LOG_CONFIG, _clip_logger, _clip_logger_initialized
    
    CLIP_LOG_CONFIG['enabled'] = enabled
    CLIP_LOG_CONFIG['console_enabled'] = console_enabled
    CLIP_LOG_CONFIG['file_enabled'] = file_enabled
    CLIP_LOG_CONFIG['log_dir'] = log_dir
    CLIP_LOG_CONFIG['yaml_name'] = yaml_name  # <-- NUOVO
    
    # Reset logger per ri-inizializzazione
    _clip_logger = None
    _clip_logger_initialized = False

def get_clip_logger():
    """
    Ottiene il logger per i clip warnings (lazy initialization).
    Rispetta la configurazione in CLIP_LOG_CONFIG.
    
    Returns:
        logging.Logger o None se disabilitato
    """
    global _clip_logger, _clip_logger_initialized
    
    # Se già inizializzato, ritorna (anche se None)
    if _clip_logger_initialized:
        return _clip_logger
    
    _clip_logger_initialized = True
    
    # Master switch
    if not CLIP_LOG_CONFIG['enabled']:
        _clip_logger = None
        return None
    
    # Se né console né file sono abilitati, disabilita
    if not CLIP_LOG_CONFIG['console_enabled'] and not CLIP_LOG_CONFIG['file_enabled']:
        _clip_logger = None
        return None
    
    # Crea logger
    _clip_logger = logging.getLogger('envelope_clip')
    _clip_logger.setLevel(logging.WARNING)
    _clip_logger.handlers = []  # Pulisci handler esistenti
    
    # === FILE HANDLER ===
    if CLIP_LOG_CONFIG['file_enabled']:
        log_dir = CLIP_LOG_CONFIG['log_dir']
        
        # Crea directory se non esiste
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            print(f"📁 Creata directory log: {log_dir}")
        
        # Nome file
        if CLIP_LOG_CONFIG.get('yaml_name'):
            # Usa nome YAML
            yaml_name = CLIP_LOG_CONFIG['yaml_name']
            log_filename = f'envelope_clips_{yaml_name}.log'
        else:
            # Fallback: timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f'envelope_clips_{timestamp}.log'
        
        log_path = os.path.join(log_dir, log_filename)
        
        file_handler = logging.FileHandler(log_path, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.WARNING)
        file_format = logging.Formatter(
            '%(asctime)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        _clip_logger.addHandler(file_handler)
        
        print(f"📝 Clip log file: {log_path}")
    
    # === CONSOLE HANDLER ===
    if CLIP_LOG_CONFIG['console_enabled']:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_format = logging.Formatter('⚠️  CLIP: %(message)s')
        console_handler.setFormatter(console_format)
        _clip_logger.addHandler(console_handler)
    
    return _clip_logger

def get_clip_log_path():
    """
    Ritorna il percorso del file di log corrente (se esiste).
    
    Returns:
        str o None
    """
    if _clip_logger is None:
        return None
    
    for handler in _clip_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            return handler.baseFilename
    return None


def log_clip_warning(stream_id, param_name, time, raw_value, clipped_value, 
                     min_val, max_val, is_envelope=False):
    """
    Logga un warning per un valore clippato.
    
    Args:
        stream_id: ID dello stream
        param_name: nome del parametro
        time: tempo in secondi
        raw_value: valore originale
        clipped_value: valore dopo il clip
        min_val: limite minimo
        max_val: limite massimo
        is_envelope: True se il valore viene da un Envelope
    """
    logger = get_clip_logger()
    
    if logger is None:
        return
    
    # Calcola bound violato
    if raw_value < min_val:
        deviation = raw_value - min_val
        bound_type = "MIN"
        bound_value = min_val
    else:
        deviation = raw_value - max_val
        bound_type = "MAX"
        bound_value = max_val
    
    source_type = "ENV" if is_envelope else "FIX"
    
    logger.warning(
        f"[{stream_id}] {param_name:<20} | "
        f"t={time:>7.3f}s | "
        f"raw={raw_value:>12.6f} → clip={clipped_value:>12.6f} | "
        f"{bound_type}={bound_value:>10.4f} | "
        f"Δ={deviation:>+10.6f} | "
        f"({source_type})"
    )
    