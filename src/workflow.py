import sys
from argparse import Namespace
from tqdm import tqdm
import args as parsers
import main


def print_header(header: str):
    text = "# " + header + " #"
    width = len(text)
    tqdm.write()
    tqdm.write()
    tqdm.write("#" * width)
    tqdm.write(text)
    tqdm.write("#" * width)
    tqdm.write()


async def workflow(args: Namespace):
    """Executes the whole workflow sequentially"""
    pbar = tqdm(desc="Overall progress", total=8,
                bar_format="{l_bar}|{bar}| {n_fmt}/{total_fmt}{postfix}")

    print_header("Phase 1: Extract files from the game")
    sub_args = parsers.extract_files.parse_args([args.pattern])
    await main.extract_files(sub_args)
    pbar.update(1)

    print_header("Phase 2: Export wems")
    sub_args = parsers.export_wem.parse_args([])
    await main.export_wem(sub_args)
    pbar.update(1)

    print_header("Phase 3: Isolate vocals")
    sub_args = parsers.isolate_vocals.parse_args(["-m", args.uvr_model])
    await main.isolate_vocals(sub_args)
    pbar.update(1)

    print_header("Phase 4: Revoice the lines")
    sub_args, _ = parsers.revoice.parse_known_args(sys.argv[1:])
    await main.revoice(sub_args)
    pbar.update(1)

    print_header("Phase 5: Merge vocals")
    sub_args = parsers.merge_vocals.parse_args([])
    await main.merge_vocals(sub_args)
    pbar.update(1)

    print_header("Phase 6: Import to Wwise")
    sub_args = parsers.wwise_import.parse_args([])
    await main.wwise_import(sub_args)
    pbar.update(1)

    print_header("Phase 7: Pack the files")
    sub_args = parsers.pack_files.parse_args([args.name])
    await main.pack_files(sub_args)
    pbar.update(1)

    print_header("Phase 8: Zip the archives")
    sub_args = parsers.zip.parse_args([args.name])
    main.zip(sub_args)
    pbar.update(1)

    pbar.close()

    tqdm.write()
    tqdm.write("Congratulations! The workflow is done!")
    tqdm.write(
        f"Your mod can be found in the current directory as '{args.name}.zip'")
