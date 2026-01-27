"""
VoiceManager - Gestione voci multiple nella sintesi granulare.

Responsabilità:
- Gestione dinamica del numero di voci attive (num_voices)
- Calcolo moltiplicatori pitch per ogni voce (pattern alternato +/-)
- Calcolo offset pointer per ogni voce (pattern alternato +/-)
"""

from typing import Dict, Optional, Union
from envelope import Envelope
from parameter_factory import ParameterFactory
from parameter_schema import VOICE_PARAMETER_SCHEMA
from parameter_orchestrator import ParameterOrchestrator
from orchestration_config import OrchestrationConfig


class VoiceManager:
    """
    Gestisce le voci multiple di uno stream granulare.
    
    Attributes:
        stream_id: ID dello stream (per logging)
        sample_dur_sec: Durata del sample (per scaling pointer offset)
        num_voices: Parameter per numero di voci
        voice_pitch_offset: Parameter per offset pitch
        voice_pointer_offset: Parameter per offset pointer normalizzato
        voice_pointer_range: Parameter per range stocastico pointer
        max_voices: Numero massimo di voci (cache)
    """
    
    def __init__(
        self,
        params: dict,                      # 1. Dati specifici
        config: OrchestrationConfig,       # 2. Regole processo
        stream_id: str,                    # 3. Context identità
        duration: float,                   # 4. Context timing
        time_mode: str = 'absolute'        # 6. Context mode
    ):
        """
        Inizializza il VoiceManager.
        
        Args:
            params: dict con parametri voci dal YAML
            stream_id: ID dello stream (per logging)
            duration: durata dello stream (per normalizzazione envelope)
            sample_dur_sec: Durata del sample in secondi
            time_mode: 'absolute' o 'normalized' (default per envelope)
        """
        self.stream_id = stream_id
        
        # Create orchestrator
        self._orchestrator = ParameterOrchestrator(
            stream_id=stream_id,
            duration=duration,
            time_mode=time_mode,
            config=config
        )

        # Carica tutti i parametri delle voci
        self._loaded_params = self._orchestrator.create_all_parameters(
            params,
            schema=VOICE_PARAMETER_SCHEMA
        )
        
        for name, param in self._loaded_params.items():
            setattr(self, name, param)                
        # Cache max voices
        self._max_voices = self._calculate_max_voices()
    
    # =========================================================================
    # CALCOLO MAX VOICES
    # =========================================================================
    
    def _calculate_max_voices(self) -> int:
        """
        Calcola il massimo numero di voci dall'envelope/valore.
        
        Se num_voices è un Envelope, prende il max dei breakpoints e lo clippa
        ai bounds definiti in parameter_definitions.py.
        """
        if self.num_voices is None:
            return 1
        
        # Estrai il valore base (potrebbe essere Envelope o numero)
        raw_value = self.num_voices.value
        
        if isinstance(raw_value, Envelope):
            # Per envelope: massimo di tutti i breakpoints
            raw_max = max(point[1] for point in raw_value.breakpoints)
        else:
            # Per numero fisso
            raw_max = raw_value
                
        return int(raw_max)
    
    @property
    def max_voices(self) -> int:
        """
        Restituisce il numero massimo assoluto di voci.
        Usato per allocazione iniziale (iterazione su tutte le voci potenziali).
        """
        return self._max_voices
    
    # =========================================================================
    # VOCI ATTIVE
    # =========================================================================
    
    def get_active_voices(self, elapsed_time: float) -> int:
        """
        Restituisce quante voci sono attive al tempo specificato.
        
        Args:
            elapsed_time: Tempo trascorso dall'onset dello stream
            
        Returns:
            int: Numero di voci attive (1 <= n <= max_voices)
        """
        if self.num_voices is None:
            return 1
        
        raw_value = self.num_voices.get_value(elapsed_time)
        
        # Round + clamp a range valido (max_voices già rispetta i bounds)
        active = int(round(raw_value))
        return max(1, min(self._max_voices, active))
    
    # =========================================================================
    # PATTERN ALTERNATO (+/-)
    # =========================================================================
    
    def _get_voice_offset(self, voice_index: int, base_offset: float) -> float:
        """
        Calcola l'offset per una voce specifica usando il pattern alternato.
        
        Pattern:
            Voice 0: 0
            Voice 1 (dispari): +offset * ceil(index/2) = +offset * 1
            Voice 2 (pari):    -offset * floor(index/2) = -offset * 1
            Voice 3 (dispari): +offset * ceil(index/2) = +offset * 2
            Voice 4 (pari):    -offset * floor(index/2) = -offset * 2
            ...
        
        Args:
            voice_index: Indice della voce (0-based)
            base_offset: Valore base dell'offset (già valutato e clippato)
            
        Returns:
            float: Offset calcolato (positivo, negativo o zero)
        """
        if voice_index == 0 or base_offset == 0:
            return 0.0
        
        # Calcola il multiplier
        if voice_index % 2 == 1:  # Dispari: positivo
            return base_offset * ((voice_index + 1) // 2)
        else:  # Pari: negativo
            return -base_offset * (voice_index // 2)
    
    # =========================================================================
    # PITCH MULTIPLIER
    # =========================================================================
    
    def get_voice_pitch_offset_semitones(self, 
                                          voice_index: int, 
                                          elapsed_time: float) -> float:
        """
        Restituisce l'offset pitch in semitoni per una voce.
        
        Args:
            voice_index: Indice della voce (0-based)
            elapsed_time: Tempo trascorso dall'onset
            
        Returns:
            float: Offset in semitoni (può essere negativo)
        """
        if self.voice_pitch_offset is None:
            return 0.0
        
        base_offset = self.voice_pitch_offset.get_value(elapsed_time)
        return self._get_voice_offset(voice_index, base_offset)
    
    def get_voice_pitch_multiplier(self, 
                                    voice_index: int, 
                                    elapsed_time: float) -> float:
        """
        Restituisce il ratio di pitch per una voce.
        
        Converte l'offset in semitoni in ratio: 2^(semitones/12)
        
        Args:
            voice_index: Indice della voce (0-based)
            elapsed_time: Tempo trascorso dall'onset
            
        Returns:
            float: Ratio pitch (1.0 = nessuna trasposizione)
        """
        semitones = self.get_voice_pitch_offset_semitones(voice_index, elapsed_time)
        return 2.0 ** (semitones / 12.0)
    
    # =========================================================================
    # POINTER OFFSET
    # =========================================================================
    
    def get_voice_pointer_offset(self, 
                                  voice_index: int, 
                                  elapsed_time: float) -> float:
        """
        Restituisce l'offset pointer in secondi per una voce.
        
        Il valore base è normalizzato (0-1), viene scalato esternamente.
        
        Args:
            voice_index: Indice della voce (0-based)
            elapsed_time: Tempo trascorso dall'onset
            
        Returns:
            float: Offset pointer normalizzato (0-1, può essere negativo)
        """
        if self.voice_pointer_offset is None:
            return 0.0
        
        base_offset = self.voice_pointer_offset.get_value(elapsed_time)
        return self._get_voice_offset(voice_index, base_offset)
    
    def get_voice_pointer_range(self, elapsed_time: float) -> float:
        """
        Restituisce il range stocastico per il pointer delle voci.
        
        Args:
            elapsed_time: Tempo trascorso dall'onset
            
        Returns:
            float: Range per variazione stocastica (normalizzato 0-1)
        """
        if self.voice_pointer_range is None:
            return 0.0
        
        return self.voice_pointer_range.get_value(elapsed_time)
    
    # =========================================================================
    # UTILITY
    # =========================================================================
    
    def is_voice_active(self, voice_index: int, elapsed_time: float) -> bool:
        """
        Verifica se una voce è attiva al tempo specificato.
        
        Args:
            voice_index: Indice della voce (0-based)
            elapsed_time: Tempo trascorso dall'onset
            
        Returns:
            bool: True se la voce è attiva
        """
        return voice_index < self.get_active_voices(elapsed_time)
    
    
    # =========================================================================
    # PROPRIETÀ PER BACKWARD COMPATIBILITY (ScoreVisualizer)
    # =========================================================================
    
    @property
    def num_voices_value(self):
        """Valore base di num_voices (per ScoreVisualizer)."""
        if self.num_voices is None:
            return 1
        return self.num_voices.value
    
    @property
    def voice_pitch_offset_value(self):
        """Valore base di voice_pitch_offset (per ScoreVisualizer)."""
        if self.voice_pitch_offset is None:
            return 0.0
        return self.voice_pitch_offset.value
    
    @property
    def voice_pointer_offset_value(self):
        """Valore base di voice_pointer_offset (per ScoreVisualizer)."""
        if self.voice_pointer_offset is None:
            return 0.0
        return self.voice_pointer_offset.value
    
    @property
    def voice_pointer_range_value(self):
        """Valore base di voice_pointer_range (per ScoreVisualizer)."""
        if self.voice_pointer_range is None:
            return 0.0
        return self.voice_pointer_range.value
    
    # =========================================================================
    # REPR
    # =========================================================================
    
    def __repr__(self) -> str:
        return (f"VoiceManager(max_voices={self._max_voices}, "
                f"pitch_offset={self.voice_pitch_offset_value}, "
                f"pointer_offset={self.voice_pointer_offset_value})")