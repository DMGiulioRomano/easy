"""
parser.py

Modulo Factory/Builder per la creazione di oggetti Parameter.
Agisce come un ponte tra i dati grezzi (YAML) e il modello a oggetti (Parameter).

Responsabilità:
1. Validazione statica: Controlla che il parametro esista nel Registry.
2. Conversione Tipi: Trasforma liste/dict in oggetti Envelope.
3. Normalizzazione Temporale: Scala i tempi degli envelope se richiesto (normalized -> absolute).
4. Iniezione delle Dipendenze: Assembla l'oggetto Parameter con i suoi Bounds.
"""

from typing import Union, Optional, List, Any
from parameter import Parameter, ParamInput
from envelope import Envelope
from parameter_definitions import get_parameter_definition

class GranularParser:
    """
    Factory contestuale per la creazione di parametri.
    Mantiene lo stato dello Stream (durata, id) per configurare correttamente
    gli Envelope e i log.
    """

    def __init__(
        self, 
        stream_id: str, 
        duration: float, 
        time_mode: str = 'absolute'
    ):
        """
        Inizializza il parser con il contesto dello Stream.

        Args:
            stream_id: ID dello stream (usato per i log del parametro).
            duration: Durata totale dello stream (usata per time_scale).
            time_mode: 'absolute' (sec) o 'normalized' (0-1). Default per gli envelope.
        """
        self.stream_id = stream_id
        self.duration = duration
        self.time_mode = time_mode

    def parse_parameter(
        self,
        name: str,
        value_raw: Any,
        range_raw: Any = None,
        prob_raw: Any = None
    ) -> Parameter:
        """
        Metodo Factory principale. Crea un oggetto Parameter pronto all'uso.

        Args:
            name: Nome del parametro (deve esistere in parameter_definitions.py).
            value_raw: Valore base dal YAML (numero, lista breakpoints, dict envelope).
            range_raw: Valore range/randomness dal YAML (opzionale).
            prob_raw: Valore probabilità/dephase dal YAML (opzionale).

        Returns:
            Un'istanza configurata di Parameter.
        """
        # 1. Recupera la definizione (Bounds & Rules) dal Registry
        # Se il nome non esiste, get_parameter_definition solleva KeyError (Fail Fast)
        bounds = get_parameter_definition(name)

        # 2. Converte i dati grezzi in formati utilizzabili (float o Envelope)
        # Qui avviene la normalizzazione temporale se necessaria
        clean_value = self._parse_input(value_raw, f"{name}.value")
        clean_range = self._parse_input(range_raw, f"{name}.range")
        clean_prob = self._parse_input(prob_raw, f"{name}.probability")

        # 3. Assembla e restituisce l'oggetto Smart Parameter
        return Parameter(
            name=name,
            value=clean_value,
            bounds=bounds,
            mod_range=clean_range,
            mod_prob=clean_prob,
            owner_id=self.stream_id
        )

    # =========================================================================
    # INTERNAL HELPER METHODS
    # =========================================================================

    def _parse_input(self, raw_data: Any, context_info: str) -> Optional[ParamInput]:
        """
        Analizza un input grezzo e restituisce float, Envelope o None.
        Gestisce la logica di scaling temporale per gli Envelope.
        """
        # Caso 0: Dato mancante
        if raw_data is None:
            return None

        # Caso 1: Numero semplice (int/float)
        if isinstance(raw_data, (int, float)):
            return float(raw_data)

        # Caso 2: Struttura complessa (Lista o Dict) -> Envelope
        if isinstance(raw_data, (list, dict)):
            return self._create_envelope(raw_data)

        # Caso Errore: Tipo non supportato
        raise ValueError(
            f"Formato non valido per '{context_info}': {raw_data}. "
            f"Atteso numero, lista di punti, o dict envelope."
        )

    def _create_envelope(self, raw_data: Union[List, dict]) -> Envelope:
        """
        Crea un oggetto Envelope gestendo la normalizzazione temporale.
        """
        points = []
        env_type = 'linear'
        local_time_mode = None

        # A) Parsing della struttura dati
        if isinstance(raw_data, dict):
            # Formato esplicito: {type: 'cubic', points: [...], time_unit: 'normalized'}
            points = raw_data.get('points', [])
            env_type = raw_data.get('type', 'linear')
            local_time_mode = raw_data.get('time_unit') # Override locale
        else:
            # Formato implicito (lista): [[0, 10], [1, 20]]
            points = raw_data
            env_type = 'linear'

        # B) Logica di Normalizzazione Temporale
        # La modalità locale vince su quella globale dello stream
        effective_mode = local_time_mode if local_time_mode else self.time_mode
        should_scale = (effective_mode == 'normalized')

        final_points = []
        if should_scale:
            # Scala l'asse X (tempo) moltiplicandolo per la durata dello stream
            # Esempio: [0.5, 10] -> [0.5 * duration, 10]
            for pt in points:
                if len(pt) != 2:
                    raise ValueError(f"Breakpoint envelope non valido: {pt}")
                final_points.append([pt[0] * self.duration, pt[1]])
        else:
            # Usa i tempi assoluti così come sono
            final_points = points

        # C) Creazione Envelope
        # Nota: Passiamo sempre una struttura dict all'init di Envelope per uniformità,
        # oppure la lista diretta se Envelope la accetta (il tuo Envelope accetta entrambi).
        if isinstance(raw_data, dict):
            # Preserva altri metadati del dict originale se necessario
            return Envelope({'type': env_type, 'points': final_points})
        else:
            return Envelope(final_points)