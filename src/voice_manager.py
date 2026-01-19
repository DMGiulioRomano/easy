"""
VoiceManager - Gestione voci multiple nella sintesi granulare.

Responsabilità:
- Gestione dinamica del numero di voci attive (num_voices)
- Calcolo moltiplicatori pitch per ogni voce (pattern alternato +/-)
- Calcolo offset pointer per ogni voce (pattern alternato +/-)

Pattern Alternato:
    Voice 0: offset = 0
    Voice 1: offset = +param * 1
    Voice 2: offset = -param * 1  
    Voice 3: offset = +param * 2
    Voice 4: offset = -param * 2
    ...

Ispirato al sistema DMX-1000 di Barry Truax.
"""

from typing import Union
from envelope import Envelope


class VoiceManager:
    """
    Gestisce le voci multiple di uno stream granulare.
    
    Attributes:
        _evaluator: ParameterEvaluator per valutare envelope
        _sample_dur_sec: Durata del sample (per scaling pointer offset)
        num_voices: Numero di voci (int o Envelope)
        voice_pitch_offset: Offset pitch in semitoni (float o Envelope)
        voice_pointer_offset: Offset pointer in secondi (float o Envelope)
        voice_pointer_range: Range stocastico pointer (float o Envelope)
    """
    
    def __init__(self, 
                 evaluator, 
                 voices_params: dict, 
                 sample_dur_sec: float):
        """
        Inizializza il VoiceManager.
        
        Args:
            evaluator: ParameterEvaluator per parsing e valutazione
            voices_params: Dict con parametri voci dal YAML
            sample_dur_sec: Durata del sample in secondi (per scaling)
        """
        self._evaluator = evaluator
        self._sample_dur_sec = sample_dur_sec
        
        # Parse parametri
        self.num_voices = self._evaluator.parse(
            voices_params.get('number', 1), 
            'num_voices'
        )
        self.voice_pitch_offset = self._evaluator.parse(
            voices_params.get('offset_pitch', 0.0), 
            'voice_pitch_offset'
        )
        self.voice_pointer_offset = self._evaluator.parse(
            voices_params.get('pointer_offset', 0.0), 
            'voice_pointer_offset'
        )
        self.voice_pointer_range = self._evaluator.parse(
            voices_params.get('pointer_range', 0.0), 
            'voice_pointer_range'
        )
        
        # Cache max voices (calcolato una volta)
        self._max_voices = self._calculate_max_voices()
    
    # =========================================================================
    # CALCOLO MAX VOICES (USANDO PARAMETEREVALUATOR)
    # =========================================================================
    
    def _calculate_max_voices(self) -> int:
        """
        Calcola il massimo numero di voci dall'envelope USANDO PARAMETEREVALUATOR.
        
        Se num_voices è un Envelope, prende il max dei breakpoints e lo clippa
        ai bounds definiti in ParameterEvaluator.BOUNDS['num_voices'].
        """
        # Ottieni i bounds dal ParameterEvaluator
        bounds = self._evaluator.get_bounds('num_voices')
        if bounds is None:
            raise ValueError(
                "Bounds per 'num_voices' non definiti in ParameterEvaluator. "
                "Aggiungi una entry in ParameterEvaluator.BOUNDS."
            )
        
        # Calcola il massimo teorico dell'envelope/valore
        if isinstance(self.num_voices, Envelope):
            # Per envelope: massimo di tutti i breakpoints
            raw_max = max(point[1] for point in self.num_voices.breakpoints)
        else:
            # Per numero fisso
            raw_max = self.num_voices
        
        # Clippa ai bounds del ParameterEvaluator (non hardcoded!)
        clipped_max = max(bounds.min_val, min(bounds.max_val, raw_max))
        
        # Arrotonda all'intero più vicino (le voci sono intere)
        return int(round(clipped_max))
    
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
        
        Usa ParameterEvaluator.evaluate() che già clippa ai bounds.
        
        Args:
            elapsed_time: Tempo trascorso dall'onset dello stream
            
        Returns:
            int: Numero di voci attive (1 <= n <= max_voices)
        """
        raw_value = self._evaluator.evaluate(
            self.num_voices, 
            elapsed_time, 
            'num_voices'
        )
        
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
        
        USA ParameterEvaluator.evaluate() per valutare e clippare base_offset.
        
        Args:
            voice_index: Indice della voce (0-based)
            elapsed_time: Tempo trascorso dall'onset
            
        Returns:
            float: Offset in semitoni (può essere negativo)
        """
        base_offset = self._evaluator.evaluate(
            self.voice_pitch_offset,
            elapsed_time,
            'voice_pitch_offset'
        )
        return self._get_voice_offset(voice_index, base_offset)
    
    def get_voice_pitch_multiplier(self, 
                                    voice_index: int, 
                                    elapsed_time: float) -> float:
        """
        Restituisce il ratio di pitch per una voce.
        
        Converte l'offset in semitoni in ratio: 2^(semitoni/12)
        
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
        
        Il valore base è già in secondi (o scalato da sample duration
        se necessario nel contesto esterno).
        
        USA ParameterEvaluator.evaluate_scaled() se necessario.
        
        Args:
            voice_index: Indice della voce (0-based)
            elapsed_time: Tempo trascorso dall'onset
            
        Returns:
            float: Offset pointer in secondi (può essere negativo)
        """
        # NOTA: voice_pointer_offset è normalizzato (0-1), viene scalato esternamente
        base_offset = self._evaluator.evaluate(
            self.voice_pointer_offset,
            elapsed_time,
            'voice_pointer_offset'
        )
        return self._get_voice_offset(voice_index, base_offset)
    
    def get_voice_pointer_range(self, elapsed_time: float) -> float:
        """
        Restituisce il range stocastico per il pointer delle voci.
        
        Args:
            elapsed_time: Tempo trascorso dall'onset
            
        Returns:
            float: Range per variazione stocastica (già scalato se necessario)
        """
        return self._evaluator.evaluate(
            self.voice_pointer_range,
            elapsed_time,
            'voice_pointer_range'
        )
    
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
    
    @property
    def sample_dur_sec(self) -> float:
        """Durata del sample in secondi."""
        return self._sample_dur_sec
    
    # =========================================================================
    # REPR
    # =========================================================================
    
    def __repr__(self) -> str:
        return (f"VoiceManager(max_voices={self._max_voices}, "
                f"pitch_offset={self.voice_pitch_offset}, "
                f"pointer_offset={self.voice_pointer_offset})")