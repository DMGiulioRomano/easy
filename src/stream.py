# src/stream.py
"""
Stream - Orchestratore per la sintesi granulare.

Fase 6 del refactoring: questa classe coordina i controller specializzati:
- ParameterEvaluator: parsing e validazione parametri
- PointerController: posizionamento testina con loop e jitter
- PitchController: trasposizione (semitoni o ratio)
- DensityController: densità e distribuzione temporale
- VoiceManager: voci multiple con offset pitch/pointer

Mantiene backward compatibility con Generator e ScoreVisualizer.
Ispirato al DMX-1000 di Barry Truax (1988).
"""
import random
from typing import List, Optional, Union

from parameter_factory import ParameterFactory
from grain import Grain
from envelope import Envelope
from parameter_evaluator import ParameterEvaluator
from pointer_controller import PointerController
from pitch_controller import PitchController
from density_controller import DensityController
from voice_manager import VoiceManager
from utils import *
from parameter_schema import STREAM_PARAMETER_SCHEMA



class Stream:
    """
    Orchestratore per uno stream di sintesi granulare.
    
    Coordina i controller specializzati e genera la lista di grani.
    Mantiene compatibilità con Generator e ScoreVisualizer.
    
    Attributes:
        stream_id: identificatore univoco
        onset: tempo di inizio (secondi)
        duration: durata dello stream (secondi)
        voices: List[List[Grain]] - grani organizzati per voce
        grains: List[Grain] - lista flattened (backward compatibility)
    """
    
    def __init__(self, params: dict):
        """
        Inizializza lo stream dai parametri YAML.
        
        Args:
            params: dizionario parametri dallo YAML
        """
        # === 1. IDENTITÀ & TIMING ===
        self.stream_id = params['stream_id']
        self.onset = params['onset']
        self.duration = params['duration']
        self.time_mode = params.get('time_mode', 'absolute')
        self.time_scale = params.get('time_scale', 1.0)
        
        # === 2. AUDIO ===
        self.sample_path = params['sample']
        self.sample_dur_sec = get_sample_duration(self.sample_path)
        
        # === 3. PARAMETER EVALUATOR (primo!) ===
        self._evaluator = ParameterEvaluator(
            stream_id=self.stream_id,
            duration=self.duration,
            time_mode=self.time_mode
        )
        # === 4. PARAMETRI DIRETTI (Data-Driven) ===
        self._init_stream_parameters(params)
        # === 5. PARAMETRI SPECIALI (logica custom) ===
        self._init_grain_reverse(params)
        # === 6. CONTROLLER ===
        self._init_controllers(params)
        # === 7. RIFERIMENTI CSOUND (assegnati da Generator) ===
        self.sample_table_num: Optional[int] = None
        self.envelope_table_num: Optional[int] = None
        # === 8. STATO ===
        self.voices: List[List[Grain]] = []
        self.grains: List[Grain] = []  # backward compatibility
        self.generated = False

    # =========================================================================
    # PARAMETRI DIRETTI (non delegati ai controller)
    # =========================================================================

    def _init_stream_parameters(self, params: dict) -> None:
        """
        Inizializza parametri diretti di Stream usando ParameterFactory.
        
        Design Pattern: Data-Driven Configuration
        - Lo schema STREAM_PARAMETER_SCHEMA definisce COSA caricare
        - ParameterFactory sa COME crearlo
        - Stream riceve i Parameter già pronti        
        """
        factory = ParameterFactory(
            stream_id=self.stream_id,
            duration=self.duration,
            time_mode=self.time_mode
        )
        
        # Crea tutti i parametri definiti nello schema
        parameters = factory.create_all_parameters(params, schema=STREAM_PARAMETER_SCHEMA)
        
        # Assegna dinamicamente come attributi
        for name, param in parameters.items():
            setattr(self, name, param)

    # =========================================================================
    # INIZIALIZZAZIONE CONTROLLER
    # =========================================================================
    
    def _init_controllers(self, params: dict) -> None:
        """Inizializza tutti i controller con i loro parametri."""
        
        # POINTER CONTROLLER
        pointer_params = params.get('pointer', {})
        self._pointer = PointerController(
            params=pointer_params,
            stream_id=self.stream_id,
            sample_dur_sec=self.sample_dur_sec,
            time_mode=self.time_mode
        )
        
        # PITCH CONTROLLER
        pitch_params = params.get('pitch', {})
        self._pitch = PitchController(
            params=pitch_params,
            evaluator=self._evaluator
        )
        
        # DENSITY CONTROLLER
        self._density = DensityController(
            evaluator=self._evaluator,
            params=params
        )
        
        # VOICE MANAGER
        voices_params = params.get('voices', {})
        self._voice_manager = VoiceManager(
            evaluator=self._evaluator,
            voices_params=voices_params,
            sample_dur_sec=self.sample_dur_sec
        )
    
            
    def _init_grain_reverse(self, params: dict) -> None:
        """
        Inizializza parametri reverse del grano.
        
        Semantica YAML RISTRETTA:
        - Chiave ASSENTE → 'auto' (segue pointer_speed)
        - Chiave PRESENTE (reverse:) → DEVE essere vuota, significa True (forzato reverse)
        - reverse: true/false/auto → ERRORE! Non accettati
        
        Examples YAML validi:
            grain:
            # reverse assente → auto mode
            
            grain:
            reverse:  # ← Unico modo per forzare reverse
        
        Examples YAML INVALIDI:
            grain:
            reverse: true    # ❌ ERRORE
            reverse: false   # ❌ ERRORE
            reverse: 'auto'  # ❌ ERRORE
        """
        grain_params = params.get('grain', {})
        
        if 'reverse' in grain_params:
            # Validazione: se la chiave è presente, DEVE essere None (vuota)
            with grain_params['reverse'] as value:
                if value is not None:
                    raise ValueError(
                        f"Stream '{self.stream_id}': grain.reverse deve essere lasciato vuoto.\n"
                        f"  Trovato: reverse: {value}\n"
                        f"  Sintassi corretta:\n"
                        f"    grain:\n"
                        f"      reverse:  # ← senza valore\n"
                        f"  Per seguire pointer_speed, ometti completamente la chiave 'reverse'."
                    )
            
            # Chiave presente e vuota → reverse forzato
            self.grain_reverse_mode = True
        else:
            # Chiave assente → auto mode (segue speed)
            self.grain_reverse_mode = 'auto'

    # =========================================================================
    # GENERAZIONE GRANI
    # =========================================================================
    
    def generate_grains(self) -> List[List[Grain]]:
        """
        Genera grani per tutte le voices.
        
        Algoritmo:
        1. Determina max_voices dall'envelope/valore fisso
        2. Per ogni voice (0 a max_voices-1):
           - Mantiene il proprio current_onset
           - Verifica se è attiva (voice_index < active_voices)
           - Se attiva: genera grano con parametri calcolati
           - Sempre: avanza current_onset per mantenere la "fase"
        
        Returns:
            List[List[Grain]]: grani organizzati per voce
        """
        # Reset stato
        self.voices = []
        self.grains = []
        
        # 1. Determina max voices
        max_voices = self._voice_manager.max_voices
        
        # 2. Loop per ogni voice
        for voice_index in range(max_voices):
            voice_grains: List[Grain] = []
            current_onset = 0.0
            
            # Loop temporale per questa voice
            while current_onset < self.duration:
                elapsed_time = current_onset

                grain_dur = self.grain_duration.get_value(elapsed_time)
                
                # 4. Verifica se voice è attiva
                if self._voice_manager.is_voice_active(voice_index, elapsed_time):
                    grain = self._create_grain(voice_index, elapsed_time, grain_dur)
                    voice_grains.append(grain)
                
                # 5. Calcola inter-onset (sempre, per mantenere fase)
                inter_onset = self._density.calculate_inter_onset(
                    elapsed_time,
                    grain_dur
                )
                current_onset += inter_onset
            
            self.voices.append(voice_grains)
        
        # 6. Flatten per backward compatibility
        self.grains = [grain for voice in self.voices for grain in voice]
        self.generated = True
        
        return self.voices
    
    def _create_grain(self, 
                      voice_index: int, 
                      elapsed_time: float, 
                      grain_dur: float) -> Grain:
        """
        Crea un singolo grano con tutti i parametri calcolati.
        
        Args:
            voice_index: indice della voce (0-based)
            elapsed_time: tempo trascorso dall'inizio dello stream
            grain_dur: durata del grano (già calcolata in generate_grains con eventuale dephase)
        
        Returns:
            Grain: oggetto grano completo
        """
        # === 1. PITCH ===
        # Base + Voice Offset
        base_pitch = self._pitch.calculate(elapsed_time)
        voice_pitch_mult = self._voice_manager.get_voice_pitch_multiplier(
            voice_index, elapsed_time
        )
        pitch_ratio = base_pitch * voice_pitch_mult
        
        # === 2. POINTER ===
        # Base + Voice Offset + Jitter Voce
        base_pointer = self._pointer.calculate(elapsed_time)
        
        voice_pointer_offset = self._voice_manager.get_voice_pointer_offset(
            voice_index, elapsed_time
        ) * self.sample_dur_sec  # Scala offset normalizzato in secondi
        
        # Variazione stocastica specifica per le voci
        voice_ptr_range = self._voice_manager.get_voice_pointer_range(elapsed_time)
        voice_ptr_deviation = random.uniform(-0.5, 0.5) * voice_ptr_range * self.sample_dur_sec
        
        pointer_pos = base_pointer + voice_pointer_offset + voice_ptr_deviation
        
        volume = self.volume.get_value(elapsed_time)
        
        # === 4. PAN (REFACTOR) ===
        # Parameter gestisce base, range e dephase interna
        pan = self.pan.get_value(elapsed_time)
        
        # === 5. REVERSE (con Dephase booleano) ===
        # Gestito separatamente perché non è un range additivo ma un flip booleano
        grain_reverse = self._calculate_grain_reverse(elapsed_time)
        
        # === 6. ONSET ===
        absolute_onset = self.onset + elapsed_time
        
        return Grain(
            onset=absolute_onset,
            duration=grain_dur,
            pointer_pos=pointer_pos,
            pitch_ratio=pitch_ratio,
            volume=volume,
            pan=pan,
            sample_table=self.sample_table_num,
            envelope_table=self.envelope_table_num,
            grain_reverse=grain_reverse
        )


    def _calculate_grain_reverse(self, elapsed_time: float) -> bool:
        """
        Calcola se il grano deve essere riprodotto al contrario.
        
        Usa evaluate_gated_stochastic con variation_mode='invert':
        - 'auto': base_reverse segue pointer_speed
        - grain_reverse_randomness: probabilità di flip (0-100)
        - grain_reverse_randomness=None: nessun flip (mantiene base)
        
        Args:
            elapsed_time: tempo trascorso dall'inizio dello stream
            
        Returns:
            bool: True se grano deve essere riprodotto al contrario
        """
        # 1. Determina base value come float (0.0 o 1.0)
        if self.grain_reverse_mode == 'auto':
            # Se la testina va indietro, il grano è reverse di base
            is_reverse_base = (self._pointer.get_speed(elapsed_time) < 0)
        else:
            # Se forzato da YAML, usiamo il valore caricato nel parametro
            # Nota: self.reverse._value può essere un numero o un Envelope
            val = self.reverse._value
            if hasattr(val, 'evaluate'):
                val = val.evaluate(elapsed_time)
            is_reverse_base = (val > 0.5)
        
        # FASE 2: Controlliamo se dobbiamo FLIPPARE (Dephase/Probabilità)
        # Usiamo il metodo interno del parametro per vedere se il "dado" vince
        # Nota: Qui stiamo "rubando" la logica probabilistica all'oggetto Parameter
        should_flip = self.reverse._check_probability(elapsed_time)
        
        # FASE 3: Applichiamo il flip
        # Se should_flip è True, invertiamo la decisione di base
        if should_flip:
            return not is_reverse_base
            
        return is_reverse_base

    # =========================================================================
    # PROPRIETÀ PER BACKWARD COMPATIBILITY
    # =========================================================================
    
    @property
    def sampleDurSec(self) -> float:
        """Alias per backward compatibility."""
        return self.sample_dur_sec
    
    @property
    def num_voices(self) -> Union[int, Envelope]:
        """Espone num_voices per ScoreVisualizer."""
        return self._voice_manager.num_voices
    
    @property
    def density(self) -> Optional[Union[float, Envelope]]:
        """Espone density per Generator/ScoreVisualizer."""
        return self._density.density
    
    @property
    def fill_factor(self) -> Optional[Union[float, Envelope]]:
        """Espone fill_factor per Generator/ScoreVisualizer."""
        return self._density.fill_factor
    
    @property
    def distribution(self) -> Union[float, Envelope]:
        """Espone distribution per ScoreVisualizer."""
        return self._density.distribution
    
    @property
    def pointer_speed(self) -> Union[float, Envelope]:
        """Espone pointer_speed per ScoreVisualizer."""
        return self._pointer.speed
    
    @property
    def pitch_ratio(self) -> Optional[Union[float, Envelope]]:
        """Espone pitch_ratio per ScoreVisualizer (solo se in modalità ratio)."""
        return self._pitch.base_ratio
    
    @property
    def pitch_semitones_envelope(self) -> Optional[Union[float, Envelope]]:
        """Espone pitch_semitones per ScoreVisualizer (solo se in modalità semitoni)."""
        return self._pitch.base_semitones
    
    @property
    def pitch_range(self) -> Union[float, Envelope]:
        """Espone pitch_range per ScoreVisualizer."""
        return self._pitch.range
    
    @property
    def voice_pitch_offset(self) -> Union[float, Envelope]:
        """Espone voice_pitch_offset per ScoreVisualizer."""
        return self._voice_manager.voice_pitch_offset
    
    @property
    def voice_pointer_offset(self) -> Union[float, Envelope]:
        """Espone voice_pointer_offset per ScoreVisualizer."""
        return self._voice_manager.voice_pointer_offset
    
    @property
    def voice_pointer_range(self) -> Union[float, Envelope]:
        """Espone voice_pointer_range per ScoreVisualizer."""
        return self._voice_manager.voice_pointer_range
    
    # =========================================================================
    # REPR
    # =========================================================================
    
    def __repr__(self) -> str:
        mode = "fill_factor" if self.fill_factor is not None else "density"
        return (f"Stream(id={self.stream_id}, onset={self.onset}, "
                f"dur={self.duration}, mode={mode}, grains={len(self.grains)})")
