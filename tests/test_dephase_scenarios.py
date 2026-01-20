"""
Test suite per i 6 scenari di interazione Range/Dephase.

Questi test validano il comportamento del sistema dephase secondo le specifiche:

DEFINIZIONI:
- "Range NON esplicitato" = il parametro *_range (es. volume_range) NON è nel YAML
                           → il codice usa il default 0.0
- "Range ESPLICITATO" = il parametro *_range È scritto nel YAML (es. volume_range: 6.0)
- "Dephase ASSENTE" = la sezione 'dephase:' NON è nel YAML
- "Dephase presente vuoto" = 'dephase: {}' È nel YAML ma senza valori

SCENARI:
1. range NON esplicitato, dephase:{} vuoto, prob non specificata → default_jitter @ 1%
2. range NON esplicitato, dephase con alcune prob → non specificate = 1%
3. range NON esplicitato, dephase ASSENTE → 0% (nessuna variazione)
4. range ESPLICITATO, dephase ASSENTE → range @ 100%
5. range ESPLICITATO, dephase:{} vuoto → range @ 1%
6. range ESPLICITATO, dephase con prob esplicita → prob specificata

NOTA: Questi test documentano il comportamento DESIDERATO.
      Alcuni falliranno finché il codice non viene aggiornato.
"""

import pytest
import random


# =============================================================================
# TEST DEPHASE - 6 SCENARI COMPLETI
# =============================================================================

class TestDephaseScenarios:
    """
    Test completi per i 6 scenari di interazione Range/Dephase.
    
    Legenda:
    - Range: parametro *_range nel YAML (es. volume_range)
    - Dephase: sezione 'dephase:' nel YAML
    - Prob: probabilità specifica (es. pc_rand_volume: 50)
    
    DEFAULT_PROB = 1% (probabilità minima quando dephase presente ma non configurato)
    """
    
    DEFAULT_PROB = 1.0  # 1% - probabilità di default desiderata
    
    # -------------------------------------------------------------------------
    # SCENARIO 1: Range NON esplicitato, Dephase presente ma vuoto
    # Atteso: default_jitter applicato con probabilità 1%
    # -------------------------------------------------------------------------
    def test_scenario_1_no_range_dephase_empty_no_prob(self, stream_factory):
        """
        SCENARIO 1: range NON nel YAML, dephase:{} vuoto, prob non specificata.
        
        YAML equivalente:
            volume: -6.0
            # volume_range: NON PRESENTE (default 0.0)
            dephase: {}
        
        Comportamento atteso:
        - Il default_jitter dovrebbe essere applicato con probabilità 1%
        - Con tanti grani, ~1% dovrebbe avere variazione
        """
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'scenario_1',
            'onset': 0.0, 
            'duration': 5.0,  # Più lungo per avere statistiche
            'sample': 'test.wav',
            'volume': -6.0,
            # volume_range NON presente → usa default 0.0
            'dephase': {}  # Presente ma VUOTO
        })
        stream.generate_grains()
        
        volumes = [g.volume for g in stream.grains]
        total_grains = len(volumes)
        
        # Con prob=1%, su ~200 grani ci aspettiamo ~2 variazioni
        # Tolleranza: max 5% variazioni (statistical noise)
        varied_count = sum(1 for v in volumes if v != -6.0)
        expected_max = total_grains * 0.05
        
        assert varied_count <= expected_max, \
            f"Troppe variazioni ({varied_count}/{total_grains}). " \
            f"Con prob=1% atteso max ~{expected_max:.0f}"
    
    # -------------------------------------------------------------------------
    # SCENARIO 2: Range NON esplicitato, Dephase presente, solo alcune prob
    # Atteso: quelle non specificate = 1%
    # -------------------------------------------------------------------------
    def test_scenario_2_no_range_dephase_partial_prob(self, stream_factory):
        """
        SCENARIO 2: range NON nel YAML, dephase con ALCUNE prob specificate.
        
        YAML equivalente:
            volume: -6.0
            # volume_range: NON PRESENTE
            pan: 45.0
            # pan_range: NON PRESENTE
            dephase:
              pc_rand_volume: 100  # Esplicito
              # pc_rand_pan: ???   # NON specificato
        
        Comportamento atteso:
        - pc_rand_volume: 100 (esplicito) → sempre attivo → usa default_jitter
        - pc_rand_pan: NON specificato → dovrebbe essere 1%
        """
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'scenario_2',
            'onset': 0.0,
            'duration': 5.0,
            'sample': 'test.wav',
            'volume': -6.0,
            # volume_range NON presente
            'pan': 45.0,
            # pan_range NON presente
            'dephase': {
                'pc_rand_volume': 100,  # Esplicito: sempre attivo
                # pc_rand_pan NON specificato → default 1%
            }
        })
        stream.generate_grains()
        
        volumes = [g.volume for g in stream.grains]
        pans = [g.pan for g in stream.grains]
        
        # Volume: con prob=100 e range=0, usa default_jitter → variazione
        volume_varied = len(set(volumes)) > 1
        assert volume_varied, "Volume dovrebbe variare con pc_rand_volume=100 (default_jitter)"
        
        # Pan: con prob=1% (default), quasi tutti dovrebbero essere 45.0
        pan_variations = sum(1 for p in pans if p != 45.0)
        total = len(pans)
        
        assert pan_variations <= total * 0.05, \
            f"Pan varia troppo ({pan_variations}/{total}). " \
            f"Con prob=1% atteso pochissime variazioni"
    
    # -------------------------------------------------------------------------
    # SCENARIO 3: Range NON esplicitato, Dephase ASSENTE
    # Atteso: nessuna variazione (tutto a 0%)
    # -------------------------------------------------------------------------
    def test_scenario_3_no_range_no_dephase(self, stream_factory):
        """
        SCENARIO 3: range NON nel YAML, dephase ASSENTE.
        
        YAML equivalente:
            volume: -6.0
            pan: 45.0
            # Niente volume_range, pan_range, dephase
        
        Comportamento atteso:
        - Nessuna variazione su nessun parametro
        - Tutto piatto ai valori base
        """
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'scenario_3',
            'onset': 0.0,
            'duration': 2.0,
            'sample': 'test.wav',
            'volume': -6.0,
            # volume_range NON presente
            'pan': 45.0
            # pan_range NON presente
            # dephase NON presente
        })
        stream.generate_grains()
        
        volumes = set(g.volume for g in stream.grains)
        pans = set(g.pan for g in stream.grains)
        
        # TUTTO deve essere piatto
        assert len(volumes) == 1 and list(volumes)[0] == -6.0, \
            f"Volume deve essere fisso a -6.0 senza dephase. Trovati: {volumes}"
        assert len(pans) == 1 and list(pans)[0] == 45.0, \
            f"Pan deve essere fisso a 45.0 senza dephase. Trovati: {pans}"
    
    # -------------------------------------------------------------------------
    # SCENARIO 4: Range ESPLICITATO > 0, Dephase ASSENTE
    # Atteso: range attivo al 100%
    # -------------------------------------------------------------------------
    def test_scenario_4_range_no_dephase(self, stream_factory):
        """
        SCENARIO 4: range ESPLICITATO nel YAML, dephase ASSENTE.
        
        YAML equivalente:
            volume: -6.0
            volume_range: 6.0  # ESPLICITATO
            # dephase: NON PRESENTE
        
        Comportamento atteso:
        - Range SEMPRE attivo (probabilità 100%)
        - Variazione visibile su tutti i grani
        """
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'scenario_4',
            'onset': 0.0,
            'duration': 2.0,
            'sample': 'test.wav',
            'volume': -6.0,
            'volume_range': 6.0,  # ESPLICITATO nel YAML
            # dephase NON presente
        })
        stream.generate_grains()
        
        volumes = [g.volume for g in stream.grains]
        
        # Range sempre attivo → variazione significativa
        assert max(volumes) != min(volumes), \
            "Senza dephase, il range deve essere sempre attivo"
        
        # Verifica bounds: -6 ± 3 → [-9, -3]
        assert min(volumes) >= -9.0, f"Volume min {min(volumes)} sotto bounds"
        assert max(volumes) <= -3.0, f"Volume max {max(volumes)} sopra bounds"
    
    # -------------------------------------------------------------------------
    # SCENARIO 5: Range ESPLICITATO > 0, Dephase presente ma vuoto
    # Atteso: range attivo al 1%
    # -------------------------------------------------------------------------
    def test_scenario_5_range_dephase_empty(self, stream_factory):
        """
        SCENARIO 5: range ESPLICITATO nel YAML, dephase:{} vuoto.
        
        YAML equivalente:
            volume: -6.0
            volume_range: 12.0  # ESPLICITATO
            dephase: {}         # PRESENTE ma vuoto
        
        Comportamento atteso:
        - Range applicato solo con probabilità 1%
        - Quasi tutti i valori dovrebbero essere il base
        """
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'scenario_5',
            'onset': 0.0,
            'duration': 5.0,
            'sample': 'test.wav',
            'volume': -6.0,
            'volume_range': 12.0,  # ESPLICITATO nel YAML
            'dephase': {}  # Presente ma VUOTO
        })
        stream.generate_grains()
        
        volumes = [g.volume for g in stream.grains]
        total = len(volumes)
        
        # Con prob=1%, ~99% dovrebbero essere esattamente -6.0
        base_count = sum(1 for v in volumes if v == -6.0)
        
        assert base_count >= total * 0.90, \
            f"Solo {base_count}/{total} ({base_count/total*100:.1f}%) al valore base. " \
            f"Con prob=1% atteso >90% invariati"
    
    # -------------------------------------------------------------------------
    # SCENARIO 6: Range ESPLICITATO > 0, Dephase con prob esplicita
    # Atteso: range attivo con la probabilità specificata
    # -------------------------------------------------------------------------
    def test_scenario_6a_range_dephase_prob_zero(self, stream_factory):
        """
        SCENARIO 6a: range ESPLICITATO, dephase con prob=0.
        
        YAML equivalente:
            volume: -6.0
            volume_range: 100.0
            dephase:
              pc_rand_volume: 0
        
        Comportamento atteso: nessuna variazione
        """
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'scenario_6a',
            'onset': 0.0,
            'duration': 2.0,
            'sample': 'test.wav',
            'volume': -6.0,
            'volume_range': 100.0,  # ESPLICITATO
            'dephase': {'pc_rand_volume': 0}  # Prob=0
        })
        stream.generate_grains()
        
        volumes = set(g.volume for g in stream.grains)
        assert len(volumes) == 1 and list(volumes)[0] == -6.0, \
            f"Con prob=0, nessuna variazione attesa. Trovati: {volumes}"
    
    def test_scenario_6b_range_dephase_prob_100(self, stream_factory):
        """
        SCENARIO 6b: range ESPLICITATO, dephase con prob=100.
        
        YAML equivalente:
            volume: -6.0
            volume_range: 6.0
            dephase:
              pc_rand_volume: 100
        
        Comportamento atteso: sempre variazione
        """
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'scenario_6b',
            'onset': 0.0,
            'duration': 2.0,
            'sample': 'test.wav',
            'volume': -6.0,
            'volume_range': 6.0,  # ESPLICITATO
            'dephase': {'pc_rand_volume': 100}  # Prob=100
        })
        stream.generate_grains()
        
        volumes = [g.volume for g in stream.grains]
        assert max(volumes) != min(volumes), \
            "Con prob=100, variazione attesa"
    
    def test_scenario_6c_range_dephase_prob_50(self, stream_factory):
        """
        SCENARIO 6c: range ESPLICITATO, dephase con prob=50.
        
        YAML equivalente:
            volume: -6.0
            volume_range: 6.0
            dephase:
              pc_rand_volume: 50
        
        Comportamento atteso: circa metà variati
        """
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'scenario_6c',
            'onset': 0.0,
            'duration': 5.0,
            'sample': 'test.wav',
            'volume': -6.0,
            'volume_range': 6.0,  # ESPLICITATO
            'dephase': {'pc_rand_volume': 50}  # Prob=50
        })
        stream.generate_grains()
        
        volumes = [g.volume for g in stream.grains]
        total = len(volumes)
        base_count = sum(1 for v in volumes if v == -6.0)
        
        # Con prob=50%, circa metà dovrebbero essere base
        # Tolleranza: 30%-70%
        ratio = base_count / total
        assert 0.30 <= ratio <= 0.70, \
            f"Con prob=50%, atteso ~50% invariati, trovato {ratio*100:.1f}%"


# =============================================================================
# TEST EDGE CASES DEPHASE
# =============================================================================

class TestDephaseEdgeCases:
    """Test casi limite per dephase."""
    
    def test_dephase_with_envelope_probability(self, stream_factory):
        """
        Probabilità dephase come envelope temporale.
        
        YAML equivalente:
            dephase:
              pc_rand_volume:
                points: [[0, 0], [5, 50], [10, 100]]
        
        La probabilità aumenta nel tempo: 0% → 50% → 100%
        """
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'dephase_env',
            'onset': 0.0,
            'duration': 10.0,
            'sample': 'test.wav',
            'volume': -6.0,
            'volume_range': 6.0,
            'dephase': {
                'pc_rand_volume': [[0, 0], [5, 50], [10, 100]]
            }
        })
        stream.generate_grains()
        
        # Dividi grani per fasce temporali (usa onset relativo)
        early = [g.volume for g in stream.grains if g.onset < 2.0]
        late = [g.volume for g in stream.grains if g.onset > 8.0]
        
        if early:
            # Early: prob~0, quasi tutto invariato
            early_base = sum(1 for v in early if v == -6.0) / len(early)
            assert early_base > 0.8, \
                f"All'inizio (prob~0) atteso >80% invariati, trovato {early_base*100:.1f}%"
        
        if late:
            # Late: prob~100, alta variazione
            late_varied = len(set(late)) > 1
            assert late_varied, "Alla fine (prob~100) attesa variazione"
    
    def test_dephase_reverse_boolean_flip(self, stream_factory):
        """
        Reverse usa logica booleana flip, non range additivo.
        
        Con speed positivo (reverse=False normalmente) e pc_rand_reverse=100,
        TUTTI i grani dovrebbero avere reverse=True (flip).
        """
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'reverse_flip',
            'onset': 0.0,
            'duration': 1.0,
            'sample': 'test.wav',
            'grain': {'duration': 0.05, 'reverse': 'auto'},
            'pointer': {'speed': 1.0},  # Positivo → reverse=False normalmente
            'dephase': {'pc_rand_reverse': 100}  # Sempre flip
        })
        stream.generate_grains()
        
        # Con speed positivo e flip al 100%, tutti reverse=True
        for grain in stream.grains:
            assert grain.grain_reverse is True, \
                "Con pc_rand_reverse=100 e speed>0, atteso reverse=True"
    
    def test_multiple_dephase_params_independent(self, stream_factory):
        """
        Ogni parametro dephase è indipendente dagli altri.
        
        pc_rand_volume=100 e pc_rand_pan=0 devono funzionare indipendentemente.
        """
        random.seed(42)
        stream = stream_factory({
            'stream_id': 'multi_dephase',
            'onset': 0.0,
            'duration': 3.0,
            'sample': 'test.wav',
            'volume': -6.0,
            'volume_range': 6.0,
            'pan': 0.0,
            'pan_range': 90.0,
            'dephase': {
                'pc_rand_volume': 100,  # Sempre attivo
                'pc_rand_pan': 0  # Mai attivo
            }
        })
        stream.generate_grains()
        
        volumes = [g.volume for g in stream.grains]
        pans = [g.pan for g in stream.grains]
        
        # Volume: sempre variato
        assert max(volumes) != min(volumes), \
            "Volume con prob=100 deve variare"
        
        # Pan: mai variato
        pans_set = set(pans)
        assert len(pans_set) == 1 and list(pans_set)[0] == 0.0, \
            f"Pan con prob=0 deve essere fisso a 0.0. Trovati: {pans_set}"
    
    def test_dephase_duration_affects_grain_timing(self, stream_factory):
        """
        Il dephase sulla duration influenza anche il timing dei grani successivi
        (attraverso il calcolo dell'inter-onset con fill_factor).
        """
        random.seed(42)
        
        # Stream senza dephase duration
        stream_fixed = stream_factory({
            'stream_id': 'dur_fixed',
            'onset': 0.0,
            'duration': 2.0,
            'sample': 'test.wav',
            'grain': {'duration': 0.05, 'duration_range': 0.0},
            'fill_factor': 2.0
        })
        stream_fixed.generate_grains()
        
        # Stream con dephase duration al 100%
        random.seed(42)
        stream_dephase = stream_factory({
            'stream_id': 'dur_dephase',
            'onset': 0.0,
            'duration': 2.0,
            'sample': 'test.wav',
            'grain': {'duration': 0.05, 'duration_range': 0.02},
            'fill_factor': 2.0,
            'dephase': {'pc_rand_duration': 100}
        })
        stream_dephase.generate_grains()
        
        # Le durate dovrebbero essere diverse
        durs_fixed = [g.duration for g in stream_fixed.grains]
        durs_dephase = [g.duration for g in stream_dephase.grains]
        
        assert len(set(durs_fixed)) == 1, "Senza dephase, durate uguali"
        assert len(set(durs_dephase)) > 1, "Con dephase, durate variate"


# =============================================================================
# TEST DIAGNOSTICI (per debug)
# =============================================================================

class TestDephaseDiagnostics:
    """
    Test diagnostici per verificare lo stato attuale dell'implementazione.
    Questi test stampano informazioni utili per il debug.
    """
    
    def test_print_current_behavior_summary(self, stream_factory, capsys):
        """
        Stampa un riepilogo del comportamento attuale per ogni scenario.
        Utile per verificare lo stato prima/dopo le modifiche.
        """
        scenarios = [
            # (nome, params, descrizione)
            ("S1: range NON presente, dephase={}", {
                'volume': -6.0,
                # volume_range NON presente
                'dephase': {}
            }, "Atteso: ~1% variazione (default_jitter)"),
            
            ("S3: range NON presente, no dephase", {
                'volume': -6.0
                # volume_range NON presente
                # dephase NON presente
            }, "Atteso: 0% variazione"),
            
            ("S4: range ESPLICITATO, no dephase", {
                'volume': -6.0,
                'volume_range': 6.0  # ESPLICITATO
                # dephase NON presente
            }, "Atteso: 100% variazione"),
            
            ("S5: range ESPLICITATO, dephase={}", {
                'volume': -6.0,
                'volume_range': 6.0,  # ESPLICITATO
                'dephase': {}
            }, "Atteso: ~1% variazione"),
        ]
        
        print("\n" + "="*60)
        print("DIAGNOSTICA COMPORTAMENTO DEPHASE ATTUALE")
        print("="*60)
        
        for name, params, expected in scenarios:
            random.seed(42)
            full_params = {
                'stream_id': 'diag',
                'onset': 0.0,
                'duration': 3.0,
                'sample': 'test.wav',
                **params
            }
            stream = stream_factory(full_params)
            stream.generate_grains()
            
            volumes = [g.volume for g in stream.grains]
            total = len(volumes)
            base_count = sum(1 for v in volumes if v == -6.0)
            varied_pct = (total - base_count) / total * 100 if total > 0 else 0
            
            print(f"\n{name}")
            print(f"  Grani totali: {total}")
            print(f"  Variati: {total - base_count} ({varied_pct:.1f}%)")
            print(f"  {expected}")
        
        print("\n" + "="*60)
        
        # Questo test passa sempre, serve solo per output diagnostico
        assert True