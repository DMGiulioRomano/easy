from generator import Generator
from score_visualizer import ScoreVisualizer
# =============================================================================
# MAIN
# =============================================================================

# =============================================================================
# COSTANTI E LIMITI DI SICUREZZA
# =============================================================================

MAX_GRAINS_PER_SECOND = 4000  # Limite assoluto di density
MIN_INTER_ONSET = 0.0001      # Minimo 0.1ms tra grani
MIN_GRAIN_DURATION = 0.001    # Minimo 1ms di durata grano
MAX_GRAIN_DURATION = 10.0     # Massimo 10s di durata grano
from logger import configure_clip_logger, get_clip_log_path
from generator import Generator

# Configura PRIMA di creare stream
configure_clip_logger(
    console_enabled=False,   # NO terminale
    file_enabled=True,       # SI file
    log_dir='./logs',
    log_transformations=False
)


def main():
    import sys
    import os
    # Verifica argomenti
    if len(sys.argv) < 2:
        print("Uso: python main.py <file.yml> [output.sco] [--visualize] [--show-static]")
        sys.exit(1)
    
    yaml_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'output.sco'
    do_visualize = '--visualize' in sys.argv or '-v' in sys.argv
    show_static = '--show-static' in sys.argv or '-s' in sys.argv
    yaml_basename = os.path.splitext(os.path.basename(yaml_file))[0]
    configure_clip_logger(
    console_enabled=False,
    file_enabled=True,
    log_dir='./logs',
    yaml_name=yaml_basename)
    try:
        # Crea il generatore
        generator = Generator(yaml_file)
        
        # Carica YAML
        print(f"Caricamento {yaml_file}...")
        generator.load_yaml()
        
        # Crea gli stream e genera i grani
        print("Generazione streams...")
        generator.create_elements()
        
        # Genera il file score
        print(f"Scrittura score...")
        generator.generate_score_file(output_file)
        
        print("\n✓ Generazione completata!")

        if do_visualize:
            print("\nGenerazione partitura grafica...")
            
            # Crea il nome del PDF dal nome dello score
            pdf_file = output_file.rsplit('.', 1)[0] + '.pdf'
            
            viz = ScoreVisualizer(generator, config={
                'page_duration': 15.0,
                'show_static_params': show_static,
            })
            viz.export_pdf(pdf_file)

        # Percorso file
        print(f"Log: {get_clip_log_path()}")


    except FileNotFoundError:
        print(f"✗ Errore: file '{yaml_file}' non trovato")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Errore: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()