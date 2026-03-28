# =============================================================================
# MAIN
# =============================================================================

# =============================================================================
# COSTANTI E LIMITI DI SICUREZZA
# =============================================================================

from shared.logger import configure_clip_logger, get_clip_log_path
from engine.generator import Generator
from rendering.score_visualizer import ScoreVisualizer


def main():
    import sys
    import os

    if len(sys.argv) < 2:
        # MODIFICA 1: aggiunto [--renderer csound|numpy] alla stringa di uso
        print("Uso: python main.py <file.yml> [output.sco] [--visualize] [--show-static] [--per-stream] [--renderer csound|numpy]")
        sys.exit(1)

    yaml_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'output.sco'
    do_visualize = '--visualize' in sys.argv or '-v' in sys.argv
    show_static = '--show-static' in sys.argv or '-s' in sys.argv
    per_stream = '--per-stream' in sys.argv or '-p' in sys.argv
    use_cache = '--cache' in sys.argv

    # MODIFICA 2: parsing del flag --renderer (default: 'csound')
    renderer_type = 'csound'
    if '--renderer' in sys.argv:
        idx = sys.argv.index('--renderer')
        if idx + 1 < len(sys.argv):
            renderer_type = sys.argv[idx + 1]

    # --cache-dir DIR (default: cache/)
    cache_dir = 'cache'
    if '--cache-dir' in sys.argv:
        idx = sys.argv.index('--cache-dir')
        if idx + 1 < len(sys.argv):
            cache_dir = sys.argv[idx + 1]

    # --aif-dir DIR (default: None, il check sul file viene ignorato)
    aif_dir = None
    if '--aif-dir' in sys.argv:
        idx = sys.argv.index('--aif-dir')
        if idx + 1 < len(sys.argv):
            aif_dir = sys.argv[idx + 1]

    yaml_basename = os.path.splitext(os.path.basename(yaml_file))[0]
    configure_clip_logger(
        console_enabled=False,
        file_enabled=True,
        log_dir='./logs',
        yaml_name=yaml_basename,
        log_transformations=False
    )

    try:
        generator = Generator(yaml_file)

        print(f"Caricamento {yaml_file}...")
        generator.load_yaml()

        print("Generazione streams...")
        generator.create_elements()

        # MODIFICA 3: branch su renderer_type.
        # Il ramo numpy e' nuovo. Il ramo csound (else) e' identico all'originale,
        # semplicemente avvolto in else: con un livello di indentazione in piu'.
        if renderer_type == 'numpy':
            from rendering.renderer_factory import RendererFactory
            from rendering.sample_registry import SampleRegistry
            from rendering.numpy_window_registry import NumpyWindowRegistry

            table_map = generator.ftable_manager.get_all_tables()

            sample_reg = SampleRegistry()
            window_reg = NumpyWindowRegistry()

            for num, (ftype, name) in table_map.items():
                if ftype == 'sample':
                    sample_reg.load(name)

            renderer = RendererFactory.create(
                'numpy',
                sample_registry=sample_reg,
                window_registry=window_reg,
                table_map=table_map,
                output_sr=48000,
            )

            aif_base = os.path.splitext(output_file)[0]
            for stream in generator.streams:
                aif_path = f"{aif_base}_{stream.stream_id}.aif"
                renderer.render_stream(stream, aif_path)

        else:
            # ramo csound: comportamento identico all'originale
            if per_stream:
                output_dir = os.path.dirname(output_file) or '.'
                base_name = os.path.splitext(os.path.basename(output_file))[0]

                cache_manager = None
                if use_cache:
                    from rendering.stream_cache_manager import StreamCacheManager
                    cache_path = os.path.join(cache_dir, f"{yaml_basename}.json")
                    cache_manager = StreamCacheManager(cache_path=cache_path)
                    print(f"[CACHE] Manifest: {cache_path}")

                print(f"Scrittura score per-stream in '{output_dir}' con prefisso '{base_name}'...")
                generated = generator.generate_score_files_per_stream(
                    output_dir=output_dir,
                    base_name=base_name,
                    cache_manager=cache_manager,
                    aif_dir=aif_dir,
                    aif_prefix=base_name,
                )
                print(f"\n Generazione completata! {len(generated)} file generati:")
                for path in generated:
                    print(f"    {path}")

            else:
                print(f"Scrittura score...")
                generator.generate_score_file(output_file)
                print("\n Generazione completata!")

        if do_visualize:
            print("\nGenerazione partitura grafica...")
            pdf_file = output_file.rsplit('.', 1)[0] + '.pdf'
            viz = ScoreVisualizer(generator, config={
                'page_duration': 15.0,
                'show_static_params': show_static,
            })
            viz.export_pdf(pdf_file)

        print(f"Log: {get_clip_log_path()}")

    except FileNotFoundError:
        print(f" Errore: file '{yaml_file}' non trovato")
        sys.exit(1)
    except Exception as e:
        print(f" Errore: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()